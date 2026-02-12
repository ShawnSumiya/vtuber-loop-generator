# ベースイメージ：軽量なPython 3.9
FROM python:3.10-slim

# システムの依存関係（FFmpeg）をインストール
# GCR上で動画処理をするために必須です
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリの設定
WORKDIR /app

# 依存関係ファイルのコピーとインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードのコピー
COPY . .

# Cloud Run はポート番号を環境変数 PORT で渡してくるので、それを受け取る設定
# デフォルトは 8080
ENV PORT=8080

# 起動コマンド (uvicornを使用)
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}
