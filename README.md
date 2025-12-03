# Real-time Bidding & Flash Sale System

即時競標與限時搶購系統 - 分散式系統與雲端應用開發實務期末專案

## 系統架構

- **後端**: Python 3.11 + FastAPI
- **前端**: React 18 + TypeScript
- **資料庫**: PostgreSQL 15
- **快取**: Redis 7
- **容器編排**: Kubernetes (GKE)

## 專案結構

```
flash-sale-system/
├── backend/           # 後端服務 (FastAPI)
│   ├── src/app/       # 源碼目錄
│   ├── tests/         # 測試
│   ├── alembic/       # 資料庫遷移
│   └── scripts/       # 腳本工具
├── frontend/          # 前端應用 (React)
├── k6-tests/          # 壓力測試腳本
├── k8s/               # Kubernetes 配置
├── docs/              # 文件
└── docker-compose.yml # 本地開發環境
```

## 快速開始

### 環境需求

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- UV (Python 套件管理工具)

### 安裝 UV

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 啟動本地開發環境

```bash
# 啟動 PostgreSQL 和 Redis
docker-compose up -d

# 進入 backend 目錄
cd backend

# 安裝依賴
uv sync

# 執行資料庫遷移
uv run alembic upgrade head

# 啟動後端服務
uv run uvicorn app.main:app --reload
```

### API 文檔

啟動後端服務後，訪問:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 核心功能

1. **會員系統**: 註冊、登入、權重管理
2. **商品管理**: 商品上架、活動設定
3. **即時競標**: 出價、積分計算、即時排名
4. **訂單結算**: 活動結束自動結算、防超賣機制
5. **即時推播**: WebSocket 排名即時更新

## 技術特點

- **高並發處理**: Redis Sorted Set 即時排名
- **防超賣機制**: 四層防護 (分散式鎖 + 原子扣減 + 行級鎖 + 樂觀鎖)
- **自動擴展**: Kubernetes HPA 基於 CPU 使用率
- **即時推播**: WebSocket 排名更新

## 文件

- [技術規格文件](docs/technical_spec.md)
- [實作任務清單](docs/task.md)
