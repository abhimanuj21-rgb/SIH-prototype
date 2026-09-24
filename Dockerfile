# One container = the whole platform (website + API) on a single port.
#   docker build -t ndp . && docker run -p 8000:8000 ndp   ->  http://localhost:8000

# 1. build the React website
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2. the FastAPI backend, which also serves the built website
FROM python:3.12-slim
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY --from=web /web/dist /app/frontend/dist
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
