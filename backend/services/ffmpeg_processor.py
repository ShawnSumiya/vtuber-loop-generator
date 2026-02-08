from __future__ import annotations

import asyncio
import math
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import ffmpeg


class LoopMode(str, Enum):
    SIMPLE = "simple"
    PINGPONG = "pingpong"
    CROSSFade = "crossfade"


@dataclass
class VideoProcessor:
    temp_dir: Path

    async def process(
        self,
        input_path: Path,
        target_duration: int,
        mode: LoopMode,
        crossfade_seconds: float = 1.0,
        start_pause_seconds: float = 0.0,
        end_pause_seconds: float = 0.0,
        target_resolution: str = "Original",
    ) -> Path:
        """モードに応じて動画をループ加工し、出力ファイルパスを返す。"""
        # 解像度を正規化（フロント未送信・不正値でも止まらないようにする）
        target_resolution = self._normalize_resolution(target_resolution)
        print("--- PROCESS: 処理開始 ---")
        self.temp_dir.mkdir(exist_ok=True, parents=True)
        output_path = self.temp_dir / f"output_{input_path.stem}_{mode.value}.mp4"

        print(f"--- PROCESS: 入力動画の長さを取得中 ---")
        base_duration = self.get_video_duration(input_path)
        if base_duration <= 0:
            raise RuntimeError("Could not determine input video duration")
        print(f"--- PROCESS: 入力動画の長さ = {base_duration}秒 ---")

        # 必要ループ回数を計算
        loops = max(1, math.ceil(target_duration / base_duration))
        print(f"--- PROCESS: ループ回数 = {loops}回 ---")

        # 入力解像度（高さ）を取得。ダウンスケール時は「先に縮小してから処理」するために使用
        input_height = self.get_video_height(input_path)
        if input_height > 0:
            print(f"--- PROCESS: 入力動画の高さ = {input_height}px ---")

        # FFmpeg は同期ブロッキングのため、イベントループをブロックしないようスレッドで実行
        if mode == LoopMode.SIMPLE:
            await asyncio.to_thread(
                self.simple_loop,
                input_path,
                output_path,
                target_duration,
                loops,
                start_pause_seconds,
                end_pause_seconds,
                target_resolution,
            )
        elif mode == LoopMode.PINGPONG:
            await asyncio.to_thread(
                self.pingpong_loop,
                input_path,
                output_path,
                target_duration,
                loops,
                start_pause_seconds,
                end_pause_seconds,
                target_resolution,
                input_height,
            )
        elif mode == LoopMode.CROSSFade:
            await asyncio.to_thread(
                self.crossfade_loop,
                input_path,
                output_path,
                target_duration,
                loops,
                crossfade_seconds,
                base_duration,
                target_resolution,
                input_height,
            )
        else:
            raise ValueError(f"Unsupported loop mode: {mode}")

        print("--- PROCESS: 処理完了 ---")
        return output_path

    # ---- Core helpers ----

    def get_video_duration(self, path: Path) -> float:
        """ffprobe を使って動画長さ（秒）を取得。"""
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")
        try:
            return float(result.stdout.strip())
        except ValueError as e:
            raise RuntimeError("Invalid duration from ffprobe") from e

    def get_video_height(self, path: Path) -> int:
        """ffprobe で動画ストリームの高さ（ピクセル）を取得。取得失敗時は 0 を返す。"""
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=height",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0 or not result.stdout.strip():
            return 0
        try:
            return int(result.stdout.strip())
        except ValueError:
            return 0

    # ターミナルに赤文字でエラーを表示するためのANSIコード
    _RED = "\033[91m"
    _RESET = "\033[0m"

    def _normalize_resolution(self, resolution: Optional[str]) -> str:
        """解像度を正規化。不正値・未指定は 'Original' にフォールバック（解像度変更でも止まらないようにする）。"""
        if not resolution or not isinstance(resolution, str):
            return "Original"
        r = resolution.strip()
        if r in ("Original", "720p", "1080p", "4K"):
            return r
        return "Original"

    def _scale_height_from_resolution(self, resolution: str) -> Optional[int]:
        """解像度文字列から高さを返す。例: '1080p' -> 1080, '4K' -> 2160。"""
        return {"720p": 720, "1080p": 1080, "4K": 2160}.get(resolution)

    def _print_stderr_error(self, label: str, message: str) -> None:
        """エラー内容をコンソールに赤文字で表示（原因特定のため必ず表示）。"""
        print(f"{self._RED}Error: {label}{self._RESET}", file=sys.stderr)
        print(f"{self._RED}{message}{self._RESET}", file=sys.stderr)
        sys.stderr.flush()

    def run_ffmpeg_safe(self, stream: ffmpeg.nodes.Stream, output_path: Path) -> None:
        """ffmpeg.run()を実行。capture_stderr=False でパイプが満杯になり止まるのを防ぎ、stderr はそのままターミナルに表示。"""
        try:
            print(f"Running FFmpeg, output: {output_path}", file=sys.stderr)
            # capture_stderr=True だと FFmpeg の進捗出力でパイプが満杯→デッドロックで「処理中」のまま止まるため False にする
            ffmpeg.run(
                stream,
                overwrite_output=True,
                quiet=False,
                capture_stdout=False,
                capture_stderr=False,
            )
        except ffmpeg.Error as e:
            # stderr を必ずコンソールに表示（赤文字で目立たせる）
            stderr_text = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            stdout_text = e.stdout.decode("utf-8", errors="replace") if e.stdout else ""
            self._print_stderr_error("FFmpeg failed (stderr)", stderr_text or str(e))
            if stdout_text:
                self._print_stderr_error("FFmpeg stdout", stdout_text)
            raise RuntimeError(f"FFmpeg processing failed: {stderr_text or str(e)}") from e
        except Exception as e:
            self._print_stderr_error("Unexpected exception", str(e))
            # 例外に stderr があればそれも表示
            if getattr(e, "stderr", None):
                stderr_text = e.stderr.decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else str(e.stderr)
                self._print_stderr_error("Exception stderr", stderr_text)
            raise RuntimeError(f"FFmpeg execution error: {e}") from e

    # ---- Loop strategies ----

    def simple_loop(
        self,
        input_path: Path,
        output_path: Path,
        target_duration: int,
        loops: int,
        start_pause_seconds: float = 0.0,
        end_pause_seconds: float = 0.0,
        target_resolution: str = "Original",
    ) -> None:
        """単純な繰り返しループ。tpad フィルタで静止時間を追加。映像のみ処理し、出力は無音。"""
        print("--- SIMPLE_LOOP: 開始 ---")

        # 入力は映像ストリームのみ使用（音声は無視）
        stream = ffmpeg.input(str(input_path))
        stream_v = stream["v"]
        if target_resolution != "Original":
            scale_height = self._scale_height_from_resolution(target_resolution)
            if scale_height is not None:
                print(f"--- SIMPLE_LOOP: リサイズ適用 ({target_resolution} -> 高さ{scale_height}) ---")
                # 幅は -2（アスペクト比維持・2の倍数）、高さを指定。文字列で渡してエスケープ不具合を防ぐ
                stream_v = stream_v.filter("scale", "-2", str(scale_height))

        # 静止時間を追加する場合は tpad を適用
        if start_pause_seconds > 0 or end_pause_seconds > 0:
            print(f"--- SIMPLE_LOOP: STEP 1 - 静止時間追加 ({start_pause_seconds}s + {end_pause_seconds}s) ---")
            stream_v = stream_v.filter(
                "tpad",
                start_duration=start_pause_seconds,
                start_mode="clone",
                stop_duration=end_pause_seconds,
                stop_mode="clone",
            )
            paused_video = self.temp_dir / f"paused_{input_path.stem}.mp4"
            out_stream = ffmpeg.output(
                stream_v,
                str(paused_video),
                vcodec="libx264",
                preset="ultrafast",
                crf=18,
            )
            self.run_ffmpeg_safe(out_stream, paused_video)
            loop_source = paused_video
        else:
            # リサイズのみ適用した場合は一時ファイルに書き出してからループ
            scale_height = self._scale_height_from_resolution(target_resolution)
            if target_resolution != "Original" and scale_height is not None:
                scaled_only = self.temp_dir / f"scaled_{input_path.stem}.mp4"
                out_stream = ffmpeg.output(
                    stream_v,
                    str(scaled_only),
                    vcodec="libx264",
                    preset="ultrafast",
                    crf=18,
                )
                self.run_ffmpeg_safe(out_stream, scaled_only)
                loop_source = scaled_only
            else:
                loop_source = input_path

        # -stream_loop で指定回数分繰り返し、-t で最終長さを切り詰め（映像のみ、出力無音）
        print(f"--- SIMPLE_LOOP: STEP 2 - ループ生成開始 ({loops}回) ---")
        loop_input = ffmpeg.input(str(loop_source), stream_loop=loops - 1)
        out_stream = ffmpeg.output(
            loop_input["v"],
            str(output_path),
            vcodec="copy",
            t=target_duration,
        )
        self.run_ffmpeg_safe(out_stream, output_path)
        print("--- SIMPLE_LOOP: STEP 2 - 完了 ---")

        # 一時ファイル削除
        if loop_source != input_path and loop_source.exists():
            try:
                loop_source.unlink()
            except OSError:
                pass
        print("--- SIMPLE_LOOP: 完了 ---")

    def pingpong_loop(
        self,
        input_path: Path,
        output_path: Path,
        target_duration: int,
        loops: int,
        start_pause_seconds: float = 0.0,
        end_pause_seconds: float = 0.0,
        target_resolution: str = "Original",
        input_height: int = 0,
    ) -> None:
        """シンプルなPing-Pongループ。映像のみ処理し、出力は無音。
        
        ストリームA: 先頭に停止(tpad) + 入力動画 + 末尾に停止(tpad)
        ストリームB: 逆再生(reverse) + setpts(PTSリセット) + 末尾に停止(tpad)（End Pause時）
        結合: A + B → 再生→静止→逆再生→静止→再生 の1サイクル
        
        解像度: 4K→720p などダウンスケールの場合は先に縮小してから reverse（メモリ節約）。
        それ以外は reverse を元解像度で行い、出力直前に scale する。
        """
        print("--- PINGPONG_LOOP: 開始 ---")

        scale_height = self._scale_height_from_resolution(target_resolution) if target_resolution != "Original" else None
        # ダウンスケール（例: 4K入力→720p出力）なら先に縮小してから reverse しないと OOM になる
        scale_first = scale_height is not None and input_height > 0 and scale_height < input_height

        if scale_first:
            print(f"--- PINGPONG_LOOP: ダウンスケールのため先にリサイズ ({target_resolution} -> 高さ{scale_height}) ---")
        elif scale_height is not None:
            print(f"--- PINGPONG_LOOP: リサイズは出力直前に適用 ({target_resolution} -> 高さ{scale_height}) ---")

        input_video = ffmpeg.input(str(input_path))
        stream_v = input_video["v"]
        if scale_first:
            stream_v = stream_v.filter("scale", "-2", str(scale_height))

        # ストリームA: Forward パート（先頭・末尾に tpad）
        print("--- PINGPONG_LOOP: ストリームA生成開始 ---")
        if start_pause_seconds > 0 or end_pause_seconds > 0:
            stream_a = stream_v
            if start_pause_seconds > 0:
                stream_a = stream_a.filter("tpad", start_duration=start_pause_seconds, start_mode="clone")
            if end_pause_seconds > 0:
                stream_a = stream_a.filter("tpad", stop_duration=end_pause_seconds, stop_mode="clone")
        else:
            stream_a = stream_v

        # ストリームB: Reverse パート（scale_first 時は既に縮小済み、そうでなければ元解像度）
        print("--- PINGPONG_LOOP: ストリームB生成開始 ---")
        stream_b = stream_v.filter("reverse").filter("setpts", "PTS-STARTPTS")
        if end_pause_seconds > 0:
            stream_b = stream_b.filter("tpad", stop_duration=end_pause_seconds, stop_mode="clone")

        # アップスケール／同一解像度のときだけ、出力直前にリサイズ
        if scale_height is not None and not scale_first:
            stream_a = stream_a.filter("scale", "-2", str(scale_height))
            stream_b = stream_b.filter("scale", "-2", str(scale_height))

        # 結合: A + B（映像のみ）
        print("--- PINGPONG_LOOP: ストリーム結合開始 ---")
        cycle_path = self.temp_dir / f"cycle_{input_path.stem}.mp4"
        concat_list = self.temp_dir / f"concat_{input_path.stem}.txt"
        temp_a = self.temp_dir / f"temp_a_{input_path.stem}.mp4"
        temp_b = self.temp_dir / f"temp_b_{input_path.stem}.mp4"

        stream = ffmpeg.output(
            stream_a,
            str(temp_a),
            vcodec="libx264",
            preset="ultrafast",
            crf=18,
        )
        self.run_ffmpeg_safe(stream, temp_a)

        stream = ffmpeg.output(
            stream_b,
            str(temp_b),
            vcodec="libx264",
            preset="ultrafast",
            crf=18,
        )
        self.run_ffmpeg_safe(stream, temp_b)

        concat_list.write_text(
            f"file '{temp_a.absolute()}'\nfile '{temp_b.absolute()}'\n",
            encoding="utf-8",
        )
        concat_input = ffmpeg.input(str(concat_list), format="concat", safe=0)
        stream = ffmpeg.output(
            concat_input["v"],
            str(cycle_path),
            vcodec="copy",
        )
        self.run_ffmpeg_safe(stream, cycle_path)

        for p in [temp_a, temp_b, concat_list]:
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass
        print("--- PINGPONG_LOOP: ストリーム結合完了 ---")

        # ループ生成（映像のみ、出力無音）
        print(f"--- PINGPONG_LOOP: ループ生成開始 ({loops}回) ---")
        loop_input = ffmpeg.input(str(cycle_path), stream_loop=loops - 1)
        stream = ffmpeg.output(
            loop_input["v"],
            str(output_path),
            vcodec="copy",
            t=target_duration,
        )
        self.run_ffmpeg_safe(stream, output_path)
        print("--- PINGPONG_LOOP: ループ生成完了 ---")
        
        # 一時ファイル削除
        if cycle_path.exists():
            try:
                cycle_path.unlink()
            except OSError:
                pass
        print("--- PINGPONG_LOOP: 完了 ---")

    def crossfade_loop(
        self,
        input_path: Path,
        output_path: Path,
        target_duration: int,
        loops: int,
        crossfade_seconds: float,
        clip_duration: float,
        target_resolution: str = "Original",
        input_height: int = 0,
    ) -> None:
        """前後をクロスフェードさせたシームレスループ。映像のみ処理し、出力は無音。
        4K→720p などダウンスケールの場合は先に縮小してから xfade（メモリ節約）。そうでなければ xfade 後に scale。
        """
        print("--- CROSSFADE_LOOP: 開始 ---")

        # crossfade_seconds が長すぎる場合を補正
        crossfade = max(0.1, min(crossfade_seconds, clip_duration / 2))
        offset = max(0.0, clip_duration - crossfade)
        print(f"--- CROSSFADE_LOOP: STEP 1 - クロスフェード設定 (duration={crossfade}s, offset={offset}s) ---")

        scale_height = self._scale_height_from_resolution(target_resolution) if target_resolution != "Original" else None
        scale_first = scale_height is not None and input_height > 0 and scale_height < input_height

        if scale_first:
            print(f"--- CROSSFADE_LOOP: ダウンスケールのため先にリサイズ ({target_resolution} -> 高さ{scale_height}) ---")
        elif scale_height is not None:
            print(f"--- CROSSFADE_LOOP: リサイズは出力直前に適用 ({target_resolution} -> 高さ{scale_height}) ---")

        stream = ffmpeg.input(str(input_path))
        v = stream["v"]
        if scale_first:
            v = v.filter("scale", "-2", str(scale_height))

        v_split = v.filter_multi_output("split", 2)
        v0 = v_split.stream(0).filter("format", "yuv420p").filter("setsar", "1")
        v1 = v_split[1].filter("format", "yuv420p").filter("setsar", "1")
        v_out = ffmpeg.filter([v0, v1], "xfade", transition="fade", duration=crossfade, offset=offset)

        if scale_height is not None and not scale_first:
            v_out = v_out.filter("scale", "-2", str(scale_height))

        # 1 サイクル分のループクリップ（映像のみ、無音）
        cycle_path = self.temp_dir / f"cross_{input_path.stem}.mp4"
        print("--- CROSSFADE_LOOP: STEP 2 - クロスフェード動画生成開始 ---")
        stream = ffmpeg.output(
            v_out,
            str(cycle_path),
            vcodec="libx264",
            preset="ultrafast",
            crf=18,
        )
        self.run_ffmpeg_safe(stream, cycle_path)
        print("--- CROSSFADE_LOOP: STEP 2 - クロスフェード動画生成完了 ---")

        # このサイクルクリップを単純ループして所定時間まで伸ばす（映像のみ、出力無音）
        print("--- CROSSFADE_LOOP: STEP 3 - ループ生成開始 ---")
        cycle_duration = self.get_video_duration(cycle_path)
        loop_count = max(1, math.ceil(target_duration / cycle_duration))
        print(f"--- CROSSFADE_LOOP: STEP 3 - ループ回数: {loop_count}回 ---")

        loop_input = ffmpeg.input(str(cycle_path), stream_loop=loop_count - 1)
        stream = ffmpeg.output(
            loop_input["v"],
            str(output_path),
            vcodec="copy",
            t=target_duration,
        )
        self.run_ffmpeg_safe(stream, output_path)
        print("--- CROSSFADE_LOOP: STEP 3 - ループ生成完了 ---")

        try:
            if cycle_path.exists():
                cycle_path.unlink()
        except OSError:
            pass
        print("--- CROSSFADE_LOOP: 完了 ---")