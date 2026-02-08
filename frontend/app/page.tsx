"use client";

import { useState, useCallback } from "react";
import { Upload, Play, Download, Loader2, Video, Settings } from "lucide-react";
import VideoUploadArea from "@/components/VideoUploadArea";
import SettingsPanel from "@/components/SettingsPanel";
import VideoPreview from "@/components/VideoPreview";

type LoopMode = "simple" | "pingpong" | "crossfade";
type Resolution = "Original" | "720p" | "1080p" | "4K";

export default function Home() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [durationSeconds, setDurationSeconds] = useState<number>(60);
  const [loopMode, setLoopMode] = useState<LoopMode>("simple");
  const [crossfadeSeconds, setCrossfadeSeconds] = useState<number>(1.0);
  const [startPauseSeconds, setStartPauseSeconds] = useState<number>(0);
  const [endPauseSeconds, setEndPauseSeconds] = useState<number>(0);
  const [resolution, setResolution] = useState<Resolution>("Original");
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [processedVideoUrl, setProcessedVideoUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = useCallback((file: File) => {
    setSelectedFile(file);
    setProcessedVideoUrl(null);
    setError(null);
  }, []);

  const handleFileRemove = useCallback(() => {
    setSelectedFile(null);
    setProcessedVideoUrl(null);
    setError(null);
  }, []);

  const handleProcess = useCallback(async () => {
    if (!selectedFile) {
      setError("動画ファイルを選択してください");
      return;
    }

    setIsProcessing(true);
    setError(null);
    setProcessedVideoUrl(null);

    // 長時間応答がない場合に「処理中」で永久に止まらないようタイムアウト（10分）
    const timeoutMs = 10 * 60 * 1000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("duration_seconds", durationSeconds.toString());
      formData.append("mode", loopMode);
      formData.append("crossfade_seconds", crossfadeSeconds.toString());
      formData.append("start_pause_seconds", startPauseSeconds.toString());
      formData.append("end_pause_seconds", endPauseSeconds.toString());
      formData.append("resolution", resolution);

      const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${API_BASE_URL}/process-video`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Unknown error" }));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      setProcessedVideoUrl(url);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        setError(
          "応答がタイムアウトしました（10分）。動画が長い・重い場合は時間がかかります。バックエンドのターミナルで「処理完了」が出ていれば、もう一度実行してみてください。処理中にバックエンドのファイルを保存するとサーバーが再起動し、接続が切れることがあります。"
        );
      } else {
        setError(err instanceof Error ? err.message : "動画処理中にエラーが発生しました");
      }
    } finally {
      clearTimeout(timeoutId);
      setIsProcessing(false);
    }
  }, [selectedFile, durationSeconds, loopMode, crossfadeSeconds, startPauseSeconds, endPauseSeconds, resolution]);

  const handleDownload = useCallback(() => {
    if (!processedVideoUrl || !selectedFile) return;

    const a = document.createElement("a");
    a.href = processedVideoUrl;
    a.download = `looped_${selectedFile.name}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }, [processedVideoUrl, selectedFile]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        {/* ヘッダー */}
        <header className="mb-8">
          <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-primary to-purple-500 bg-clip-text text-transparent">
            VTuber Background Loop Generator
          </h1>
          <p className="text-muted-foreground">
            短い動画クリップを指定した長さまで自然にループさせた背景動画を自動生成
          </p>
        </header>

        {/* メインコンテンツ */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 左側: アップロード & 設定 */}
          <div className="space-y-6">
            {/* 動画アップロードエリア */}
            <div className="bg-secondary/50 rounded-lg p-6 border border-border">
              <div className="flex items-center gap-2 mb-4">
                <Upload className="w-5 h-5 text-primary" />
                <h2 className="text-xl font-semibold">動画アップロード</h2>
              </div>
              <VideoUploadArea
                onFileSelect={handleFileSelect}
                onRemove={handleFileRemove}
                selectedFile={selectedFile}
              />
            </div>

            {/* 設定パネル */}
            <div className="bg-secondary/50 rounded-lg p-6 border border-border">
              <div className="flex items-center gap-2 mb-4">
                <Settings className="w-5 h-5 text-primary" />
                <h2 className="text-xl font-semibold">設定</h2>
              </div>
              <SettingsPanel
                durationSeconds={durationSeconds}
                onDurationChange={setDurationSeconds}
                loopMode={loopMode}
                onLoopModeChange={setLoopMode}
                crossfadeSeconds={crossfadeSeconds}
                onCrossfadeChange={setCrossfadeSeconds}
                startPauseSeconds={startPauseSeconds}
                onStartPauseChange={setStartPauseSeconds}
                endPauseSeconds={endPauseSeconds}
                onEndPauseChange={setEndPauseSeconds}
                resolution={resolution}
                onResolutionChange={setResolution}
                disabled={isProcessing || !selectedFile}
              />
            </div>

            {/* 処理実行ボタン */}
            <button
              onClick={handleProcess}
              disabled={isProcessing || !selectedFile}
              className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-semibold py-3 px-6 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isProcessing ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  処理中...
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  動画を処理する
                </>
              )}
            </button>

            {/* エラーメッセージ */}
            {error && (
              <div className="bg-red-500/20 border border-red-500/50 text-red-400 rounded-lg p-4">
                <p className="font-medium">エラー</p>
                <p className="text-sm mt-1">{error}</p>
              </div>
            )}
          </div>

          {/* 右側: プレビュー & ダウンロード */}
          <div className="space-y-6">
            <div className="bg-secondary/50 rounded-lg p-6 border border-border">
              <div className="flex items-center gap-2 mb-4">
                <Video className="w-5 h-5 text-primary" />
                <h2 className="text-xl font-semibold">プレビュー & ダウンロード</h2>
              </div>
              <VideoPreview
                videoUrl={processedVideoUrl}
                onDownload={handleDownload}
                isProcessing={isProcessing}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
