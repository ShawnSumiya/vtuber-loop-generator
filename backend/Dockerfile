# Python 3.9の軽量版を使用
FROM python:3.11-slim

# FFmpegをインストール (これが重要)
RUN apt-get update && apt-get install -y ffmpeg

# 作業ディレクトリを設定
WORKDIR /app

# 依存ファイルをコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ソースコードをコピー
COPY . .

# ポート8000を開放
EXPOSE 8000

# サーバー起動コマンド
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
