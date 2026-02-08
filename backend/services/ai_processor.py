from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class AIProcessor:
    """将来的な AI ベース映像処理 (inpainting / outpainting など) のためのプレースホルダークラス。

    現時点では未実装だが、VideoProcessor から呼び出せるようにここで責務を分離しておく。
    """

    model_name: str | None = None

    def enhance_background(self, input_path: Path, output_path: Path) -> None:
        """背景強調やノイズ除去などの AI 処理を行う予定のメソッド。"""
        raise NotImplementedError("AI-based processing is not implemented yet.")
