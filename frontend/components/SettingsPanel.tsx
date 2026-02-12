"use client";

import { Repeat, ArrowLeftRight, Sparkles } from "lucide-react";

type LoopMode = "simple" | "pingpong" | "crossfade";

type Resolution = "Original" | "720p" | "1080p";

type PlaybackSpeed = 0.5 | 1 | 2;

const PRO_ACCESS_KEY = "LOOP-PRO-2026-C3";

interface SettingsPanelProps {
  durationSeconds: number;
  onDurationChange: (value: number) => void;
  loopMode: LoopMode;
  onLoopModeChange: (mode: LoopMode) => void;
  crossfadeSeconds: number;
  onCrossfadeChange: (value: number) => void;
  startPauseSeconds: number;
  onStartPauseChange: (value: number) => void;
  endPauseSeconds: number;
  onEndPauseChange: (value: number) => void;
  resolution: Resolution;
  onResolutionChange: (value: Resolution) => void;
  playbackSpeed: PlaybackSpeed;
  onPlaybackSpeedChange: (value: PlaybackSpeed) => void;
  disabled: boolean;
  isProUser: boolean;
  onUnlockPro: () => void;
}

export default function SettingsPanel({
  durationSeconds,
  onDurationChange,
  loopMode,
  onLoopModeChange,
  crossfadeSeconds,
  onCrossfadeChange,
  startPauseSeconds,
  onStartPauseChange,
  endPauseSeconds,
  onEndPauseChange,
  resolution,
  onResolutionChange,
  playbackSpeed,
  onPlaybackSpeedChange,
  disabled,
  isProUser,
  onUnlockPro,
}: SettingsPanelProps) {
  const formatDuration = (seconds: number): string => {
    if (seconds < 60) {
      return `${seconds}秒`;
    }
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return secs > 0 ? `${minutes}分${secs}秒` : `${minutes}分`;
  };

  const handleSelectPingPong = () => {
    if (disabled) return;

    if (isProUser) {
      onLoopModeChange("pingpong");
      return;
    }

    if (typeof window === "undefined") return;

    const input = window.prompt("Pro版キーを入力してください");
    if (!input) return;

    if (input === PRO_ACCESS_KEY) {
      onUnlockPro();
      onLoopModeChange("pingpong");
    } else {
      window.alert("キーが正しくありません。");
    }
  };

  const handleSelectCrossfade = () => {
    if (disabled) return;

    if (isProUser) {
      onLoopModeChange("crossfade");
      return;
    }

    if (typeof window === "undefined") return;

    const input = window.prompt("Pro版キーを入力してください");
    if (!input) return;

    if (input === PRO_ACCESS_KEY) {
      onUnlockPro();
      onLoopModeChange("crossfade");
    } else {
      window.alert("キーが正しくありません。");
    }
  };

  return (
    <div className="space-y-6">
      {/* 目標の長さ */}
      <div>
        <label className="block text-sm font-medium mb-2">
          目標の長さ: {formatDuration(durationSeconds)}
        </label>
        <div className="flex flex-col sm:flex-row gap-2 sm:gap-4 sm:items-center">
          <input
            type="range"
            min="5"
            max="3600"
            step="5"
            value={durationSeconds}
            onChange={(e) => onDurationChange(Number(e.target.value))}
            disabled={disabled}
            className="w-full sm:flex-1 h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary touch-manipulation"
          />
          <div className="flex items-center gap-2 shrink-0">
            <input
              type="number"
              min="5"
              max="3600"
              step="5"
              value={durationSeconds}
              onChange={(e) => onDurationChange(Number(e.target.value))}
              disabled={disabled}
              className="w-20 px-2 py-1.5 sm:py-1 bg-secondary border border-border rounded text-sm min-h-[44px] sm:min-h-0"
            />
            <span className="text-xs text-muted-foreground">秒</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 sm:gap-4 mt-2">
          <button
            onClick={() => onDurationChange(30)}
            disabled={disabled}
            className="text-xs px-3 py-2 min-h-[44px] sm:min-h-0 sm:py-1 bg-secondary hover:bg-secondary/80 rounded transition-colors disabled:opacity-50 touch-manipulation"
          >
            30秒
          </button>
          <button
            onClick={() => onDurationChange(60)}
            disabled={disabled}
            className="text-xs px-3 py-2 min-h-[44px] sm:min-h-0 sm:py-1 bg-secondary hover:bg-secondary/80 rounded transition-colors disabled:opacity-50 touch-manipulation"
          >
            1分
          </button>
          <button
            onClick={() => onDurationChange(300)}
            disabled={disabled}
            className="text-xs px-3 py-2 min-h-[44px] sm:min-h-0 sm:py-1 bg-secondary hover:bg-secondary/80 rounded transition-colors disabled:opacity-50 touch-manipulation"
          >
            5分
          </button>
          <button
            onClick={() => onDurationChange(3600)}
            disabled={disabled}
            className="text-xs px-3 py-2 min-h-[44px] sm:min-h-0 sm:py-1 bg-secondary hover:bg-secondary/80 rounded transition-colors disabled:opacity-50 touch-manipulation"
          >
            1時間
          </button>
        </div>
      </div>

      {/* ループモード選択 */}
      <div>
        <label className="block text-sm font-medium mb-3">
          ループモード
        </label>
        <div className="grid grid-cols-1 gap-3">
          <button
            onClick={() => onLoopModeChange("simple")}
            disabled={disabled}
            className={`p-3 sm:p-4 min-h-[44px] rounded-lg border-2 text-left transition-all touch-manipulation ${
              loopMode === "simple"
                ? "border-primary bg-primary/10"
                : "border-border hover:border-primary/50"
            } disabled:opacity-50`}
          >
            <div className="flex items-center gap-3">
              <Repeat className="w-5 h-5 text-primary" />
              <div>
                <p className="font-medium text-sm">Simple Loop</p>
                <p className="text-xs text-muted-foreground mt-1">
                  単純な繰り返し。最もシンプルで高速。
                </p>
              </div>
            </div>
          </button>

          <button
            onClick={handleSelectPingPong}
            disabled={disabled}
            className={`p-3 sm:p-4 min-h-[44px] rounded-lg border-2 text-left transition-all touch-manipulation ${
              loopMode === "pingpong"
                ? "border-primary bg-primary/10"
                : "border-border hover:border-primary/50"
            } disabled:opacity-50`}
          >
            <div className="flex items-center gap-3">
              <ArrowLeftRight className="w-5 h-5 text-primary" />
              <div>
                <p className="font-medium text-sm flex items-center gap-1">
                  Ping-Pong (Mirror)
                  {!isProUser && <span className="text-[11px]">🔒 Pro</span>}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  再生→逆再生→再生... を繰り返す。継ぎ目なし。
                </p>
              </div>
            </div>
          </button>

          <button
            onClick={handleSelectCrossfade}
            disabled={disabled}
            className={`p-3 sm:p-4 min-h-[44px] rounded-lg border-2 text-left transition-all touch-manipulation ${
              loopMode === "crossfade"
                ? "border-primary bg-primary/10"
                : "border-border hover:border-primary/50"
            } disabled:opacity-50`}
          >
            <div className="flex items-center gap-3">
              <Sparkles className="w-5 h-5 text-primary" />
              <div>
                <p className="font-medium text-sm flex items-center gap-1">
                  Crossfade (Seamless)
                  {!isProUser && <span className="text-[11px]">🔒 Pro</span>}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  前後をクロスフェードさせて自然につなぐ。風景などに最適。出力は 480p 固定です。
                </p>
              </div>
            </div>
          </button>
        </div>
      </div>

      {/* クロスフェード時間（Crossfade モード時のみ表示） */}
      {loopMode === "crossfade" && (
        <div>
          <label className="block text-sm font-medium mb-2">
            クロスフェード時間: {crossfadeSeconds.toFixed(1)}秒
          </label>
          <input
            type="range"
            min="0.1"
            max="5.0"
            step="0.1"
            value={crossfadeSeconds}
            onChange={(e) => onCrossfadeChange(Number(e.target.value))}
            disabled={disabled}
            className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary touch-manipulation"
          />
        </div>
      )}

      {/* 出力解像度 */}
      <div>
        <label className="block text-sm font-medium mb-2">
          出力解像度 (Resolution)
        </label>
        <select
          value={resolution}
          onChange={(e) => onResolutionChange(e.target.value as Resolution)}
          disabled={disabled}
          className="w-full px-3 py-2.5 sm:py-2 min-h-[44px] sm:min-h-0 bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed touch-manipulation"
        >
          <option value="Original">Original (そのまま)</option>
          <option value="720p">720p (HD)</option>
          <option value="1080p">1080p (Full HD)</option>
        </select>
        <p className="mt-1.5 text-xs text-muted-foreground">
          {loopMode === "crossfade"
            ? "Crossfade モードでは出力解像度は 480p 固定です（メモリ対策）。"
            : "高解像度の動画はサーバー制限のため、指定した解像度に制限して出力されます。"}
        </p>
      </div>

      {/* 再生速度 */}
      <div>
        <label className="block text-sm font-medium mb-2">
          再生速度 (Playback Speed)
        </label>
        <select
          value={playbackSpeed}
          onChange={(e) => onPlaybackSpeedChange(Number(e.target.value) as PlaybackSpeed)}
          disabled={disabled}
          className="w-full px-3 py-2.5 sm:py-2 min-h-[44px] sm:min-h-0 bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed touch-manipulation"
        >
          <option value={0.5}>0.5倍速（スロー）</option>
          <option value={1}>1倍速（通常）</option>
          <option value={2}>2倍速</option>
        </select>
        <p className="mt-1.5 text-xs text-muted-foreground">
          出力動画の再生速度を変更します。0.5倍速は尺が2倍になり、メモリ消費が増えます。
        </p>
      </div>

      {/* 静止（ポーズ）時間（Simple と Ping-Pong モード時のみ表示） */}
      {(loopMode === "simple" || loopMode === "pingpong") && (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Start Pause (秒): 動き出しの溜め
            </label>
            <div className="flex flex-col sm:flex-row gap-2 sm:gap-4 sm:items-center">
              <input
                type="range"
                min="0"
                max="10"
                step="0.1"
                value={startPauseSeconds}
                onChange={(e) => onStartPauseChange(Number(e.target.value))}
                disabled={disabled}
                className="w-full sm:flex-1 h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary touch-manipulation"
              />
              <div className="flex items-center gap-2 shrink-0">
                <input
                  type="number"
                  min="0"
                  max="10"
                  step="0.1"
                  value={startPauseSeconds}
                  onChange={(e) => onStartPauseChange(Number(e.target.value))}
                  disabled={disabled}
                  className="w-20 px-2 py-1.5 sm:py-1 bg-secondary border border-border rounded text-sm min-h-[44px] sm:min-h-0"
                />
                <span className="text-xs text-muted-foreground">秒</span>
              </div>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              End Pause (秒): 動き終わりの余韻
            </label>
            <div className="flex flex-col sm:flex-row gap-2 sm:gap-4 sm:items-center">
              <input
                type="range"
                min="0"
                max="10"
                step="0.1"
                value={endPauseSeconds}
                onChange={(e) => onEndPauseChange(Number(e.target.value))}
                disabled={disabled}
                className="w-full sm:flex-1 h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary touch-manipulation"
              />
              <div className="flex items-center gap-2 shrink-0">
                <input
                  type="number"
                  min="0"
                  max="10"
                  step="0.1"
                  value={endPauseSeconds}
                  onChange={(e) => onEndPauseChange(Number(e.target.value))}
                  disabled={disabled}
                  className="w-20 px-2 py-1.5 sm:py-1 bg-secondary border border-border rounded text-sm min-h-[44px] sm:min-h-0"
                />
                <span className="text-xs text-muted-foreground">秒</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
