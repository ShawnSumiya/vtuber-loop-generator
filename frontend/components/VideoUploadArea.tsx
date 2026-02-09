"use client";

import { useCallback, useState } from "react";
import { Upload, X, FileVideo } from "lucide-react";

interface VideoUploadAreaProps {
  onFileSelect: (file: File) => void;
  onRemove?: () => void;
  selectedFile: File | null;
}

export default function VideoUploadArea({
  onFileSelect,
  onRemove,
  selectedFile,
}: VideoUploadAreaProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);

      const files = Array.from(e.dataTransfer.files);
      const videoFile = files.find(
        (file) => file.type.startsWith("video/")
      );

      if (videoFile) {
        onFileSelect(videoFile);
      }
    },
    [onFileSelect]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        const file = files[0];
        if (file.type.startsWith("video/")) {
          onFileSelect(file);
        }
      }
    },
    [onFileSelect]
  );

  const handleRemove = useCallback(() => {
    if (onRemove) {
      onRemove();
    }
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    if (input) {
      input.value = "";
    }
  }, [onRemove]);

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + " " + sizes[i];
  };

  return (
    <div>
      {selectedFile ? (
        <div className="border-2 border-primary/50 rounded-lg p-3 sm:p-4 bg-primary/10">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-3 min-w-0 flex-1">
              <FileVideo className="w-8 h-8 text-primary shrink-0" />
              <div className="min-w-0">
                <p className="font-medium text-sm truncate" title={selectedFile.name}>
                  {selectedFile.name}
                </p>
                <p className="text-xs text-muted-foreground">
                  {formatFileSize(selectedFile.size)}
                </p>
              </div>
            </div>
            <button
              onClick={handleRemove}
              className="p-2 sm:p-1 min-w-[44px] min-h-[44px] sm:min-w-0 sm:min-h-0 flex items-center justify-center hover:bg-secondary rounded transition-colors touch-manipulation shrink-0"
              aria-label="ファイルを削除"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      ) : (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-lg p-6 sm:p-8 text-center transition-colors ${
            isDragging
              ? "border-primary bg-primary/10"
              : "border-border hover:border-primary/50"
          }`}
        >
          <Upload className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
          <p className="text-sm font-medium mb-2">
            動画ファイルをドラッグ＆ドロップ
          </p>
          <p className="text-xs text-muted-foreground mb-4">
            または
          </p>
          <label className="inline-block">
            <span className="inline-flex items-center justify-center min-h-[44px] bg-primary hover:bg-primary/90 text-primary-foreground px-4 py-2 rounded-lg cursor-pointer text-sm font-medium transition-colors touch-manipulation">
              ファイルを選択
            </span>
            <input
              type="file"
              accept="video/*"
              onChange={handleFileInput}
              className="hidden"
            />
          </label>
        </div>
      )}
    </div>
  );
}
