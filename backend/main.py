import datetime
import os
import urllib.request
import shutil

import google.auth
from google.auth.transport import requests as google_auth_requests
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google.cloud import storage
import logging
import uvicorn

from services.ffmpeg_processor import VideoProcessor, LoopMode

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)

app = FastAPI(title="VTuber Background Loop Generator")

# ---------------------------------------------------
# 設定：バケット名はプロジェクトIDから自動生成したものを指定
# ---------------------------------------------------
BUCKET_NAME = "loop-generator-487117-videos"

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

video_processor = VideoProcessor(temp_dir=TEMP_DIR)


def get_current_service_account_email():
    """Cloud Runのメタデータサーバーから自分のSAメールアドレスを取得する"""
    try:
        url = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email"
        req = urllib.request.Request(url)
        req.add_header("Metadata-Flavor", "Google")
        with urllib.request.urlopen(req) as response:
            return response.read().decode("utf-8").strip()
    except Exception:
        # ローカル開発などで取得できない場合はNoneを返す
        return None


def upload_to_gcs_and_get_url(file_path: str, destination_blob_name: str):
    """
    ファイルをGCSにアップロードし、IAM signBlob APIを使って署名付きURLを発行する。
    Cloud Run / Compute Engine では秘密鍵が無いため、access_token と service_account_email を
    渡して IAM API 経由で署名する。サービスアカウントに roles/iam.serviceAccountTokenCreator
    の付与が必要。
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(destination_blob_name)

        # 1. アップロード
        print(f"Uploading {file_path} to gs://{BUCKET_NAME}/{destination_blob_name}...")
        blob.upload_from_filename(file_path)

        # 2. 資格情報を取得し、refresh して access_token を取得（必須）
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        credentials.refresh(google_auth_requests.Request())

        # 3. サービスアカウントのメールアドレスを取得
        sa_email = None
        if hasattr(credentials, "service_account_email") and credentials.service_account_email:
            sa_email = credentials.service_account_email
        if not sa_email:
            sa_email = get_current_service_account_email()
        if not sa_email:
            sa_email = os.environ.get("SERVICE_ACCOUNT_EMAIL")

        print(f"Signing URL using account: {sa_email}")

        if not sa_email:
            raise Exception("Service Account Email could not be determined. Cannot sign URL.")

        if not credentials.token:
            raise Exception(
                "Access token is not available. "
                "Ensure IAM Service Account Credentials API is enabled and "
                "the service account has roles/iam.serviceAccountTokenCreator on itself."
            )

        # 4. 署名付きURLの発行（IAM signBlob API を使用）
        # ブラウザに「再生ではなくダウンロードさせたい」ことを伝えるため、
        # response_disposition で Content-Disposition ヘッダを指定する
        download_filename = os.path.basename(destination_blob_name) or "download.mp4"
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="GET",
            service_account_email=sa_email,
            access_token=credentials.token,  # これがないと秘密鍵エラーになる
            response_disposition=f'attachment; filename="{download_filename}"',
        )
        print(f"Generated signed URL: {url}")
        return url
    except Exception as e:
        print(f"GCS Error: {e}")
        import traceback
        traceback.print_exc()
        raise e


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
    """アップロードされた動画を指定のモードでループ処理し、GCSにアップロードしてURLを返す。"""
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
        if input_path.exists():
            try:
                input_path.unlink()
            except OSError:
                pass
        return JSONResponse(
            status_code=500,
            content={"detail": f"Video processing failed: {e}"},
        )

    try:
        # GCSへアップロード
        output_filename = output_path.name
        download_url = upload_to_gcs_and_get_url(
            str(output_path), f"outputs/{output_filename}"
        )

        # 後始末（一時ファイルの削除）
        if input_path.exists():
            input_path.unlink()
        if output_path.exists():
            output_path.unlink()

        return JSONResponse(content={
            "status": "success",
            "download_url": download_url,
            "filename": output_filename,
        })
    except Exception as e:
        logger.exception("GCS upload or cleanup failed")
        if input_path.exists():
            try:
                input_path.unlink()
            except OSError:
                pass
        if output_path.exists():
            try:
                output_path.unlink()
            except OSError:
                pass
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)},
        )


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
