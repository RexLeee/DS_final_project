# Real-time Bidding & Flash Sale System

即時競標與限時搶購系統 - 分散式系統與雲端應用開發實務期末專案

## 系統架構

- **後端**: Python 3.11 + FastAPI
- **前端**: React 18 + TypeScript + Vite + Tailwind CSS
- **資料庫**: PostgreSQL 15
- **快取**: Redis 7
- **容器編排**: Kubernetes (GKE)

## 專案結構

```
flash-sale-system/
├── backend/               # 後端服務 (FastAPI)
│   ├── src/app/           # 源碼目錄
│   │   ├── api/           # API 路由
│   │   ├── core/          # 核心配置
│   │   ├── models/        # 資料庫模型
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── services/      # 業務邏輯服務
│   │   └── main.py        # 應用程式入口
│   ├── tests/             # 單元測試
│   ├── alembic/           # 資料庫遷移
│   ├── scripts/           # 腳本工具
│   └── pyproject.toml     # Python 依賴配置
├── frontend/              # 前端應用 (React)
│   ├── src/
│   │   ├── api/           # API 客戶端
│   │   ├── components/    # React 元件
│   │   ├── contexts/      # React Context
│   │   ├── hooks/         # 自訂 Hooks
│   │   ├── pages/         # 頁面元件
│   │   └── types/         # TypeScript 型別
│   └── package.json       # Node.js 依賴配置
├── k8s/                   # Kubernetes 配置
├── docs/                  # 文件
└── docker-compose.yml     # 本地開發環境
```

## 環境需求

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- UV (Python 套件管理工具)

## 快速開始

### 1. 安裝 UV (Python 套件管理工具)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. 資料庫設置

使用 Docker Compose 啟動 PostgreSQL 和 Redis：

```bash
# 在專案根目錄執行
docker-compose up -d
```

這會啟動以下服務：
- **PostgreSQL**: `localhost:5432`
  - 使用者: `postgres`
  - 密碼: `postgres`
  - 資料庫: `flash_sale`
- **Redis**: `localhost:6379`

確認服務是否正常運行：

```bash
docker-compose ps
```

### 3. 後端設置與啟動

```bash
# 進入 backend 目錄
cd backend

# 複製環境變數設定檔
cp .env.example .env

# 安裝 Python 依賴
uv sync

# 執行資料庫遷移
uv run alembic upgrade head

# 啟動後端服務（開發模式）
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

後端服務會在 `http://localhost:8000` 運行。

### 4. 前端設置與啟動

```bash
# 進入 frontend 目錄
cd frontend

# 安裝 Node.js 依賴
npm install

# 啟動前端開發伺服器
npm run dev
```

前端服務會在 `http://localhost:3000` 運行。

## 環境變數配置

### 後端 (.env)

| 變數名稱 | 說明 | 預設值 |
|---------|------|--------|
| `DATABASE_URL` | PostgreSQL 連線字串 | `postgresql+asyncpg://postgres:postgres@localhost:5432/flash_sale` |
| `REDIS_URL` | Redis 連線字串 | `redis://localhost:6379/0` |
| `JWT_SECRET_KEY` | JWT 簽名密鑰 | `your-secret-key-change-in-production` |
| `JWT_ALGORITHM` | JWT 演算法 | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token 過期時間（分鐘） | `60` |
| `DEBUG` | 除錯模式 | `true` |
| `CORS_ORIGINS` | 允許的 CORS 來源 | `["http://localhost:3000","http://localhost:5173"]` |

## API 文檔

啟動後端服務後，可訪問以下 API 文檔：
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **健康檢查**: http://localhost:8000/health

## 開發指令

### 後端

```bash
cd backend

# 安裝依賴（含開發依賴）
uv sync --all-extras

# 執行測試
uv run pytest

# 執行測試（含覆蓋率報告）
uv run pytest --cov=app --cov-report=term-missing

# 建立新的資料庫遷移
uv run alembic revision --autogenerate -m "描述"

# 執行資料庫遷移
uv run alembic upgrade head

# 回滾資料庫遷移
uv run alembic downgrade -1
```

### 前端

```bash
cd frontend

# 啟動開發伺服器
npm run dev

# 建置生產版本
npm run build

# 預覽生產版本
npm run preview

# 程式碼檢查
npm run lint
```

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

## 常見問題

### Q: 資料庫連線失敗？

確認 Docker 容器正在運行：
```bash
docker-compose ps
docker-compose logs postgres
```

### Q: 如何重置資料庫？

```bash
# 刪除並重建資料庫容器
docker-compose down -v
docker-compose up -d

# 重新執行遷移
cd backend
uv run alembic upgrade head
```

### Q: 前端無法連接後端 API？

1. 確認後端服務正在運行於 `http://localhost:8000`
2. 確認 `.env` 中的 `CORS_ORIGINS` 包含前端 URL

---

## GCP 雲端部署

### 部署架構

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                    Google Cloud Platform                 │
                    │                                                          │
┌──────────┐        │  ┌─────────────┐     ┌─────────────────────────────┐    │
│  Users   │◄──────►│  │   Ingress   │◄───►│     GKE Autopilot Cluster   │    │
└──────────┘        │  │ (Static IP) │     │  ┌─────────┐  ┌──────────┐  │    │
                    │  └─────────────┘     │  │ Backend │  │ Frontend │  │    │
                    │                      │  │  (2-10) │  │  (1-5)   │  │    │
                    │                      │  └────┬────┘  └──────────┘  │    │
                    │                      └───────┼──────────────────────┘    │
                    │                              │                           │
                    │         ┌────────────────────┼────────────────────┐      │
                    │         │                    │                    │      │
                    │         ▼                    ▼                    │      │
                    │  ┌─────────────┐     ┌─────────────┐              │      │
                    │  │  Cloud SQL  │     │ Memorystore │   VPC Network│      │
                    │  │ PostgreSQL  │     │    Redis    │              │      │
                    │  └─────────────┘     └─────────────┘              │      │
                    │                                                   │      │
                    └───────────────────────────────────────────────────┴──────┘
```

### 部署需求

- Google Cloud 帳號並啟用計費
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) 已安裝
- Docker Desktop 已安裝並運行
- GKE Auth Plugin

```bash
# 安裝 gcloud CLI (macOS)
brew install google-cloud-sdk

# 登入 GCP
gcloud auth login

# 安裝 GKE 認證插件
gcloud components install gke-gcloud-auth-plugin
export USE_GKE_GCLOUD_AUTH_PLUGIN=True
```

### 部署檔案結構

```
├── scripts/
│   └── deploy-gcp.sh      # 自動化部署腳本
├── k8s/
│   ├── namespace.yaml     # Kubernetes 命名空間
│   ├── configmap.yaml     # 應用配置
│   ├── secrets.yaml       # 敏感資訊 (部署時自動生成)
│   ├── backend-deployment.yaml
│   ├── frontend-deployment.yaml
│   ├── services.yaml      # ClusterIP 服務
│   ├── ingress.yaml       # GCE Ingress + Static IP
│   └── hpa.yaml           # 水平自動擴展
├── backend/
│   └── Dockerfile         # 後端容器映像檔
└── frontend/
    ├── Dockerfile         # 前端容器映像檔
    └── nginx.conf         # Nginx 配置
```

### 一鍵部署

```bash
# 1. 設定專案 ID (修改為你的專案)
#    編輯 scripts/deploy-gcp.sh 第 11 行的 PROJECT_ID

# 2. 執行部署腳本
./scripts/deploy-gcp.sh

# 3. 選擇 A (Run ALL steps)
#    - Step 4: 輸入資料庫密碼
#    - Step 9: 再次輸入資料庫密碼
```

部署過程約需 15-20 分鐘，完成後會顯示應用 URL。

### 部署步驟說明

| 步驟 | 說明 | 預估時間 |
|------|------|---------|
| 1 | 設定專案並啟用 APIs | 1 分鐘 |
| 2 | 建立 Artifact Registry | 30 秒 |
| 3 | 建立 VPC 網路 | 1 分鐘 |
| 4 | 建立 Cloud SQL (PostgreSQL) | 5 分鐘 |
| 5 | 建立 Memorystore (Redis) | 3 分鐘 |
| 6 | 建立 GKE Autopilot 叢集 | 5 分鐘 |
| 7 | 預留靜態 IP | 10 秒 |
| 8 | 建構並推送 Docker 映像檔 | 2 分鐘 |
| 9 | 部署至 GKE | 2 分鐘 |
| 10 | 執行資料庫遷移 | 30 秒 |
| 11 | 驗證部署 | 10 秒 |

### 程式碼更新後重新部署

```bash
# 後端程式碼更新
./scripts/deploy-gcp.sh   # 選擇 8
kubectl rollout restart deployment/backend -n flash-sale

# 前端程式碼更新
./scripts/deploy-gcp.sh   # 選擇 8
kubectl rollout restart deployment/frontend -n flash-sale

# 或使用一行指令
docker buildx build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/YOUR_PROJECT_ID/flash-sale-repo/backend:latest \
  --push ./backend && \
kubectl rollout restart deployment/backend -n flash-sale
```

### 常用 kubectl 指令

```bash
# 查看 Pod 狀態
kubectl get pods -n flash-sale

# 查看 Pod 日誌
kubectl logs -n flash-sale -l app=backend --tail=100

# 進入 Pod 終端
kubectl exec -it -n flash-sale deployment/backend -- /bin/bash

# 查看 HPA 狀態
kubectl get hpa -n flash-sale

# 手動擴展
kubectl scale deployment/backend -n flash-sale --replicas=5
```

### 刪除所有資源

```bash
./scripts/deploy-gcp.sh
# 選擇 D (DELETE all resources)
# 輸入 yes 確認
```

這會刪除：GKE 叢集、Cloud SQL、Memorystore、Artifact Registry、Static IP、VPC

### GCP 資源配置 (Demo 優化版)

| 資源 | 規格 | 預估月費 |
|------|------|---------|
| GKE Autopilot | 按需計費 | ~$50 |
| Cloud SQL | db-g1-small (1 vCPU, 1.7GB) | ~$25 |
| Memorystore Redis | 1GB Basic | ~$15 |
| Static IP | 1 個 | ~$3 |
| **總計** | | **~$93/月** |

> 注意：實際費用可能因使用量和地區而異。Demo 用途建議使用完後刪除資源以節省費用。

### 生產環境建議

如需生產環境部署，建議調整以下配置：

```bash
# scripts/deploy-gcp.sh

# Cloud SQL - 升級為高可用
--tier=db-custom-2-4096
--availability-type=REGIONAL

# Memorystore - 升級為標準層
--size=5
--tier=standard
```

```yaml
# k8s/backend-deployment.yaml
resources:
  requests:
    cpu: "500m"
    memory: "512Mi"
  limits:
    cpu: "1000m"
    memory: "1Gi"

# k8s/hpa.yaml
minReplicas: 3
maxReplicas: 20
```

## 文件

- [技術規格文件](docs/technical_spec.md)
- [實作任務清單](docs/task.md)
