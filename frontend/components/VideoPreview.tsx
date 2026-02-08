"use client";

import { Download, Loader2 } from "lucide-react";

interface VideoPreviewProps {
  videoUrl: string | null;
  onDownload: () => void;
  isProcessing: boolean;
}

export default function VideoPreview({
  videoUrl,
  onDownload,
  isProcessing,
}: VideoPreviewProps) {
  if (isProcessing) {
    return (
      <div className="aspect-video bg-secondary rounded-lg flex items-center justify-center border border-border">
        <div className="text-center">
          <Loader2 className="w-12 h-12 mx-auto mb-4 text-primary animate-spin" />
          <p className="text-sm text-muted-foreground">動画を処理中...</p>
        </div>
      </div>
    );
  }

  if (!videoUrl) {
    return (
      <div className="aspect-video bg-secondary rounded-lg flex items-center justify-center border border-border">
        <div className="text-center">
          <p className="text-sm text-muted-foreground">
            処理された動画がここに表示されます
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="aspect-video bg-black rounded-lg overflow-hidden border border-border">
        <video
          src={videoUrl}
          controls
          className="w-full h-full object-contain"
          preload="metadata"
        >
          お使いのブラウザは動画タグをサポートしていません。
        </video>
      </div>
      <button
        onClick={onDownload}
        className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-semibold py-3 px-6 rounded-lg transition-colors flex items-center justify-center gap-2"
      >
        <Download className="w-5 h-5" />
        動画をダウンロード
      </button>
    </div>
  );
}
