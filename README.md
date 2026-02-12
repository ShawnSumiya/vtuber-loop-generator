# VTuber Background Loop Generator

VTuber向けの背景動画自動ループ生成アプリケーション。短い動画クリップ（数秒〜十数秒）をアップロードし、指定した長さ（例：1時間、30秒など）まで自然にループさせた動画ファイルを自動生成します。

## 技術スタック

- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, Lucide React
- **Backend**: Python (FastAPI)
- **Video Processing**: FFmpeg
- **Infra**: Google Cloud Run, Cloud Storage (GCS)

## 機能

- **動画アップロード**: ドラッグ＆ドロップ対応
- **3つのループモード**:
  - **Simple Loop**: 単純な繰り返し。最もシンプルで高速
  - **Ping-Pong (Mirror)**: 再生→逆再生→再生... を繰り返す（継ぎ目なし）
  - **Crossfade (Seamless)**: 動画の前後をクロスフェードさせて自然につなぐ。風景などに最適。高解像度入力時はサーバー保護のため内部的にダウンスケールされる場合があります。
- **高度な設定オプション**:
  - **目標の長さ**: 5秒〜1時間（3600秒）まで指定可能
  - **クロスフェード時間**: Crossfadeモード時に、前後のクロスフェード時間を調整（0.1〜5.0秒）。高解像度入力時は内部的にリサイズされる場合があります。
  - **Start Pause**: Simple/Ping-Pongモード時に、動き出しの溜め時間を追加（0〜10秒）
  - **End Pause**: Simple/Ping-Pongモード時に、動き終わりの余韻時間を追加（0〜10秒）
  - **出力解像度**: Original / 720p / 1080p / 4K から選択可能（一部モード・高解像度入力では 720p などに自動制限されます）
  - **再生速度**: 0.5x / 1x / 2x を選択可能
- **プレビュー & ダウンロード**: 処理完了後、生成された動画をプレビューし、ダウンロード可能

## セットアップ

### 前提条件

- Node.js 18以上
- Python 3.9以上
- FFmpeg がインストールされていること

### バックエンドのセットアップ

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### フロントエンドのセットアップ

```bash
cd frontend
npm install
```

## 実行方法

### バックエンドの起動

```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
python main.py
```

バックエンドは `http://localhost:8080`（`PORT` 未指定時のデフォルト）で起動します。

### フロントエンドの起動

```bash
cd frontend
npm run dev
```

フロントエンドは `http://localhost:3000` で起動します。

ローカル開発でバックエンドに接続する場合は、フロントエンド側で `NEXT_PUBLIC_API_URL` を設定してください（例: `http://localhost:8080`）。  
未指定の場合は、本番用の Cloud Run エンドポイント `https://api-backend-880889120755.asia-northeast1.run.app` に接続します。

## プロジェクト構成

```
VTuber-Background-Loop-Generator/
├── frontend/                    # Next.js フロントエンド
│   ├── app/                    # App Router ページ
│   │   ├── page.tsx           # メインページ
│   │   ├── layout.tsx          # レイアウト
│   │   └── globals.css         # グローバルスタイル
│   ├── components/              # React コンポーネント
│   │   ├── VideoUploadArea.tsx # 動画アップロードエリア
│   │   ├── SettingsPanel.tsx   # 設定パネル
│   │   └── VideoPreview.tsx    # プレビューコンポーネント
│   ├── package.json
│   └── ...
├── backend/                     # FastAPI バックエンド
│   ├── services/                # ビジネスロジック
│   │   ├── ffmpeg_processor.py # FFmpeg処理ロジック（3つのループモード実装）
│   │   └── ai_processor.py     # AI処理用プレースホルダー（将来の拡張用）
│   ├── temp/                    # 一時ファイル保存用
│   ├── main.py                  # FastAPIアプリケーション
│   └── requirements.txt         # Python依存関係
└── README.md
```

## API エンドポイント

### POST `/process-video`
動画をアップロードしてループ処理を実行します。

**リクエストパラメータ:**
- `file`: 動画ファイル（multipart/form-data）
- `duration_seconds`: 目標の長さ（秒、整数）
- `mode`: ループモード（`simple`, `pingpong`, `crossfade`）。`crossfade` のときは出力解像度は高解像度入力時に自動的にダウンスケールされる場合があります。
- `crossfade_seconds`: クロスフェード時間（秒、浮動小数点数、デフォルト: 1.0）
- `start_pause_seconds`: 開始時のポーズ時間（秒、浮動小数点数、デフォルト: 0.0）
- `end_pause_seconds`: 終了時のポーズ時間（秒、浮動小数点数、デフォルト: 0.0）
- `resolution`: 出力解像度（`Original`, `720p`, `1080p`, `4K`）。不正値や未指定時は `Original` として扱われますが、高解像度入力時は内部的に 720p などに制限される場合があります。
- `speed`: 再生速度（`0.5`, `1.0`, `2.0`）。不正値や未指定時は `1.0` として扱われます。

**レスポンス:**
- 成功時: JSON  
  - `status`: `"success"`
  - `download_url`: 署名付きURL（Cloud Storage 上の動画への一時的なダウンロードURL・有効期限約15分）
  - `filename`: GCS 上のファイル名
- エラー時: JSON形式のエラーメッセージ

### GET `/health`
ヘルスチェックエンドポイント。

**レスポンス:**
```json
{"status": "ok"}
```

## Cloud Run デプロイ時の IAM 設定

署名付きURLを発行するには、Cloud Run のサービスアカウントに **Service Account Token Creator** ロールを付与する必要があります（IAM signBlob API を使用するため）。

1. **IAM Service Account Credentials API** を有効にする  
   [API を有効にする](https://console.cloud.google.com/apis/library/iamcredentials.googleapis.com)

2. サービスアカウントに自身への Token Creator ロールを付与する：
   ```bash
   # 使用しているサービスアカウントのメールアドレスを指定
   SA_EMAIL="YOUR-SERVICE-ACCOUNT@YOUR-PROJECT.iam.gserviceaccount.com"

   gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
     --member="serviceAccount:$SA_EMAIL" \
     --role="roles/iam.serviceAccountTokenCreator"
   ```

Cloud Run のデフォルトサービスアカウント（`PROJECT_NUMBER-compute@developer.gserviceaccount.com`）を使う場合、上記の `SA_EMAIL` をそれに置き換えて実行してください。

## 将来の拡張

- AI ベースの映像生成（Inpainting/Outpainting）への対応
- Replicate API などの統合
- より高度な動画エフェクト機能