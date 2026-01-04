FROM node:20-slim AS ui-builder

WORKDIR /app/ops_ui/ui-src
COPY app/ops_ui/ui-src/package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY app/ops_ui/ui-src ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

# 依存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリ
COPY app ./app
COPY --from=ui-builder /app/ops_ui/static/ui/dist ./app/ops_ui/static/ui/dist

ENV PYTHONUNBUFFERED=1

# Cloud RunはPORT環境変数が渡される
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
