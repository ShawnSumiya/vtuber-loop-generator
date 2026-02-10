from __future__ import annotations

import asyncio
import logging
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import ffmpeg

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# Crossfade時はメモリ対策のため最初にこの解像度へリサイズ（480p相当・16:9で幅854px）
MAX_WIDTH_CROSSFADE = 854


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
        speed: float = 1.0,
    ) -> Path:
        """モードに応じて動画をループ加工し、出力ファイルパスを返す。"""
        # 解像度を正規化（フロント未送信・不正値でも止まらないようにする）
        target_resolution = self._normalize_resolution(target_resolution)
        # 速度を正規化（0.5, 1.0, 2.0 のみ許可、不正値は 1.0 にフォールバック）
        speed = self._normalize_speed(speed)
        logger.info("PROCESS: 処理開始")
        self.temp_dir.mkdir(exist_ok=True, parents=True)
        output_path = self.temp_dir / f"output_{input_path.stem}_{mode.value}.mp4"

        logger.info("PROCESS: 入力動画の長さを取得中")
        base_duration = self.get_video_duration(input_path)
        if base_duration <= 0:
            raise RuntimeError("Could not determine input video duration")
        logger.info(f"PROCESS: 入力動画の長さ = {base_duration}秒")

        # 速度変更後の実効尺（0.5倍速で2倍に、2倍速で0.5倍になる）
        effective_duration = base_duration / speed
        if speed != 1.0:
            logger.info(f"PROCESS: 再生速度 = {speed}x、実効尺 = {effective_duration:.2f}秒")

        # 必要ループ回数は「速度変更後の動画」を基準に計算
        loops = max(1, math.ceil(target_duration / effective_duration))
        logger.info(f"PROCESS: ループ回数 = {loops}回")

        # 入力解像度（高さ）を取得。ダウンスケール時は「先に縮小してから処理」するために使用
        input_height = self.get_video_height(input_path)
        if input_height > 0:
            logger.info(f"PROCESS: 入力動画の高さ = {input_height}px")
        # tpad が速度変更後に正しく duration を解釈するために FPS を取得
        input_fps = self.get_video_fps(input_path)

        # サーバーリソース制限: Original 選択でも入力が 720 超の場合は 720p に制限（OOM 防止）
        if target_resolution == "Original" and input_height > 720:
            logger.info(f"PROCESS: 高解像度のため 720p に制限します（入力高さ {input_height}px）")
            target_resolution = "720p"

        # Crossfade時はメモリ対策のため 480p に固定（無料枠などで安定動作させる）
        if mode == LoopMode.CROSSFade:
            target_resolution = "480p"
            logger.info("PROCESS: Crossfade のため解像度を 480p に制限します（メモリ対策）")

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
                speed,
                input_fps,
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
                speed,
                input_fps,
            )
        elif mode == LoopMode.CROSSFade:
            await asyncio.to_thread(
                self.crossfade_loop,
                input_path,
                output_path,
                target_duration,
                loops,
                crossfade_seconds,
                effective_duration,  # 速度変更後のクリップ長（xfade offset 計算用）
                target_resolution,
                input_height,
                speed,
                input_fps,
            )
        else:
            raise ValueError(f"Unsupported loop mode: {mode}")

        logger.info("PROCESS: 処理完了")
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

    def get_video_fps(self, path: Path) -> float:
        """ffprobe で動画のフレームレートを取得。r_frame_rate から計算。取得失敗時は 30.0 を返す。"""
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=r_frame_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0 or not result.stdout.strip():
            return 30.0
        try:
            # r_frame_rate は "30/1" や "30000/1001" 形式
            frac = result.stdout.strip()
            if "/" in frac:
                num, den = frac.split("/", 1)
                n, d = float(num), float(den)
                return n / d if d > 0 else 30.0
            return float(frac)
        except (ValueError, ZeroDivisionError):
            return 30.0

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

    def _normalize_speed(self, speed: Optional[float]) -> float:
        """再生速度を正規化。0.5, 1.0, 2.0 のみ許可。不正値は 1.0 にフォールバック。"""
        if speed is None:
            return 1.0
        try:
            s = float(speed)
            if s in (0.5, 1.0, 2.0):
                return s
        except (TypeError, ValueError):
            pass
        return 1.0

    def _scale_height_from_resolution(self, resolution: str) -> Optional[int]:
        """解像度文字列から高さを返す。例: '1080p' -> 1080, '4K' -> 2160, '480p' -> 480。"""
        return {"480p": 480, "720p": 720, "1080p": 1080, "4K": 2160}.get(resolution)

    def _print_stderr_error(self, label: str, message: str) -> None:
        """エラー内容をログとコンソールに赤文字で表示（原因特定のため必ず表示）。"""
        logger.error(f"Error: {label} - {message}")
        print(f"{self._RED}Error: {label}{self._RESET}", file=sys.stderr)
        print(f"{self._RED}{message}{self._RESET}", file=sys.stderr)
        sys.stderr.flush()

    def run_ffmpeg_safe(self, stream: ffmpeg.nodes.Stream, output_path: Path) -> None:
        """ffmpeg.run()を実行。capture_stderr=False でパイプが満杯になり止まるのを防ぎ、stderr はそのままターミナルに表示。"""
        try:
            logger.info(f"FFMPEG: Running FFmpeg, output: {output_path}")
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
        speed: float = 1.0,
        input_fps: float = 30.0,
    ) -> None:
        """単純な繰り返しループ。tpad フィルタで静止時間を追加。映像のみ処理し、出力は無音。"""
        logger.info("SIMPLE_LOOP: 開始")

        # 入力は映像ストリームのみ使用（音声は無視）
        stream = ffmpeg.input(str(input_path))
        stream_v = stream["v"]
        if target_resolution != "Original":
            scale_height = self._scale_height_from_resolution(target_resolution)
            if scale_height is not None:
                logger.info(f"SIMPLE_LOOP: リサイズ適用 ({target_resolution} -> 高さ{scale_height})")
                stream_v = stream_v.filter("scale", "-2", str(scale_height))
        stream_resized = stream_v

        # リサイズ直後に速度変更を適用（setpts: 0.5倍速=2*PTS, 2倍速=0.5*PTS）
        if speed != 1.0:
            pts_expr = f"{1.0 / speed}*PTS"
            logger.info(f"SIMPLE_LOOP: 速度変更適用 ({speed}x)")
            stream_v = stream_resized.filter("setpts", pts_expr)
            # tpad が正しく duration（秒）を解釈するため fps を明示（速度変更で FPS が変わる）
            out_fps = max(1, round(input_fps * speed))
            stream_v = stream_v.filter("fps", fps=out_fps)
        else:
            stream_v = stream_resized

        # 静止時間を追加する場合は tpad を適用
        if start_pause_seconds > 0 or end_pause_seconds > 0:
            logger.info(f"SIMPLE_LOOP: STEP 1 - 静止時間追加 ({start_pause_seconds}s + {end_pause_seconds}s)")
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
            # リサイズ or 速度変更を適用した場合は一時ファイルに書き出してからループ
            scale_height = self._scale_height_from_resolution(target_resolution)
            needs_encode = (
                (target_resolution != "Original" and scale_height is not None)
                or speed != 1.0
            )
            if needs_encode:
                temp_for_loop = self.temp_dir / f"prepared_{input_path.stem}.mp4"
                out_stream = ffmpeg.output(
                    stream_v,
                    str(temp_for_loop),
                    vcodec="libx264",
                    preset="ultrafast",
                    crf=18,
                )
                self.run_ffmpeg_safe(out_stream, temp_for_loop)
                loop_source = temp_for_loop
            else:
                loop_source = input_path

        # -stream_loop で指定回数分繰り返し、-t で最終長さを切り詰め（映像のみ、出力無音）
        logger.info(f"SIMPLE_LOOP: STEP 2 - ループ生成開始 ({loops}回)")
        loop_input = ffmpeg.input(str(loop_source), stream_loop=loops - 1)
        out_stream = ffmpeg.output(
            loop_input["v"],
            str(output_path),
            vcodec="copy",
            t=target_duration,
        )
        self.run_ffmpeg_safe(out_stream, output_path)
        logger.info("SIMPLE_LOOP: STEP 2 - 完了")

        # 一時ファイル削除
        if loop_source != input_path and loop_source.exists():
            try:
                loop_source.unlink()
            except OSError:
                pass
        logger.info("SIMPLE_LOOP: 完了")

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
        speed: float = 1.0,
        input_fps: float = 30.0,
    ) -> None:
        """シンプルなPing-Pongループ。映像のみ処理し、出力は無音。
        
        ストリームA: 先頭に停止(tpad) + 入力動画 + 末尾に停止(tpad)
        ストリームB: 逆再生(reverse) + setpts(PTSリセット) のみ（末尾にtpadは付けない）
        End Pause時: ストリームPause = 先頭1フレームを end_pause_seconds 分延長したクリップを別出力
        結合: A + B + (Pause) → 再生→Pause→逆再生→Pause→再生 の1サイクル
        
        解像度: 4K→720p などダウンスケールの場合は先に縮小してから reverse（メモリ節約）。
        それ以外は reverse を元解像度で行い、出力直前に scale する。
        """
        logger.info("PINGPONG_LOOP: 開始")

        scale_height = self._scale_height_from_resolution(target_resolution) if target_resolution != "Original" else None
        # ダウンスケール（例: 4K入力→720p出力）なら先に縮小してから reverse しないと OOM になる
        scale_first = scale_height is not None and input_height > 0 and scale_height < input_height

        if scale_first:
            logger.info(f"PINGPONG_LOOP: ダウンスケールのため先にリサイズ ({target_resolution} -> 高さ{scale_height})")
        elif scale_height is not None:
            logger.info(f"PINGPONG_LOOP: リサイズは出力直前に適用 ({target_resolution} -> 高さ{scale_height})")

        input_video = ffmpeg.input(str(input_path))
        stream_v = input_video["v"]
        if scale_first:
            stream_v = stream_v.filter("scale", "-2", str(scale_height))
        stream_resized = stream_v

        # リサイズ直後に速度変更を適用（setpts）
        if speed != 1.0:
            pts_expr = f"{1.0 / speed}*PTS"
            logger.info(f"PINGPONG_LOOP: 速度変更適用 ({speed}x)")
            stream_v = stream_resized.filter("setpts", pts_expr)
            # tpad が正しく duration（秒）を解釈するため fps を明示（速度変更で FPS が変わる）
            out_fps = max(1, round(input_fps * speed))
            stream_v = stream_v.filter("fps", fps=out_fps)
        else:
            stream_v = stream_resized

        # ストリームA: Forward パート（先頭・末尾に tpad）
        logger.info("PINGPONG_LOOP: ストリームA生成開始")
        if start_pause_seconds > 0 or end_pause_seconds > 0:
            stream_a = stream_v
            if start_pause_seconds > 0:
                stream_a = stream_a.filter("tpad", start_duration=start_pause_seconds, start_mode="clone")
            if end_pause_seconds > 0:
                stream_a = stream_a.filter("tpad", stop_duration=end_pause_seconds, stop_mode="clone")
        else:
            stream_a = stream_v

        # ストリームB: Reverse パート（末尾にtpadは付けず、End Pauseは別セグメントで結合）
        logger.info("PINGPONG_LOOP: ストリームB生成開始")
        stream_b = stream_v.filter("reverse").filter("setpts", "PTS-STARTPTS")

        # End Pause時: 逆再生の直後に挿入する「ポーズクリップ」（先頭1フレームを end_pause 秒分表示）
        effective_fps = max(1, round(input_fps * speed)) if speed != 1.0 else input_fps
        one_frame_duration = 1.0 / effective_fps
        if end_pause_seconds > 0:
            stream_pause = (
                stream_v.filter("trim", duration=one_frame_duration)
                .filter("setpts", "PTS-STARTPTS")
                .filter("tpad", stop_duration=end_pause_seconds, stop_mode="clone")
            )
        else:
            stream_pause = None

        # アップスケール／同一解像度のときだけ、出力直前にリサイズ
        if scale_height is not None and not scale_first:
            stream_a = stream_a.filter("scale", "-2", str(scale_height))
            stream_b = stream_b.filter("scale", "-2", str(scale_height))
            if stream_pause is not None:
                stream_pause = stream_pause.filter("scale", "-2", str(scale_height))

        # 結合: A + B、End Pause時は A + B + Pause（映像のみ）
        logger.info("PINGPONG_LOOP: ストリーム結合開始")
        cycle_path = self.temp_dir / f"cycle_{input_path.stem}.mp4"
        concat_list = self.temp_dir / f"concat_{input_path.stem}.txt"
        temp_a = self.temp_dir / f"temp_a_{input_path.stem}.mp4"
        temp_b = self.temp_dir / f"temp_b_{input_path.stem}.mp4"
        temp_pause = self.temp_dir / f"temp_pause_{input_path.stem}.mp4"

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

        concat_lines = [f"file '{temp_a.absolute()}'", f"file '{temp_b.absolute()}'"]
        if stream_pause is not None:
            stream = ffmpeg.output(
                stream_pause,
                str(temp_pause),
                vcodec="libx264",
                preset="ultrafast",
                crf=18,
            )
            self.run_ffmpeg_safe(stream, temp_pause)
            concat_lines.append(f"file '{temp_pause.absolute()}'")

        concat_list.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
        concat_input = ffmpeg.input(str(concat_list), format="concat", safe=0)
        stream = ffmpeg.output(
            concat_input["v"],
            str(cycle_path),
            vcodec="copy",
        )
        self.run_ffmpeg_safe(stream, cycle_path)

        to_unlink = [temp_a, temp_b, concat_list]
        if end_pause_seconds > 0:
            to_unlink.append(temp_pause)
        for p in to_unlink:
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass
        logger.info("PINGPONG_LOOP: ストリーム結合完了")

        # ループ生成（映像のみ、出力無音）
        logger.info(f"PINGPONG_LOOP: ループ生成開始 ({loops}回)")
        loop_input = ffmpeg.input(str(cycle_path), stream_loop=loops - 1)
        stream = ffmpeg.output(
            loop_input["v"],
            str(output_path),
            vcodec="copy",
            t=target_duration,
        )
        self.run_ffmpeg_safe(stream, output_path)
        logger.info("PINGPONG_LOOP: ループ生成完了")
        
        # 一時ファイル削除
        if cycle_path.exists():
            try:
                cycle_path.unlink()
            except OSError:
                pass
        logger.info("PINGPONG_LOOP: 完了")

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
        speed: float = 1.0,
        input_fps: float = 30.0,
    ) -> None:
        """前後をクロスフェードさせたシームレスループ。映像のみ処理し、出力は無音。
        clip_duration は速度変更後の実効尺（xfade offset 計算用）。
        メモリ対策のため、Crossfade 時は常に最初に 480p（幅854px）へリサイズしてから xfade する。
        """
        logger.info("CROSSFADE_LOOP: 開始")

        # crossfade_seconds が長すぎる場合を補正
        crossfade = max(0.1, min(crossfade_seconds, clip_duration / 2))
        offset = max(0.0, clip_duration - crossfade)
        logger.info(f"CROSSFADE_LOOP: STEP 1 - クロスフェード設定 (duration={crossfade}s, offset={offset}s)")

        # 【重要】メモリ対策: Crossfade 時は常に最初に 480p 相当へリサイズ（scale=854:-2）
        logger.info(f"CROSSFADE_LOOP: メモリ対策のため先に 480p へリサイズ (幅{MAX_WIDTH_CROSSFADE}px)")
        stream = ffmpeg.input(str(input_path))
        v = stream["v"].filter("scale", MAX_WIDTH_CROSSFADE, -2)
        stream_resized = v

        # リサイズ直後に速度変更を適用（setpts）
        if speed != 1.0:
            pts_expr = f"{1.0 / speed}*PTS"
            logger.info(f"CROSSFADE_LOOP: 速度変更適用 ({speed}x)")
            v = stream_resized.filter("setpts", pts_expr)
            out_fps = max(1, round(input_fps * speed))
            v = v.filter("fps", fps=out_fps)
        else:
            v = stream_resized
            out_fps = max(1, round(input_fps))
            v = v.filter("fps", fps=out_fps)

        v_split = v.filter_multi_output("split", 2)
        v0 = v_split.stream(0).filter("format", "yuv420p").filter("setsar", "1")
        v1 = v_split[1].filter("format", "yuv420p").filter("setsar", "1")
        v_out = ffmpeg.filter([v0, v1], "xfade", transition="fade", duration=crossfade, offset=offset)
        # 出力は 480p のまま（追加の scale はしない）

        # 1 サイクル分のループクリップ（映像のみ、無音）
        cycle_path = self.temp_dir / f"cross_{input_path.stem}.mp4"
        logger.info("CROSSFADE_LOOP: STEP 2 - クロスフェード動画生成開始")
        stream = ffmpeg.output(
            v_out,
            str(cycle_path),
            vcodec="libx264",
            preset="ultrafast",
            crf=18,
        )
        self.run_ffmpeg_safe(stream, cycle_path)
        logger.info("CROSSFADE_LOOP: STEP 2 - クロスフェード動画生成完了")

        # このサイクルクリップを単純ループして所定時間まで伸ばす（映像のみ、出力無音）
        logger.info("CROSSFADE_LOOP: STEP 3 - ループ生成開始")
        cycle_duration = self.get_video_duration(cycle_path)
        if cycle_duration <= 0:
            raise RuntimeError("Invalid crossfade cycle duration")

        approx_loops = max(1, target_duration / cycle_duration)
        loop_count = max(1, int(round(approx_loops)))
        total_duration = cycle_duration * loop_count

        logger.info(
            "CROSSFADE_LOOP: STEP 3 - ループ回数: %d回 (サイクル長=%.3fs, 目標=%.3fs, 実際の出力長=%.3fs)",
            loop_count,
            cycle_duration,
            target_duration,
            total_duration,
        )

        # STEP 3 は一時ファイルに出力。STEP 4 で「末尾→先頭」をクロスフェードしてから最終出力する
        looped_path = self.temp_dir / f"looped_{input_path.stem}.mp4"
        loop_input = ffmpeg.input(str(cycle_path), stream_loop=loop_count - 1)
        stream = ffmpeg.output(
            loop_input["v"],
            str(looped_path),
            vcodec="copy",
            t=total_duration,
        )
        self.run_ffmpeg_safe(stream, looped_path)
        logger.info("CROSSFADE_LOOP: STEP 3 - ループ生成完了")

        # STEP 4: 0に戻る境界でもクロスフェードする（再生→Crossfade→再生→Crossfade→… を実現）
        # ループ動画の「末尾数秒」と「先頭数秒」を xfade でつなぎ、出力の最後をそのクロスフェードにする。
        L = self.get_video_duration(looped_path)
        # mid を取るには crossfade ～ L-2*crossfade の区間が必要なので L > 3*crossfade である必要がある
        if L > 3 * crossfade:
            logger.info("CROSSFADE_LOOP: STEP 4 - 末尾→先頭のクロスフェードを適用 (L=%.2fs)", L)
            inp = ffmpeg.input(str(looped_path))
            v = inp["v"]
            v_split = v.filter_multi_output("split", 3)
            # trim は start+duration で指定（end は環境によって解釈が変わるため避ける）
            head = (
                v_split[0]
                .filter("trim", start=0, duration=crossfade)
                .filter("setpts", "PTS-STARTPTS")
                .filter("format", "yuv420p")
                .filter("setsar", "1")
            )
            mid_duration = L - 3 * crossfade
            mid = (
                v_split[1]
                .filter("trim", start=crossfade, duration=mid_duration)
                .filter("setpts", "PTS-STARTPTS")
                .filter("format", "yuv420p")
                .filter("setsar", "1")
            )
            tail = (
                v_split[2]
                .filter("trim", start=L - 2 * crossfade, duration=crossfade)
                .filter("setpts", "PTS-STARTPTS")
                .filter("format", "yuv420p")
                .filter("setsar", "1")
            )
            tailhead = ffmpeg.filter(
                [tail, head], "xfade", transition="fade", duration=crossfade, offset=0
            )
            out = ffmpeg.filter([mid, tailhead], "concat", n=2, v=1, a=0)
            stream = ffmpeg.output(
                out,
                str(output_path),
                vcodec="libx264",
                preset="ultrafast",
                crf=18,
            )
            self.run_ffmpeg_safe(stream, output_path)
            logger.info("CROSSFADE_LOOP: STEP 4 - 完了")
        else:
            # 動画が短くて末尾→先頭 xfade を取れない場合はそのままコピー
            logger.info(
                "CROSSFADE_LOOP: STEP 4 - スキップ（L=%.2fs <= 3*crossfade=%.2fs）、ループ動画をそのまま出力",
                L,
                3 * crossfade,
            )
            shutil.copy2(looped_path, output_path)

        try:
            if cycle_path.exists():
                cycle_path.unlink()
            if looped_path.exists():
                looped_path.unlink()
        except OSError:
            pass
        logger.info("CROSSFADE_LOOP: 完了")