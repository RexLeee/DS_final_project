# 即時競標與限時搶購系統

分散式系統與雲端應用開發實務期末專案

---

## 目錄

1. [專案目標與需求](#1-專案目標與需求)
2. [系統與部署架構](#2-系統與部署架構)
3. [資料庫 Schema](#3-資料庫-schema)
4. [核心服務與資料流](#4-核心服務與資料流)
5. [API 設計](#5-api-設計)

---

## 1. 專案目標與需求

### 系統定位

專為高並發場景設計的即時競標系統，支援 1000+ 並發用戶，提供毫秒級出價處理與即時排名更新。

### 核心功能

| 功能     | 說明                                      |
| -------- | ----------------------------------------- |
| 即時競標 | 用戶對商品出價，系統即時計算排名          |
| 限時搶購 | 活動結束時，排名前 K 名用戶自動成為得標者 |
| 庫存保護 | 四層防超賣機制確保庫存一致性              |
| 即時推播 | WebSocket 推送排名更新與活動結果          |

### 效能目標

- 並發用戶：1000+ VUs
- 出價處理：毫秒級響應
- 排名查詢：O(log N) 時間複雜度
- 庫存一致性：orders ≤ stock

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
│    5-50 Pods (HPA)    │       │    1-5 Pods (HPA)     │
└───────────┬───────────┘       └───────────────────────┘
            │
    ┌───────┴───────┐
    ▼               ▼
┌───────┐    ┌─────────────┐
│ Redis │    │  PgBouncer  │
│       │    │  (6 Pods)   │
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

| 元件       | 技術                       | 規格                      |
| ---------- | -------------------------- | ------------------------- |
| Backend    | FastAPI + Uvicorn + uvloop | 5-50 Pods (HPA, CPU 50%)  |
| Frontend   | React 18 + Nginx           | 1-5 Pods (HPA)            |
| PgBouncer  | Connection Pooler          | 6 Pods, Transaction Mode  |
| Redis      | GCP Memorystore            | 1GB Basic Tier, Redis 7.0 |
| PostgreSQL | Cloud SQL 15               | 2 vCPU / 4GB RAM / 10GB SSD, max_connections=200 |

### 連線池配置

```
Backend Pods (最多 50 個)
└── SQLAlchemy AsyncEngine
    └── pool_size=8, max_overflow=15 → 每 Pod 最多 23 連線

PgBouncer (6 Replicas)
└── Transaction Mode
└── max_client_conn=2000
└── max_db_connections=30/pod → 共 180 DB 連線

Cloud SQL PostgreSQL
└── max_connections=200

連線複用比: 1,150 : 180 = 6.4 : 1
```

### HPA 擴展策略

| 方向       | 策略                           | 說明               |
| ---------- | ------------------------------ | ------------------ |
| Scale Up   | 無穩定窗口，每 15 秒 +10 pods  | 流量暴增時快速應對 |
| Scale Down | 5 分鐘穩定期，每 60 秒 -2 pods | 避免縮容抖動       |

### Docker 映像配置

| 服務     | 基礎映像                 | 特點                                         |
| -------- | ------------------------ | -------------------------------------------- |
| Backend  | python:3.11-slim-bookworm | Multi-stage build, UV 套件管理, uvloop + httptools |
| Frontend | nginx:1.25-alpine        | Multi-stage build, Node 18 建置, Nginx 靜態服務   |
| PgBouncer| edoburu/pgbouncer        | 輕量連線池代理                                |

### Kubernetes 資源配置

| 資源類型   | 名稱            | 說明                                    |
| ---------- | --------------- | --------------------------------------- |
| Namespace  | flash-sale      | 專案隔離命名空間                        |
| Deployment | backend         | FastAPI 應用，單 worker/Pod + HPA 水平擴展 |
| Deployment | frontend        | Nginx 靜態檔案服務                      |
| Deployment | pgbouncer       | 6 Replicas 連線池代理                   |
| Service    | ClusterIP       | 內部服務發現                            |
| Ingress    | GCP L7 LB       | 路由 /api/*, /ws/* → Backend, /* → Frontend |
| HPA        | backend-hpa     | CPU 50% 觸發，5-50 Pods                 |
| HPA        | frontend-hpa    | CPU 70% 觸發，1-5 Pods                  |

---

## 3. 資料庫 Schema

### ER Diagram

```
┌────────────┐           ┌────────────┐           ┌────────────┐
│   users    │           │    bids    │           │ campaigns  │
├────────────┤           ├────────────┤           ├────────────┤
│ user_id PK │◄──────────┤ user_id FK │     ┌────►│campaign_id │
│ email      │     1:M   │ campaign_id├─────┘     │ product_id │
│ username   │           │ price      │    M:1    │ start_time │
│ weight     │           │ score      │           │ end_time   │
│ is_admin   │           │ UNIQUE     │           │ alpha/beta │
└─────┬──────┘           │(camp,user) │           │ gamma      │
      │                  └────────────┘           └─────┬──────┘
      │                                                 │
      │                  ┌────────────┐                 │
      │           1:M    │   orders   │    M:1          │
      └─────────────────►├────────────┤◄────────────────┘
                         │ order_id PK│
                         │ final_price│
                         │ final_rank │
                         │ UNIQUE     │
                         │(camp,user) │
                         └─────┬──────┘
                               │
                               │ M:1
                               ▼
                         ┌────────────┐
                         │  products  │
                         ├────────────┤
                         │product_id  │
                         │ name       │
                         │ stock      │
                         │ min_price  │
                         │ version    │
                         └────────────┘
```

### 表格定義

| 表格                | 主要欄位                                                                     | 特殊約束                               |
| ------------------- | ---------------------------------------------------------------------------- | -------------------------------------- |
| **users**     | user_id (UUID), email, username, weight (0.5-5.0), is_admin                  | UNIQUE(email)                          |
| **products**  | product_id (UUID), name, stock, min_price, version                           | CHECK(stock >= 0)                      |
| **campaigns** | campaign_id (UUID), product_id (FK), start/end_time, alpha/beta/gamma        | CHECK(end > start)                     |
| **bids**      | bid_id (UUID), campaign_id (FK), user_id (FK), price, score, time_elapsed_ms | **UNIQUE(campaign_id, user_id)** |
| **orders**    | order_id (UUID), campaign_id (FK), user_id (FK), final_price, final_rank     | UNIQUE(campaign_id, user_id)           |

### 關鍵索引

| 表格      | 索引                    | 用途         |
| --------- | ----------------------- | ------------ |
| bids      | idx_bids_campaign_score | 排名查詢     |
| bids      | uq_bids_campaign_user   | UPSERT 支援  |
| campaigns | idx_campaigns_status    | 狀態篩選     |
| campaigns | idx_campaigns_time      | 時間範圍查詢 |

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
| K    | 商品庫存（得標名額）   | 活動設定  |
| α   | 價格權重係數           | 1.0000    |
| β   | 時間權重係數           | 1000.0000 |
| γ   | 會員權重係數           | 100.0000  |

**設計理念**：越高出價、越早出價、越高會員等級 → 越高分數

### 出價流程

```
┌────────┐  POST /bids   ┌─────────────┐  Validate   ┌─────────────┐
│ Client │──────────────►│Rate Limiter │────────────►│  Campaign   │
└────────┘               │ (Lua Script)│             │ Validation  │
                         └─────────────┘             └──────┬──────┘
                                                            │
                                                            ▼
                                                    ┌──────────────┐
                                                    │   Calculate  │
                                                    │    Score     │
                                                    └──────┬───────┘
                                                           │
                    ┌──────────────────────────────────────┴───────┐
                    ▼                                              ▼
            ┌──────────────┐                              ┌──────────────┐
            │  PostgreSQL  │                              │    Redis     │
            │   UPSERT     │                              │  Pipeline    │
            │  (Atomic)    │                              │ZADD+HSET+RANK│
            └──────┬───────┘                              └──────┬───────┘
                   │                                             │
                   └─────────────────────┬───────────────────────┘
                                         ▼
                                 ┌──────────────┐
                                 │  WebSocket   │
                                 │ bid_accepted │
                                 └──────────────┘
```

**關鍵技術**：

- **UPSERT**：`INSERT ... ON CONFLICT DO UPDATE` 消除競態條件
- **Redis Pipeline**：ZADD + HSET + ZREVRANK 合併為 1 RTT，減少 40-60% 延遲

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
                                           │  Four-Layer Protection  │
                                           │                         │
                                           │  L1: Redis 分散式鎖     │
                                           │  L2: Redis Lua 原子扣減 │
                                           │  L3: PostgreSQL 行級鎖  │
                                           │  L4: 樂觀鎖 (version)   │
                                           └────────────┬────────────┘
                                                        │
                                                        ▼
                                           ┌─────────────────────────┐
                                           │   Create Order Records  │
                                           │  Broadcast campaign_end │
                                           └─────────────────────────┘
```

### 四層防超賣機制

| 層級         | 機制              | 實現                              | 目的           |
| ------------ | ----------------- | --------------------------------- | -------------- |
| **L1** | Redis 分散式鎖    | `SET lock:product:{id} NX EX 2` | 序列化並發請求 |
| **L2** | Redis 原子扣減    | Lua:`if stock >= 1 then DECR`   | 快速庫存檢查   |
| **L3** | PostgreSQL 行級鎖 | `SELECT ... FOR UPDATE`         | 鎖定該行       |
| **L4** | 樂觀鎖            | `UPDATE WHERE version = ?`      | 最終一致性保證 |

### Redis 資料結構

| Key Pattern                             | 結構       | 用途                        |
| --------------------------------------- | ---------- | --------------------------- |
| `bid:{campaign_id}`                   | Sorted Set | 排名（user_id → score）    |
| `bid_details:{campaign_id}:{user_id}` | Hash       | 出價詳情（price, username） |
| `stock:{product_id}`                  | String     | 即時庫存計數器              |
| `lock:product:{product_id}`           | String     | 分散式鎖（TTL 2秒）         |

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

| 方法           | 端點                             | 說明                   | 認證     |
| -------------- | -------------------------------- | ---------------------- | -------- |
| POST           | `/api/v1/auth/register`        | 用戶註冊               | -        |
| POST           | `/api/v1/auth/login`           | 用戶登入，取得 JWT     | -        |
| GET            | `/api/v1/auth/me`              | 取得當前用戶資訊       | Required |
| GET            | `/api/v1/products`             | 商品列表               | -        |
| POST           | `/api/v1/products`             | 建立商品               | Admin    |
| GET            | `/api/v1/campaigns`            | 活動列表               | -        |
| GET            | `/api/v1/campaigns/{id}`       | 活動詳情（含統計）     | -        |
| POST           | `/api/v1/campaigns`            | 建立活動               | Admin    |
| **POST** | **`/api/v1/bids`**       | **提交出價**     | Required |
| GET            | `/api/v1/rankings/{id}`        | 取得 Top K 排名        | -        |
| GET            | `/api/v1/rankings/{id}/me`     | 取得自己的排名         | Required |
| GET            | `/api/v1/orders`               | 我的訂單列表           | Required |
| GET            | `/api/v1/orders/campaign/{id}` | 活動訂單（驗證一致性） | Admin    |

### WebSocket

**端點**：`ws://host/ws/{campaign_id}?token={jwt}`

| 事件                | 方向             | 觸發時機 | 說明             |
| ------------------- | ---------------- | -------- | ---------------- |
| `ranking_update`  | Server → Client | 每 2 秒  | 廣播 Top K 排名  |
| `bid_accepted`    | Server → Client | 出價成功 | 推送用戶當前排名 |
| `campaign_ended`  | Server → Client | 活動結算 | 通知最終結果     |
| `ping` / `pong` | 雙向             | 心跳檢測 | 維持連線         |

### 排名廣播資料結構

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
    "max_score": 15000.5
  }
}
```

---

## 技術棧總覽

| 層級     | 技術                                     |
| -------- | ---------------------------------------- |
| 前端     | React 18, TypeScript, Vite, Tailwind CSS |
| 後端     | FastAPI, Uvicorn, uvloop, SQLAlchemy 2.0 |
| 資料庫   | PostgreSQL 15, Redis 7                   |
| 連線池   | PgBouncer (Transaction Mode)             |
| 容器     | Docker, Kubernetes (GKE Autopilot)       |
| 負載均衡 | GCP Ingress (L7)                         |

---

## 專案結構

```
flash-sale-system/
├── backend/
│   └── src/app/
│       ├── api/v1/           # API 路由
│       ├── core/             # 核心配置
│       ├── middleware/       # 中介軟體
│       ├── models/           # SQLAlchemy 模型
│       ├── schemas/          # Pydantic Schema
│       ├── services/         # 業務邏輯
│       └── main.py
├── frontend/
│   └── src/
│       ├── api/              # API 客戶端
│       ├── components/       # React 元件
│       ├── contexts/         # 狀態管理
│       ├── hooks/            # 自訂 Hooks
│       └── pages/            # 頁面元件
├── k8s/                      # Kubernetes 配置
├── k6-tests/                 # 負載測試腳本
└── docker-compose.yml        # 本地開發環境
```
