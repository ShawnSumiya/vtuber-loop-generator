from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from uuid import uuid4
import shutil
import os

from services.ffmpeg_processor import VideoProcessor, LoopMode

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)

app = FastAPI(title="VTuber Background Loop Generator")

# --- CORS設定 ---
# 許可するオリジンのリスト
origins = [
    "http://localhost:3000",                      # ローカル開発用
    "https://vtuber-loop-generator.vercel.app",   # Vercelの本番URL
    "*",                                          # ★緊急策: すべて許可（どうしても動かない場合）
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        # 許可するリストをセット
    allow_credentials=True,
    allow_methods=["*"],          # 全てのメソッド(GET, POSTなど)を許可
    allow_headers=["*"],          # 全てのヘッダーを許可
)

video_processor = VideoProcessor(temp_dir=TEMP_DIR)


@app.post("/process-video")
async def process_video(
    file: UploadFile = File(...),
    duration_seconds: int = Form(...),
    mode: str = Form("simple"),
    crossfade_seconds: float = Form(1.0),
    start_pause_seconds: float = Form(0.0),
    end_pause_seconds: float = Form(0.0),
    resolution: str = Form(default="Original"),
    speed: float = Form(1.0),
):
    """アップロードされた動画を指定のモードでループ処理する。"""
    # 解像度が未送信・空・不正値の場合は Original として扱う（解像度を変えても止まらない）
    r = (resolution or "").strip() or "Original"
    resolution = r if r in ("Original", "720p", "1080p", "4K") else "Original"

    if duration_seconds <= 0:
        return JSONResponse(
            status_code=400,
            content={"detail": "duration_seconds must be positive"},
        )

    try:
        loop_mode = LoopMode(mode)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"detail": f"Invalid mode: {mode}"},
        )

    # 一時ファイルに保存
    input_suffix = Path(file.filename or "input.mp4").suffix or ".mp4"
    input_path = TEMP_DIR / f"input_{uuid4().hex}{input_suffix}"

    with input_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        output_path = await video_processor.process(
            input_path=input_path,
            target_duration=duration_seconds,
            mode=loop_mode,
            crossfade_seconds=crossfade_seconds,
            start_pause_seconds=start_pause_seconds,
            end_pause_seconds=end_pause_seconds,
            target_resolution=resolution,
            speed=speed,
        )
    except Exception as e:
        # 失敗時も入力ファイルは削除
        if input_path.exists():
            try:
                input_path.unlink()
            except OSError:
                pass
        return JSONResponse(
            status_code=500,
            content={"detail": f"Video processing failed: {e}"},
        )

    # 入力ファイルは処理後削除
    if input_path.exists():
        try:
            input_path.unlink()
        except OSError:
            pass

    filename = f"looped_{file.filename or 'output.mp4'}"
    print(f"--- API: 処理完了、ファイル送信開始 ({output_path}) ---", flush=True)
    return FileResponse(
        path=output_path,
        media_type="video/mp4",
        filename=filename,
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
