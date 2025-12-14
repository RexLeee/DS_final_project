# 即時競標與限時搶購系統

分散式系統與雲端應用開發實務期末專案

---

## 目錄

1. [專案目標與需求](#1-專案目標與需求)
2. [系統與部署架構](#2-系統與部署架構)
3. [資料庫 Schema](#3-資料庫-schema)
4. [核心服務與資料流](#4-核心服務與資料流)
5. [API 設計](#5-api-設計)
6. [專案結構](#6-專案結構)
7. [技術棧總覽](#7-技術棧總覽)

---

## 1. 專案目標與需求

### 系統定位

專為高並發場景設計的即時競標系統，支援 1000+ 並發用戶，提供毫秒級出價處理與即時排名更新。

### 核心功能

| 功能     | 說明                                      |
| -------- | ----------------------------------------- |
| 即時競標 | 用戶對商品出價，系統即時計算排名          |
| 限時搶購 | 活動結束時，排名前 K 名用戶自動成為得標者 |
| 庫存保護 | Lua 腳本原子扣減確保庫存一致性            |
| 即時推播 | WebSocket 推送排名更新與活動結果          |

### 效能目標

- 並發用戶：1000+ VUs
- 出價處理：毫秒級響應
- 排名查詢：O(log N) 時間複雜度
- 庫存一致性：orders ≤ quota

---

## 2. 系統與部署架構

### 高層架構圖

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                            │
│                   React 18 + TypeScript + Vite                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP / WebSocket
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      GCP Ingress (L7)                           │
│     /api/* & /ws/* ──► Backend    /* ──► Frontend               │
└───────────────────────────┬─────────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
┌───────────────────────┐       ┌───────────────────────┐
│    Backend Service    │       │   Frontend Service    │
│  FastAPI + Uvicorn    │       │   Nginx + Static      │
│    2-5 Pods (HPA)     │       │    1-5 Pods (HPA)     │
└───────────┬───────────┘       └───────────────────────┘
            │
    ┌───────┴───────┐
    ▼               ▼
┌───────┐    ┌─────────────┐
│ Redis │    │  PgBouncer  │
│       │    │  (2 Pods)   │
└───┬───┘    └──────┬──────┘
    │               │
    └───────┬───────┘
            ▼
    ┌───────────────┐
    │  PostgreSQL   │
    │  (Cloud SQL)  │
    └───────────────┘
```

### 雲端配置

| 元件       | 技術                       | 規格                           |
| ---------- | -------------------------- | ------------------------------ |
| Backend    | FastAPI + Uvicorn + uvloop | 2-5 Pods (HPA, CPU 50%)        |
| Frontend   | React 18 + Nginx           | 1-5 Pods (HPA, CPU 70%)        |
| PgBouncer  | Connection Pooler          | 2 Pods, Transaction Mode       |
| Redis      | GCP Memorystore            | 1GB Basic Tier, Redis 7.0      |
| PostgreSQL | Cloud SQL 15               | 2 vCPU / 4GB RAM / 10GB SSD    |

### 連線池配置

```
Backend Pods (最多 5 個)
└── SQLAlchemy AsyncEngine
    └── pool_size=8, max_overflow=15 → 每 Pod 最多 23 連線

PgBouncer (2 Replicas)
└── Transaction Mode
└── max_client_conn=2000
└── default_pool_size=30
└── max_db_connections=50

Cloud SQL PostgreSQL
└── max_connections=200
```

### HPA 擴展策略

| 方向       | 策略                             | 說明               |
| ---------- | -------------------------------- | ------------------ |
| Scale Up   | 無穩定窗口，每 15 秒 +10 pods    | 流量暴增時快速應對 |
| Scale Down | 穩定期後逐步縮減                 | 避免縮容抖動       |

### Docker 映像配置

| 服務      | 基礎映像                      | 特點                                               |
| --------- | ----------------------------- | -------------------------------------------------- |
| Backend   | python:3.11-slim-bookworm     | Multi-stage build, UV 套件管理, uvloop + httptools |
| Frontend  | nginx:1.25-alpine             | Multi-stage build, Node 18 建置, Nginx 靜態服務    |
| PgBouncer | edoburu/pgbouncer             | 輕量連線池代理                                     |

### Kubernetes 資源配置

| 資源類型   | 名稱            | 說明                                           |
| ---------- | --------------- | ---------------------------------------------- |
| Namespace  | flash-sale      | 專案隔離命名空間                               |
| Deployment | backend         | FastAPI 應用，2 workers/Pod + HPA 水平擴展     |
| Deployment | frontend        | Nginx 靜態檔案服務                             |
| Deployment | pgbouncer       | 2 Replicas 連線池代理                          |
| Service    | ClusterIP       | 內部服務發現                                   |
| Ingress    | GCP L7 LB       | 路由 /api/\*, /ws/\* → Backend, /\* → Frontend |
| HPA        | backend-hpa     | CPU 50% 觸發，2-5 Pods                         |
| HPA        | frontend-hpa    | CPU 70% 觸發，1-5 Pods                         |

---

## 3. 資料庫 Schema

### ER Diagram

```
┌────────────────┐           ┌────────────────┐           ┌────────────────┐
│     users      │           │      bids      │           │   campaigns    │
├────────────────┤           ├────────────────┤           ├────────────────┤
│ user_id PK     │◄──────────┤ user_id FK     │     ┌────►│ campaign_id PK │
│ email (UNIQUE) │     1:M   │ campaign_id FK ├─────┘     │ product_id FK  │
│ password_hash  │           │ product_id FK  │    M:1    │ start_time     │
│ username       │           │ price          │           │ end_time       │
│ weight         │           │ score          │           │ alpha/beta     │
│ status         │           │ time_elapsed_ms│           │ gamma          │
│ is_admin       │           │ bid_number     │           │ quota          │
│ created_at     │           │ UNIQUE         │           │ status         │
│ updated_at     │           │ (camp,user)    │           │ created_at     │
└───────┬────────┘           └────────────────┘           └───────┬────────┘
        │                                                         │
        │                    ┌────────────────┐                   │
        │            1:M     │     orders     │    M:1            │
        └───────────────────►├────────────────┤◄──────────────────┘
                             │ order_id PK    │
                             │ product_id FK  │
                             │ final_price    │
                             │ final_score    │
                             │ final_rank     │
                             │ status         │
                             │ UNIQUE         │
                             │ (camp,user)    │
                             └───────┬────────┘
                                     │
                                     │ M:1
                                     ▼
                             ┌────────────────┐
                             │    products    │
                             ├────────────────┤
                             │ product_id PK  │
                             │ name           │
                             │ description    │
                             │ image_url      │
                             │ stock          │
                             │ min_price      │
                             │ version        │
                             │ status         │
                             └────────────────┘
```

### 表格定義

| 表格          | 主要欄位                                                                                | 特殊約束                     |
| ------------- | --------------------------------------------------------------------------------------- | ---------------------------- |
| **users**     | user_id (UUID), email, password_hash, username, weight (0.5-5.0), status, is_admin      | UNIQUE(email)                |
| **products**  | product_id (UUID), name, description, image_url, stock, min_price, version, status      | CHECK(stock >= 0)            |
| **campaigns** | campaign_id (UUID), product_id (FK), start/end_time, alpha/beta/gamma, quota, status    | CHECK(end > start)           |
| **bids**      | bid_id (UUID), campaign_id (FK), user_id (FK), product_id (FK), price, score, time_elapsed_ms, bid_number | UNIQUE(campaign_id, user_id) |
| **orders**    | order_id (UUID), campaign_id (FK), user_id (FK), product_id (FK), final_price, final_score, final_rank, status | UNIQUE(campaign_id, user_id) |

### 關鍵索引

| 表格      | 索引                        | 用途         |
| --------- | --------------------------- | ------------ |
| users     | idx_users_email             | 登入查詢     |
| users     | idx_users_status            | 狀態篩選     |
| bids      | idx_bids_campaign_score     | 排名查詢     |
| bids      | idx_bids_campaign_user      | UPSERT 支援  |
| campaigns | idx_campaigns_status        | 狀態篩選     |
| campaigns | idx_campaigns_time          | 時間範圍查詢 |
| orders    | idx_orders_campaign_created | 活動訂單查詢 |
| orders    | idx_orders_user_created     | 用戶訂單查詢 |
| orders    | idx_orders_status           | 狀態篩選     |

---

## 4. 核心服務與資料流

### 計分公式

```
Score = α × P + β / (T + 1) + γ × W
```

| 參數 | 說明                   | 預設值    |
| ---- | ---------------------- | --------- |
| P    | 出價金額               | 用戶輸入  |
| T    | 活動開始後經過的毫秒數 | 系統計算  |
| W    | 會員權重               | 0.5 - 5.0 |
| K    | 得標名額 (quota)       | 活動設定  |
| α    | 價格權重係數           | 1.0000    |
| β    | 時間權重係數           | 1000.0000 |
| γ    | 會員權重係數           | 100.0000  |

**設計理念**：越高出價、越早出價、越高會員等級 → 越高分數

### 出價流程

```
┌────────┐  POST /bids   ┌─────────────┐  Validate   ┌─────────────┐
│ Client │──────────────►│   Campaign  │────────────►│  Calculate  │
└────────┘               │ Validation  │             │    Score    │
                         │(Redis Cache)│             └──────┬──────┘
                         └─────────────┘                    │
                                                            │
                    ┌───────────────────────────────────────┴───────┐
                    ▼                                               ▼
            ┌──────────────┐                               ┌──────────────┐
            │  PostgreSQL  │                               │    Redis     │
            │   UPSERT     │                               │  Pipeline    │
            │  (Atomic)    │                               │ZADD+HSET    │
            └──────┬───────┘                               └──────┬───────┘
                   │                                              │
                   └─────────────────────┬────────────────────────┘
                                         ▼
                                 ┌──────────────┐
                                 │  WebSocket   │
                                 │ bid_accepted │
                                 └──────────────┘
```

**關鍵技術**：

- **UPSERT**：`INSERT ... ON CONFLICT DO UPDATE` 消除競態條件
- **Redis Pipeline**：ZADD + HSET 合併為 1 RTT，減少延遲
- **三層快取架構**：詳見下方說明
- **float64 優化**：使用 float64 代替 Decimal，提升 10-50x 計算速度

### 三層快取架構

出價時的活動參數查詢採用三層快取，大幅降低延遲：

```
┌─────────────────────────────────────────────────────────────────┐
│                    Campaign Validation Request                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  L1: Local TTLCache   │  ◄── 0ms RTT
                    │  (In-Memory, 60s TTL) │      99.9% hit rate
                    │  maxsize=1000 entries │
                    └───────────┬───────────┘
                                │ miss
                                ▼
                    ┌───────────────────────┐
                    │  L2: Redis Cache      │  ◄── 1-5ms RTT
                    │  (campaign:{id} Hash) │      on L1 miss
                    │  TTL: 3600s           │
                    └───────────┬───────────┘
                                │ miss
                                ▼
                    ┌───────────────────────┐
                    │  L3: PostgreSQL       │  ◄── 10-30ms RTT
                    │  (campaigns + JOIN)   │      on L2 miss
                    └───────────────────────┘
```

| 層級 | 技術                        | 延遲      | 說明                     |
| ---- | --------------------------- | --------- | ------------------------ |
| L1   | cachetools.TTLCache         | 0ms       | Python 進程內記憶體快取 |
| L2   | Redis Hash                  | 1-5ms     | 分散式快取              |
| L3   | PostgreSQL + SQLAlchemy     | 10-30ms   | 持久化資料來源          |

**快取參數**：
- L1 TTL: 60 秒，最大 1000 條目
- L2 TTL: 3600 秒（1 小時）
- 寫入時同步更新 L2，L1 會在下次請求時自動填充

### 結算流程

```
┌───────────────┐      ┌─────────────────┐      ┌─────────────────┐
│ Background    │      │ Query Campaigns │      │  Get Top K from │
│ Loop (10s)    │─────►│ status='active' │─────►│  Redis Sorted   │
└───────────────┘      │ end_time < now  │      │      Set        │
                       └─────────────────┘      └────────┬────────┘
                                                         │
                                                         ▼
                                           ┌─────────────────────────┐
                                           │   Settlement Process    │
                                           │                         │
                                           │  1. Redis Lua 原子扣減  │
                                           │  2. 建立 Order 記錄     │
                                           │  3. 更新活動狀態        │
                                           │  4. 廣播 campaign_ended │
                                           └─────────────────────────┘
```

### 庫存保護機制

**Redis Lua 腳本 - 原子庫存遞減**：
```lua
local stock = tonumber(redis.call("GET", stock_key))
if stock and stock >= 1 then
    return redis.call("DECR", stock_key)
else
    return -1
end
```

### Redis 資料結構

| Key Pattern                           | 結構       | 用途                      | TTL      |
| ------------------------------------- | ---------- | ------------------------- | -------- |
| `bid:{campaign_id}`                   | Sorted Set | 排名（user_id → score）   | -        |
| `bid_details:{campaign_id}:{user_id}` | Hash       | 出價詳情（price, username）| -        |
| `campaign:{campaign_id}`              | String     | 活動參數快取 (JSON)       | 3600 秒  |
| `stock:{product_id}`                  | String     | 即時庫存計數器            | -        |
| `login:{hash}`                        | String     | 登入會話快取 (JSON)       | 60 秒    |

### 排名查詢效能

| 操作                    | 時間複雜度   |
| ----------------------- | ------------ |
| 更新排名 (ZADD)         | O(log N)     |
| 查詢單人排名 (ZREVRANK) | O(log N)     |
| 取得 Top K (ZREVRANGE)  | O(log N + K) |
| 總參與人數 (ZCARD)      | O(1)         |

---

## 5. API 設計

### REST API

| 方法   | 端點                               | 說明                   | 認證     |
| ------ | ---------------------------------- | ---------------------- | -------- |
| POST   | `/api/v1/auth/register`            | 用戶註冊               | -        |
| POST   | `/api/v1/auth/login`               | 用戶登入，取得 JWT     | -        |
| GET    | `/api/v1/auth/me`                  | 取得當前用戶資訊       | Required |
| GET    | `/api/v1/products`                 | 商品列表               | -        |
| GET    | `/api/v1/products/{id}`            | 商品詳情               | -        |
| POST   | `/api/v1/products`                 | 建立商品               | Admin    |
| GET    | `/api/v1/campaigns`                | 活動列表               | -        |
| GET    | `/api/v1/campaigns/{id}`           | 活動詳情（含統計）     | -        |
| POST   | `/api/v1/campaigns`                | 建立活動               | Admin    |
| **POST** | **`/api/v1/bids`**               | **提交出價**           | Required |
| GET    | `/api/v1/bids/{campaign_id}/history` | 用戶競標歷史         | Required |
| GET    | `/api/v1/rankings/{id}`            | 取得 Top K 排名        | -        |
| GET    | `/api/v1/rankings/{id}/me`         | 取得自己的排名         | Required |
| GET    | `/api/v1/orders`                   | 我的訂單列表           | Required |
| GET    | `/api/v1/orders/campaign/{id}`     | 活動訂單（驗證一致性） | Admin    |
| GET    | `/health`                          | 健康檢查               | -        |
| GET    | `/metrics`                         | Prometheus 指標        | -        |

### WebSocket

**端點**：`ws://host/ws/{campaign_id}?token={jwt}`

| 事件              | 方向            | 觸發時機 | 說明             |
| ----------------- | --------------- | -------- | ---------------- |
| `ranking_update`  | Server → Client | 每 2 秒  | 廣播 Top K 排名  |
| `bid_accepted`    | Server → Client | 出價成功 | 推送用戶當前排名 |
| `campaign_ended`  | Server → Client | 活動結算 | 通知最終結果     |
| `ping` / `pong`   | 雙向            | 心跳檢測 | 維持連線         |

### WebSocket 訊息格式

**ranking_update**：
```json
{
  "event": "ranking_update",
  "data": {
    "campaign_id": "uuid",
    "top_k": [
      {"rank": 1, "user_id": "...", "score": 15000.5, "price": 5000, "username": "..."}
    ],
    "total_participants": 1000,
    "min_winning_score": 12000,
    "max_score": 15000.5,
    "timestamp": "2025-12-14T00:00:00Z"
  }
}
```

**bid_accepted**：
```json
{
  "event": "bid_accepted",
  "data": {
    "bid_id": "uuid",
    "campaign_id": "uuid",
    "price": 500.0,
    "score": 9999.99,
    "rank": 5,
    "time_elapsed_ms": 15000,
    "timestamp": "2025-12-14T00:00:00Z"
  }
}
```

**campaign_ended**：
```json
{
  "event": "campaign_ended",
  "data": {
    "campaign_id": "uuid",
    "is_winner": true,
    "final_rank": 5,
    "final_score": 9999.99,
    "final_price": 500.0
  }
}
```

---

## 6. 專案結構

```
flash-sale-system/
├── backend/
│   ├── src/app/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── auth.py          # 認證端點
│   │   │   │   ├── bids.py          # 競標端點
│   │   │   │   ├── campaigns.py     # 活動端點
│   │   │   │   ├── orders.py        # 訂單端點
│   │   │   │   ├── products.py      # 商品端點
│   │   │   │   ├── rankings.py      # 排名端點
│   │   │   │   └── ws.py            # WebSocket 端點
│   │   │   └── deps.py              # 依賴注入
│   │   ├── core/
│   │   │   ├── config.py            # 應用配置
│   │   │   ├── database.py          # 資料庫連線
│   │   │   ├── redis.py             # Redis 連線
│   │   │   └── security.py          # JWT 安全
│   │   ├── middleware/
│   │   │   ├── metrics.py           # Prometheus 指標
│   │   │   └── rate_limit.py        # 速率限制
│   │   ├── models/
│   │   │   ├── user.py              # 用戶模型
│   │   │   ├── product.py           # 商品模型
│   │   │   ├── campaign.py          # 活動模型
│   │   │   ├── bid.py               # 競標模型
│   │   │   └── order.py             # 訂單模型
│   │   ├── schemas/                 # Pydantic 驗證 Schema
│   │   ├── services/
│   │   │   ├── bid_service.py       # 競標業務邏輯
│   │   │   ├── campaign_service.py  # 活動業務邏輯
│   │   │   ├── order_service.py     # 訂單業務邏輯
│   │   │   ├── ranking_service.py   # 排名業務邏輯
│   │   │   ├── settlement_service.py# 結算業務邏輯
│   │   │   ├── inventory_service.py # 庫存業務邏輯
│   │   │   ├── product_service.py   # 商品業務邏輯
│   │   │   ├── user_service.py      # 用戶業務邏輯
│   │   │   ├── redis_service.py     # Redis 操作
│   │   │   └── ws_manager.py        # WebSocket 管理
│   │   └── main.py                  # FastAPI 應用主程式
│   ├── alembic/                     # 資料庫遷移
│   ├── scripts/                     # 輔助腳本
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts            # axios 實例
│   │   │   ├── auth.ts              # 認證 API
│   │   │   ├── bids.ts              # 競標 API
│   │   │   ├── campaigns.ts         # 活動 API
│   │   │   ├── orders.ts            # 訂單 API
│   │   │   ├── products.ts          # 商品 API
│   │   │   └── rankings.ts          # 排名 API
│   │   ├── components/
│   │   │   ├── Layout.tsx           # 頁面佈局
│   │   │   ├── Navbar.tsx           # 導航欄
│   │   │   ├── RankingBoard.tsx     # 排名榜
│   │   │   └── BidForm.tsx          # 出價表單
│   │   ├── contexts/
│   │   │   └── AuthContext.tsx      # 認證狀態管理
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts      # WebSocket Hook
│   │   │   └── useCountdown.ts      # 倒數計時 Hook
│   │   ├── pages/
│   │   │   ├── Login.tsx            # 登入頁
│   │   │   ├── Register.tsx         # 註冊頁
│   │   │   ├── Campaigns.tsx        # 活動列表頁
│   │   │   ├── CampaignDetail.tsx   # 活動詳情頁
│   │   │   └── admin/
│   │   │       └── CreateCampaign.tsx # 建立活動頁
│   │   ├── types/                   # TypeScript 型別定義
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   └── vite.config.ts
├── k8s/
│   ├── namespace.yaml               # 命名空間
│   ├── configmap.yaml               # 配置映射
│   ├── secrets.yaml                 # 密鑰
│   ├── services.yaml                # 服務定義
│   ├── backend-deployment.yaml      # 後端部署
│   ├── backend-config.yaml          # 後端配置
│   ├── frontend-deployment.yaml     # 前端部署
│   ├── pgbouncer-deployment.yaml    # PgBouncer 部署
│   ├── hpa.yaml                     # 自動縮放
│   └── ingress.yaml                 # 入口配置
├── k6-tests/                        # 負載測試腳本與報告
├── docker-compose.yml               # 本地開發環境
└── README.md
```

---

## 7. 技術棧總覽

| 層級     | 技術                                                       |
| -------- | ---------------------------------------------------------- |
| 前端     | React 18, TypeScript, Vite, Tailwind CSS                   |
| 後端     | FastAPI, Uvicorn, uvloop, httptools, SQLAlchemy 2.0        |
| 資料庫   | PostgreSQL 15, Redis 7                                     |
| 連線池   | PgBouncer (Transaction Mode)                               |
| ORM      | SQLAlchemy 2.0 + asyncpg                                   |
| 認證     | JWT (python-jose)                                          |
| 監控     | Prometheus (prometheus-client)                             |
| 容器     | Docker, Kubernetes (GKE Autopilot)                         |
| 負載均衡 | GCP Ingress (L7)                                           |

### 後端 Uvicorn 配置

```bash
uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --loop uvloop \
    --http httptools \
    --timeout-keep-alive 30 \
    --limit-concurrency 500 \
    --limit-max-requests 10000
```

| 參數                  | 說明                            |
| --------------------- | ------------------------------- |
| `--workers 2`         | 雙 worker 支持多核              |
| `--loop uvloop`       | 2-3x 異步性能提升               |
| `--http httptools`    | 更快的 HTTP 解析                |
| `--limit-concurrency` | 支持 1000 VU 負載測試           |
| `--limit-max-requests`| 防止記憶體洩漏                  |

---

## 本地開發

### 環境需求

- Docker & Docker Compose
- Node.js 18+
- Python 3.11+

### 啟動方式

```bash
# 啟動所有服務
docker-compose up -d

# 執行資料庫遷移
docker-compose --profile migration up migrate

# 前端開發模式
cd frontend && npm run dev

# 後端開發模式
cd backend && uvicorn app.main:app --reload
```

### 預設埠號

| 服務       | 埠號 |
| ---------- | ---- |
| Frontend   | 80   |
| Backend    | 8000 |
| PostgreSQL | 5432 |
| Redis      | 6379 |
