# 即時競標與限時搶購系統 - 技術規格文件

## 文件資訊

| 項目 | 內容 |
|------|------|
| **專案名稱** | Real-time Bidding & Flash Sale System |
| **文件版本** | 1.0 |
| **建立日期** | 2025-12-03 |
| **文件狀態** | 最終版本 |

---

## 目錄

1. [系統架構設計](#1-系統架構設計)
2. [資料庫設計](#2-資料庫設計)
3. [高並發寫入處理策略](#3-高並發寫入處理策略)
4. [即時排名計算與推播](#4-即時排名計算與推播)
5. [庫存一致性保證（防超賣）](#5-庫存一致性保證防超賣)
6. [API 設計](#6-api-設計)
7. [可擴展性設計](#7-可擴展性設計)
8. [容器化與 GCP 雲端部署](#8-容器化與-gcp-雲端部署)
9. [監控與可觀測性](#9-監控與可觀測性)
10. [壓力測試設計](#10-壓力測試設計)
11. [安全性考量](#11-安全性考量)

---

## 1. 系統架構設計

### 1.1 整體架構概述

本系統採用**微服務架構**結合**事件驅動模式**，使用 **CQRS (Command Query Responsibility Segregation)** 分離讀寫操作，確保高並發下的系統穩定性與擴展能力。

### 1.2 系統架構圖

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              用戶層                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │   一般會員    │  │  平台管理員   │  │  監控人員     │                   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                   │
└─────────┼─────────────────┼─────────────────┼───────────────────────────┘
          │ HTTPS/WSS       │ HTTPS           │ HTTPS
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         GCP Cloud Load Balancing                         │
│                    (L7 負載均衡 + SSL 終止 + WAF)                         │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
          ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端應用       │    │   API Gateway    │    │  WebSocket      │
│   (React SPA)   │    │   (Kong/Nginx)   │    │  Gateway        │
│   CDN 分發       │    │   限流、路由      │    │  即時推播        │
└─────────────────┘    └────────┬────────┘    └────────┬────────┘
                                │                      │
                    ┌───────────┴───────────┐          │
                    │                       │          │
┌───────────────────┴───────────────────────┴──────────┴──────────────────┐
│                         GKE (Kubernetes 叢集)                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│  │ User Service│ │Product Svc  │ │Bidding Svc  │ │Ranking Svc  │       │
│  │ (會員服務)   │ │(商品服務)    │ │(競標核心)    │ │(排名服務)    │       │
│  │ Python      │ │ Python      │ │ Python      │ │ Python      │       │
│  │ FastAPI     │ │ FastAPI     │ │ FastAPI     │ │ FastAPI     │       │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘       │
│         │               │               │               │               │
│  ┌─────────────┐                 ┌─────────────┐                        │
│  │Order Service│                 │Notification │                        │
│  │(訂單服務)    │                 │Service      │                        │
│  │ Python      │                 │(通知服務)    │                        │
│  └──────┬──────┘                 └──────┬──────┘                        │
└─────────┼───────────────────────────────┼──────────────────────────────┘
          │                               │
          ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           訊息佇列層                                      │
│                    ┌─────────────────────────┐                           │
│                    │   Google Cloud Pub/Sub   │                          │
│                    │   (事件驅動、解耦)         │                          │
│                    └─────────────────────────┘                           │
└─────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            資料層                                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │  Cloud SQL      │  │  Memorystore    │  │  Cloud Storage  │         │
│  │  (PostgreSQL)   │  │  (Redis)        │  │  (靜態資源)      │         │
│  │  ・用戶資料      │  │  ・排名 Sorted   │  │  ・商品圖片      │         │
│  │  ・商品資料      │  │    Set          │  │  ・日誌備份      │         │
│  │  ・訂單資料      │  │  ・庫存計數      │  │                 │         │
│  │  ・競標記錄      │  │  ・分散式鎖      │  │                 │         │
│  │                 │  │  ・Session      │  │                 │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.3 微服務拆分

| 服務名稱 | 職責 | 技術棧 | 主要資料庫 |
|----------|------|--------|-----------|
| **User Service** | 會員註冊、登入、權重管理 | Python + FastAPI | PostgreSQL + Redis (Session) |
| **Product Service** | 商品 CRUD、活動參數設定 | Python + FastAPI | PostgreSQL |
| **Bidding Service** | 接收出價、計算積分、發布事件 | Python + FastAPI | Redis + Pub/Sub |
| **Ranking Service** | 消費出價事件、更新排名 | Python + FastAPI | Redis (Sorted Set) |
| **Order Service** | 活動結算、訂單生成、防超賣 | Python + FastAPI | PostgreSQL |
| **WebSocket Gateway** | 維護 WS 連接、推送即時排名 | Python + FastAPI | Redis Pub/Sub |
| **Notification Service** | 發送得標/未得標通知 | Python + Celery | Pub/Sub |

### 1.4 技術棧選型

| 類別 | 技術 | 選型理由 |
|------|------|----------|
| **後端語言** | Python 3.11+ | 開發效率高、生態豐富、團隊熟悉 |
| **套件管理** | UV | 極速套件安裝、虛擬環境管理、取代 pip + venv |
| **Web 框架** | FastAPI | 異步支援 (asyncio)、自動生成 OpenAPI 文檔、高性能 |
| **異步任務** | Celery + Redis | 分散式任務佇列、延遲任務處理 |
| **主資料庫** | PostgreSQL 15 | ACID 保證、行級鎖、JSON 支援 |
| **快取** | Redis 7 (Memorystore) | Sorted Set 天然適合排行榜、原子操作防超賣 |
| **訊息佇列** | Google Cloud Pub/Sub | GCP 原生整合、自動擴展、至少一次投遞 |
| **容器編排** | GKE (Kubernetes) | 自動擴展、自癒能力、服務發現 |
| **前端** | React 18 + TypeScript | 生態成熟、型別安全 |

> **UV 套件管理工具說明**:
> - 官方文檔: https://docs.astral.sh/uv/
> - 由 Astral 開發，比 pip 快 10-100 倍
> - 使用 `pyproject.toml` 管理依賴
> - 支援虛擬環境建立與管理 (`uv venv`)
> - 支援鎖定檔案 (`uv.lock`) 確保環境一致性

### 1.5 服務間通訊模式

```
┌─────────────────────────────────────────────────────────────────┐
│                     服務間通訊模式                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  同步通訊 (REST API)              異步通訊 (Pub/Sub)             │
│  ┌─────────────────┐              ┌─────────────────┐           │
│  │ • 用戶認證       │              │ • 出價事件       │           │
│  │ • 查詢排名       │              │ • 排名更新通知    │           │
│  │ • 獲取商品資訊    │              │ • 訂單建立事件    │           │
│  │ • 提交出價       │              │ • 活動結束事件    │           │
│  └─────────────────┘              └─────────────────┘           │
│          │                               │                      │
│          ▼                               ▼                      │
│  適用場景：                         適用場景：                    │
│  • 需要立即回應                     • 可以容忍延遲                 │
│  • 簡單查詢操作                     • 需要解耦服務                 │
│  • 用戶直接互動                     • 批次處理                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.6 設計原則

1. **無狀態服務**: 所有服務不在記憶體中保存狀態，Session 存 Redis
2. **故障隔離**: 使用熔斷器 (Circuit Breaker) 防止級聯失敗
3. **最終一致性**: 出價記錄允許異步寫入，但庫存扣減必須同步
4. **冪等性**: 所有寫入操作支援重試，避免重複處理

---

## 2. 資料庫設計

### 2.1 PostgreSQL Schema

#### 2.1.1 ER Diagram

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     users       │       │    products     │       │   campaigns     │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ PK user_id      │       │ PK product_id   │       │ PK campaign_id  │
│    email        │       │    name         │       │ FK product_id   │
│    password_hash│       │    description  │       │    start_time   │
│    username     │       │    image_url    │       │    end_time     │
│    weight (W)   │       │    stock (K)    │       │    alpha (α)    │
│    status       │       │    min_price    │       │    beta (β)     │
│    created_at   │       │    version      │       │    gamma (γ)    │
└────────┬────────┘       │    status       │       │    status       │
         │                └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         │    ┌────────────────────┴─────────────────────────┘
         │    │
         ▼    ▼
┌─────────────────────────────────┐       ┌─────────────────┐
│            bids                 │       │     orders      │
├─────────────────────────────────┤       ├─────────────────┤
│ PK bid_id                       │       │ PK order_id     │
│ FK campaign_id                  │       │ FK campaign_id  │
│ FK user_id                      │       │ FK user_id      │
│ FK product_id                   │       │ FK product_id   │
│    price (P)                    │       │    final_price  │
│    score                        │       │    final_score  │
│    time_elapsed_ms (T)          │       │    final_rank   │
│    bid_number                   │       │    status       │
│    created_at                   │       │    created_at   │
└─────────────────────────────────┘       └─────────────────┘
```

#### 2.1.2 Table Schema

**users（用戶表）**
```sql
CREATE TABLE users (
    user_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    username        VARCHAR(100) NOT NULL,
    weight          DECIMAL(10,2) NOT NULL DEFAULT 1.00,  -- 會員權重 W
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status);
```

**products（商品表）**
```sql
CREATE TABLE products (
    product_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    image_url       VARCHAR(500),
    stock           INTEGER NOT NULL CHECK (stock >= 0),  -- 庫存數量 K
    min_price       DECIMAL(10,2) NOT NULL CHECK (min_price > 0),  -- 底價
    version         INTEGER NOT NULL DEFAULT 0,  -- 樂觀鎖版本號
    status          VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**campaigns（活動表）**
```sql
CREATE TABLE campaigns (
    campaign_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id      UUID NOT NULL REFERENCES products(product_id),
    start_time      TIMESTAMP NOT NULL,
    end_time        TIMESTAMP NOT NULL,
    alpha           DECIMAL(10,4) NOT NULL DEFAULT 1.0000,   -- 價格權重 α
    beta            DECIMAL(10,4) NOT NULL DEFAULT 1000.0000, -- 時間權重 β
    gamma           DECIMAL(10,4) NOT NULL DEFAULT 100.0000,  -- 會員權重 γ
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_time CHECK (end_time > start_time)
);

CREATE INDEX idx_campaigns_status ON campaigns(status);
CREATE INDEX idx_campaigns_time ON campaigns(start_time, end_time);
```

**bids（出價記錄表）**
```sql
CREATE TABLE bids (
    bid_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id     UUID NOT NULL REFERENCES campaigns(campaign_id),
    user_id         UUID NOT NULL REFERENCES users(user_id),
    product_id      UUID NOT NULL REFERENCES products(product_id),
    price           DECIMAL(10,2) NOT NULL CHECK (price > 0),
    score           DECIMAL(15,4) NOT NULL,
    time_elapsed_ms BIGINT NOT NULL,  -- 反應時間 T（毫秒）
    bid_number      INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_bids_campaign_user ON bids(campaign_id, user_id);
CREATE INDEX idx_bids_campaign_score ON bids(campaign_id, score DESC);
```

**orders（訂單表）**
```sql
CREATE TABLE orders (
    order_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id     UUID NOT NULL REFERENCES campaigns(campaign_id),
    user_id         UUID NOT NULL REFERENCES users(user_id),
    product_id      UUID NOT NULL REFERENCES products(product_id),
    final_price     DECIMAL(10,2) NOT NULL,
    final_score     DECIMAL(15,4) NOT NULL,
    final_rank      INTEGER NOT NULL CHECK (final_rank > 0),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (campaign_id, user_id)  -- 每人每活動只能一筆訂單
);
```

### 2.2 Redis 資料結構設計

| Key Pattern | 資料結構 | 用途 | TTL |
|-------------|----------|------|-----|
| `bid:{campaign_id}` | Sorted Set | 競標排名（score=積分, member=user_id） | 活動期間 + 1hr |
| `stock:{product_id}` | String (Integer) | 庫存計數器（原子扣減） | 永久 |
| `lock:product:{product_id}` | String | 分散式鎖 | 2 秒 |
| `campaign:{campaign_id}` | Hash | 活動快取（參數α,β,γ等） | 活動期間 + 1hr |
| `session:{session_id}` | String (JSON) | 用戶 Session | 1 小時 |
| `user_weight` | Hash | 用戶權重快取 | 1 小時 |

**排名操作範例：**
```
# 更新用戶排名
ZADD bid:campaign-123 1523.75 user-456

# 獲取 Top K (K=10)
ZREVRANGE bid:campaign-123 0 9 WITHSCORES

# 獲取用戶排名 (0-based)
ZREVRANK bid:campaign-123 user-456

# 獲取用戶分數
ZSCORE bid:campaign-123 user-456

# 總參與人數
ZCARD bid:campaign-123
```

### 2.3 讀寫分離策略

```
                     ┌─────────────────┐
                     │   Application   │
                     └────────┬────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
         Write Ops                       Read Ops
              │                               │
              ▼                               ▼
      ┌──────────────┐              ┌──────────────┐
      │   Primary    │    同步複製   │   Replica    │
      │   (Master)   │ ───────────> │   (Slave)    │
      │ Cloud SQL    │              │ Cloud SQL    │
      └──────────────┘              └──────────────┘
       us-central1-a                 us-central1-b
```

- **寫入操作**: 用戶註冊、出價記錄、訂單建立 → Primary
- **讀取操作**: 查詢排名、商品列表、用戶資訊 → Replica

---

## 3. 高並發寫入處理策略

### 3.1 流量處理架構

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        高並發寫入處理流程                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌───────┐ │
│  │  Client │───>│   WAF   │───>│   LB    │───>│ Gateway │───>│ Rate  │ │
│  │ 1000+   │    │ 防護    │    │ 負載    │    │ 路由    │    │ Limit │ │
│  │ Users   │    │         │    │ 均衡    │    │         │    │       │ │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘    └───┬───┘ │
│                                                                  │     │
│                                   ┌──────────────────────────────┘     │
│                                   ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                      Bidding Service                             │  │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐       │  │
│  │  │ 驗證請求 │───>│ 計算積分 │───>│ 發布事件 │───>│ 回應客戶 │       │  │
│  │  │         │    │ Score   │    │ Pub/Sub │    │ 端       │       │  │
│  │  └─────────┘    └─────────┘    └─────────┘    └─────────┘       │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                   │                                    │
│                                   ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                    Google Cloud Pub/Sub                          │  │
│  │                    (削峰填谷、流量緩衝)                            │  │
│  └────────────────────────────┬────────────────────────────────────┘  │
│                               │                                       │
│                    ┌──────────┴──────────┐                           │
│                    ▼                     ▼                           │
│             ┌─────────────┐       ┌─────────────┐                    │
│             │ Ranking Svc │       │ History Svc │                    │
│             │ 更新 Redis  │       │ 寫入 DB     │                    │
│             │ Sorted Set  │       │ 批次處理    │                    │
│             └─────────────┘       └─────────────┘                    │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

### 3.2 限流策略 (Rate Limiting)

採用 **Token Bucket 演算法**：

| 限流層級 | 限制 | 說明 |
|----------|------|------|
| 全局限流 | 10,000 req/s | 整體系統保護 |
| 用戶限流 | 10 req/s | 防止單用戶濫用 |
| IP 限流 | 100 req/s | 防止 DDoS |

**限流回應：**
- HTTP 429 Too Many Requests
- 回應 `Retry-After` header

### 3.3 訊息佇列削峰 (Pub/Sub)

**Topic 設計：**
| Topic | Publisher | Subscriber | 用途 |
|-------|-----------|------------|------|
| `bid-events` | Bidding Service | Ranking Service, History Service | 出價事件 |
| `ranking-updates` | Ranking Service | WebSocket Gateway | 排名變更 |
| `campaign-events` | Product Service | All Services | 活動狀態變更 |
| `order-events` | Order Service | Notification Service | 訂單事件 |

**處理流程：**
1. Bidding Service 收到出價請求，驗證後立即發布到 Pub/Sub
2. 快速回應客戶端（不等待排名更新）
3. Ranking Service 異步消費事件，更新 Redis 排名
4. WebSocket Gateway 推送排名變更給前端

### 3.4 批次處理策略

```
┌─────────────────────────────────────────────────────────────────┐
│                     批次處理機制                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  出價請求 ──────────────────────────────────────────────────>   │
│     │                                                           │
│     ▼                                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Buffer (100ms 窗口)                   │   │
│  │   [bid1] [bid2] [bid3] [bid4] [bid5] ... [bid50]        │   │
│  └────────────────────────┬────────────────────────────────┘   │
│                           │                                     │
│           ┌───────────────┴───────────────┐                    │
│           │                               │                    │
│           ▼                               ▼                    │
│   觸發條件 1: 滿 50 筆            觸發條件 2: 超過 100ms         │
│           │                               │                    │
│           └───────────────┬───────────────┘                    │
│                           │                                     │
│                           ▼                                     │
│              ┌─────────────────────────┐                       │
│              │    Redis Pipeline       │                       │
│              │    批次 ZADD 操作       │                       │
│              └─────────────────────────┘                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

- **時間窗口**: 100ms
- **批次大小**: 50 筆
- **優點**: 減少 Redis 網路往返，提升吞吐量

---

## 4. 即時排名計算與推播

### 4.1 積分計算公式

```
Score = α·P + β/(T+1) + γ·W
```

| 參數 | 說明 | 範圍 | 影響 |
|------|------|------|------|
| **P** (Price) | 出價金額 | ≥ 底價 | 出價越高，分數越高 |
| **T** (Time) | 反應時間（毫秒） | ≥ 0 | 反應越快，分數越高 |
| **W** (Weight) | 會員權重 | 0.5 ~ 5.0 | 等級越高，分數越高 |
| **α** | 價格權重 | 建議 1.0 | 調整價格影響程度 |
| **β** | 時間權重 | 建議 1000 | 調整速度影響程度 |
| **γ** | 會員權重 | 建議 100 | 調整會員等級影響程度 |

**計算範例：**
```
設定: α=1.0, β=1000, γ=100
用戶A: P=1500, T=2000ms, W=2.0
Score = 1.0×1500 + 1000/(2000+1) + 100×2.0
      = 1500 + 0.5 + 200
      = 1700.5
```

### 4.2 排名更新流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        排名更新流程                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐                                                          │
│  │ 用戶出價  │                                                          │
│  └────┬─────┘                                                          │
│       │                                                                 │
│       ▼                                                                 │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 1. Bidding Service 計算 Score                                     │  │
│  │    • 獲取活動參數 (α, β, γ) 從 Redis 快取                          │  │
│  │    • 計算 T = current_time - campaign_start_time                  │  │
│  │    • 計算 Score = α·P + β/(T+1) + γ·W                            │  │
│  └────────────────────────────┬─────────────────────────────────────┘  │
│                               │                                        │
│                               ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 2. 發布出價事件到 Pub/Sub                                          │  │
│  │    Topic: bid-events                                              │  │
│  │    Payload: {campaign_id, user_id, price, score, timestamp}       │  │
│  └────────────────────────────┬─────────────────────────────────────┘  │
│                               │                                        │
│                               ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 3. Ranking Service 消費事件                                        │  │
│  │    • ZADD bid:{campaign_id} {score} {user_id}                     │  │
│  │    • 更新 Redis Sorted Set                                        │  │
│  └────────────────────────────┬─────────────────────────────────────┘  │
│                               │                                        │
│                               ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 4. 發布排名更新事件                                                 │  │
│  │    Topic: ranking-updates                                         │  │
│  │    Payload: {campaign_id, top_k, total_participants, timestamp}   │  │
│  └────────────────────────────┬─────────────────────────────────────┘  │
│                               │                                        │
│                               ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 5. WebSocket Gateway 推播                                          │  │
│  │    • 訂閱 ranking-updates topic                                   │  │
│  │    • 廣播到 campaign:{campaign_id} 房間的所有連接                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.3 即時推播機制 (WebSocket)

**連接管理：**
```
┌────────────────────────────────────────────────────────────────┐
│                    WebSocket 連接管理                           │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Client                    Server (WS Gateway)                 │
│    │                              │                            │
│    │──── connect ─────────────────>│                           │
│    │                              │                            │
│    │<─── connected ───────────────│                            │
│    │                              │                            │
│    │──── join_campaign ──────────>│  加入活動房間               │
│    │     {campaign_id: "xxx"}     │                            │
│    │                              │                            │
│    │<─── ranking_update ─────────│  即時排名推送               │
│    │     {top_k: [...]}           │  (每 1-2 秒)               │
│    │                              │                            │
│    │<─── bid_accepted ───────────│  出價確認                   │
│    │     {score: 1523.75,         │                            │
│    │      rank: 15}               │                            │
│    │                              │                            │
│    │<─── campaign_ended ─────────│  活動結束                   │
│    │     {is_winner: true}        │                            │
│    │                              │                            │
└────────────────────────────────────────────────────────────────┘
```

**推播事件類型：**
| 事件 | 觸發條件 | 頻率 | 內容 |
|------|----------|------|------|
| `ranking_update` | 排名有變化 | 1-2 秒 | Top K 排名、最高/最低分 |
| `bid_accepted` | 用戶出價成功 | 即時 | 個人積分、排名 |
| `stats_update` | 統計變化 | 2 秒 | 參與人數、出價次數 |
| `campaign_ended` | 活動結束 | 一次 | 得標結果 |

### 4.4 快取策略

```
┌─────────────────────────────────────────────────────────────────┐
│                     多層快取架構                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐                                               │
│   │   Request   │                                               │
│   └──────┬──────┘                                               │
│          │                                                      │
│          ▼                                                      │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │     L1 Cache: Application Memory (TTL: 5秒)              │  │
│   │     • 熱門活動參數                                        │  │
│   │     • 當前排名快照                                        │  │
│   └────────────────────────┬────────────────────────────────┘  │
│                            │ Cache Miss                        │
│                            ▼                                   │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │     L2 Cache: Redis Memorystore (TTL: 30秒~永久)         │  │
│   │     • 排名 Sorted Set (永久)                             │  │
│   │     • 活動資訊 Hash (活動期間)                            │  │
│   │     • Session (1小時)                                    │  │
│   └────────────────────────┬────────────────────────────────┘  │
│                            │ Cache Miss                        │
│                            ▼                                   │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │     L3: Cloud SQL PostgreSQL                             │  │
│   │     • 持久化存儲                                          │  │
│   │     • 歷史記錄                                            │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. 庫存一致性保證（防超賣）

### 5.1 四層防護架構

防超賣是本系統的**核心需求**，採用多層防護確保**絕對不發生超賣**。

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        四層防超賣機制                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Layer 1: Redis 分散式鎖                                                │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  • 粒度: product_id                                               │  │
│  │  • TTL: 2 秒（防死鎖）                                            │  │
│  │  • 作用: 防止同一商品並發修改                                       │  │
│  │  • 命令: SET lock:product:{id} {uuid} NX EX 2                     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                   │                                    │
│                                   ▼                                    │
│  Layer 2: Redis 原子扣減（核心）                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  • 使用 Lua 腳本保證原子性                                         │  │
│  │  • 先檢查庫存再扣減                                               │  │
│  │  • 庫存 < 0 立即拒絕                                              │  │
│  │  Lua Script:                                                      │  │
│  │  if redis.call("GET", key) >= 1 then                             │  │
│  │      return redis.call("DECR", key)                               │  │
│  │  else                                                             │  │
│  │      return -1  -- 庫存不足                                       │  │
│  │  end                                                              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                   │                                    │
│                                   ▼                                    │
│  Layer 3: PostgreSQL 行級鎖                                            │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  • SELECT ... FOR UPDATE                                         │  │
│  │  • 事務隔離級別: SERIALIZABLE                                     │  │
│  │  • 二次驗證庫存數量                                               │  │
│  │  SQL:                                                             │  │
│  │  SELECT stock FROM products WHERE product_id = $1 FOR UPDATE;    │  │
│  │  UPDATE products SET stock = stock - 1 WHERE product_id = $1;    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                   │                                    │
│                                   ▼                                    │
│  Layer 4: 樂觀鎖版本號                                                  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  • version 欄位防止並發更新衝突                                    │  │
│  │  • 更新失敗則重試                                                  │  │
│  │  SQL:                                                             │  │
│  │  UPDATE products SET stock = stock - 1, version = version + 1    │  │
│  │  WHERE product_id = $1 AND version = $2 AND stock >= 1;          │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 訂單建立流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    防超賣訂單建立流程                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐                                                       │
│  │ 活動結束     │                                                       │
│  │ 開始結算     │                                                       │
│  └──────┬──────┘                                                       │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 1. 獲取 Top K 排名                                               │   │
│  │    ZREVRANGE bid:{campaign_id} 0 {K-1} WITHSCORES               │   │
│  └────────────────────────────┬────────────────────────────────────┘   │
│                               │                                        │
│                               ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 2. 對每位得標者 (排名 1 到 K)                                     │   │
│  │    ┌────────────────────────────────────────────────────────┐   │   │
│  │    │ 2.1 獲取分散式鎖                                        │   │   │
│  │    │     SET lock:product:{id} {uuid} NX EX 2               │   │   │
│  │    └────────────────────────────────────────────────────────┘   │   │
│  │                         │                                       │   │
│  │                         ▼                                       │   │
│  │    ┌────────────────────────────────────────────────────────┐   │   │
│  │    │ 2.2 Redis 原子扣減                                      │   │   │
│  │    │     DECR stock:{product_id}                            │   │   │
│  │    │     if 返回 < 0 → 回滾並跳過                            │   │   │
│  │    └────────────────────────────────────────────────────────┘   │   │
│  │                         │                                       │   │
│  │                         ▼                                       │   │
│  │    ┌────────────────────────────────────────────────────────┐   │   │
│  │    │ 2.3 PostgreSQL 事務                                     │   │   │
│  │    │     BEGIN;                                             │   │   │
│  │    │     SELECT ... FOR UPDATE;                             │   │   │
│  │    │     UPDATE products SET stock = stock - 1 ...;         │   │   │
│  │    │     INSERT INTO orders ...;                            │   │   │
│  │    │     COMMIT;                                            │   │   │
│  │    │     if 失敗 → Redis INCR 回滾                           │   │   │
│  │    └────────────────────────────────────────────────────────┘   │   │
│  │                         │                                       │   │
│  │                         ▼                                       │   │
│  │    ┌────────────────────────────────────────────────────────┐   │   │
│  │    │ 2.4 釋放分散式鎖                                        │   │   │
│  │    │     DEL lock:product:{id} (Lua: 只刪自己的鎖)           │   │   │
│  │    └────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                               │                                        │
│                               ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 3. 最終一致性驗證                                                │   │
│  │    • 訂單數量 ≤ 庫存 K                                          │   │
│  │    • 如發現不一致 → 觸發告警                                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.3 對賬機制

定時對賬確保 Redis 和 PostgreSQL 資料一致：

| 檢查項目 | 頻率 | 動作 |
|----------|------|------|
| Redis 庫存 vs DB 庫存 | 每小時 | 以 DB 為準修復 Redis |
| 訂單數量 vs 初始庫存 | 活動結束後 | 驗證無超賣 |
| 得標者 vs Top K | 活動結束後 | 驗證排名正確 |

---

## 6. API 設計

### 6.1 API 端點總覽

| 端點 | 方法 | 說明 | 認證 |
|------|------|------|------|
| `/api/v1/auth/register` | POST | 用戶註冊 | 否 |
| `/api/v1/auth/login` | POST | 用戶登入 | 否 |
| `/api/v1/auth/me` | GET | 獲取當前用戶 | 是 |
| `/api/v1/campaigns` | GET | 活動列表 | 否 |
| `/api/v1/campaigns/{id}` | GET | 活動詳情 | 否 |
| `/api/v1/campaigns` | POST | 建立活動（管理員） | 是 |
| `/api/v1/bids` | POST | 提交出價 | 是 |
| `/api/v1/bids/{campaign_id}/history` | GET | 出價歷史 | 是 |
| `/api/v1/rankings/{campaign_id}` | GET | 排名查詢 | 否 |
| `/api/v1/rankings/{campaign_id}/me` | GET | 我的排名 | 是 |
| `/api/v1/orders` | GET | 我的訂單 | 是 |
| `/ws` | WebSocket | 即時推播 | 是 |

### 6.2 核心 API 規格

#### POST /api/v1/bids（提交出價）

**Request:**
```json
{
  "campaign_id": "uuid-string",
  "price": 1500.00
}
```

**Response (201 Created):**
```json
{
  "bid_id": "uuid-string",
  "campaign_id": "uuid-string",
  "user_id": "uuid-string",
  "price": 1500.00,
  "score": 1723.45,
  "rank": 15,
  "time_elapsed_ms": 3500,
  "created_at": "2025-12-03T10:30:00Z"
}
```

**Error Responses:**
| 狀態碼 | 錯誤碼 | 說明 |
|--------|--------|------|
| 400 | PRICE_TOO_LOW | 出價低於底價 |
| 403 | CAMPAIGN_NOT_STARTED | 活動尚未開始 |
| 403 | CAMPAIGN_ENDED | 活動已結束 |
| 429 | RATE_LIMIT_EXCEEDED | 請求過於頻繁 |

#### GET /api/v1/rankings/{campaign_id}

**Response (200 OK):**
```json
{
  "campaign_id": "uuid-string",
  "total_participants": 1523,
  "rankings": [
    {
      "rank": 1,
      "user_id": "uuid-string",
      "username": "user_001",
      "score": 2523.75,
      "price": 2000.00
    },
    {
      "rank": 2,
      "user_id": "uuid-string",
      "username": "user_002",
      "score": 2401.50,
      "price": 1900.00
    }
  ],
  "min_winning_score": 1100.25,
  "max_score": 2523.75,
  "updated_at": "2025-12-03T10:30:00Z"
}
```

### 6.3 WebSocket 事件

**Client → Server:**
| 事件 | Payload | 說明 |
|------|---------|------|
| `join_campaign` | `{campaign_id}` | 加入活動房間 |
| `leave_campaign` | `{campaign_id}` | 離開活動房間 |

**Server → Client:**
| 事件 | Payload | 說明 |
|------|---------|------|
| `ranking_update` | `{top_k, total, min_score, max_score}` | 排名更新 |
| `bid_accepted` | `{bid_id, score, rank}` | 出價成功 |
| `campaign_ended` | `{is_winner, final_rank}` | 活動結束 |

### 6.4 錯誤回應格式

```json
{
  "error": {
    "code": "PRICE_TOO_LOW",
    "message": "出價金額必須高於底價 1000.00",
    "details": {
      "min_price": 1000.00,
      "submitted_price": 500.00
    },
    "timestamp": "2025-12-03T10:30:00Z",
    "request_id": "req-uuid-123"
  }
}
```

---

## 7. 可擴展性設計

### 7.1 水平擴展策略

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        水平擴展架構                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                    ┌─────────────────────────┐                          │
│                    │   Cloud Load Balancer   │                          │
│                    └───────────┬─────────────┘                          │
│                                │                                        │
│            ┌───────────────────┼───────────────────┐                   │
│            │                   │                   │                   │
│            ▼                   ▼                   ▼                   │
│     ┌────────────┐      ┌────────────┐      ┌────────────┐            │
│     │  Pod #1    │      │  Pod #2    │      │  Pod #N    │            │
│     │ Bidding    │      │ Bidding    │      │ Bidding    │            │
│     │ Service    │      │ Service    │      │ Service    │            │
│     └────────────┘      └────────────┘      └────────────┘            │
│            │                   │                   │                   │
│            └───────────────────┴───────────────────┘                   │
│                                │                                        │
│                    ┌───────────┴───────────┐                           │
│                    │                       │                           │
│                    ▼                       ▼                           │
│            ┌──────────────┐        ┌──────────────┐                    │
│            │ Memorystore  │        │  Cloud SQL   │                    │
│            │ (Redis)      │        │ (PostgreSQL) │                    │
│            │ HA Cluster   │        │ Multi-AZ     │                    │
│            └──────────────┘        └──────────────┘                    │
│                                                                         │
│  關鍵設計原則:                                                          │
│  • 無狀態服務: Session 存 Redis，任意 Pod 可處理任意請求                 │
│  • 服務發現: Kubernetes Service + DNS                                  │
│  • 共享存儲: 所有 Pod 連接同一個 Redis Cluster 和 Cloud SQL              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Auto-scaling 配置

**Horizontal Pod Autoscaler (HPA) 設定：**

| 服務 | Min Pods | Max Pods | CPU 閾值 | Memory 閾值 |
|------|----------|----------|----------|-------------|
| Bidding Service | 3 | 20 | 70% | 80% |
| Ranking Service | 2 | 10 | 70% | 80% |
| WebSocket Gateway | 3 | 15 | 60% | 70% |
| User Service | 2 | 8 | 70% | 80% |

**擴展行為：**
- **Scale Up**: CPU > 70% 持續 30 秒 → 增加 2 個 Pod
- **Scale Down**: CPU < 30% 持續 5 分鐘 → 減少 1 個 Pod
- **冷卻時間**: Scale Up 後 60 秒內不再擴展

### 7.3 負載均衡策略

| 層級 | 技術 | 演算法 | 說明 |
|------|------|--------|------|
| L7 | Cloud Load Balancing | Round Robin | HTTPS 終止、SSL 卸載 |
| L4 | Kubernetes Service | IP Hash | 內部服務通訊 |
| WebSocket | Cloud Load Balancing | Sticky Session | 維持長連接 |

### 7.4 資料庫擴展

**Cloud SQL (PostgreSQL):**
- 主從架構：1 Primary + 2 Read Replicas
- 自動故障轉移
- 讀寫分離：寫入 Primary，查詢 Replica

**Memorystore (Redis):**
- Redis Cluster 模式
- 3 分片，每分片 1 主 1 從
- 自動分片，支援線性擴展

---

## 8. 容器化與 GCP 雲端部署

### 8.1 GCP 服務架構

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         GCP 部署架構                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                         VPC Network                              │   │
│  │  ┌─────────────────────────────────────────────────────────┐    │   │
│  │  │                   Public Subnet                          │    │   │
│  │  │  ┌─────────────┐    ┌─────────────┐                     │    │   │
│  │  │  │ Cloud Load  │    │ Cloud CDN   │                     │    │   │
│  │  │  │ Balancing   │    │ (靜態資源)   │                     │    │   │
│  │  │  └──────┬──────┘    └─────────────┘                     │    │   │
│  │  └─────────┼────────────────────────────────────────────────┘    │   │
│  │            │                                                     │   │
│  │  ┌─────────┼────────────────────────────────────────────────┐    │   │
│  │  │         ▼             Private Subnet                      │    │   │
│  │  │  ┌─────────────────────────────────────────────────┐     │    │   │
│  │  │  │              GKE Cluster                         │     │    │   │
│  │  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐            │     │    │   │
│  │  │  │  │Node Pool│ │Node Pool│ │Node Pool│            │     │    │   │
│  │  │  │  │ (3節點)  │ │ (可擴展) │ │ (可擴展) │            │     │    │   │
│  │  │  │  └─────────┘ └─────────┘ └─────────┘            │     │    │   │
│  │  │  └─────────────────────────────────────────────────┘     │    │   │
│  │  │                          │                                │    │   │
│  │  │         ┌────────────────┴────────────────┐              │    │   │
│  │  │         │                                 │              │    │   │
│  │  │         ▼                                 ▼              │    │   │
│  │  │  ┌─────────────┐                   ┌─────────────┐       │    │   │
│  │  │  │ Cloud SQL   │                   │ Memorystore │       │    │   │
│  │  │  │ (PostgreSQL)│                   │ (Redis)     │       │    │   │
│  │  │  │ HA 配置     │                   │ HA 配置     │       │    │   │
│  │  │  └─────────────┘                   └─────────────┘       │    │   │
│  │  │                                                           │    │   │
│  │  │  ┌─────────────┐                   ┌─────────────┐       │    │   │
│  │  │  │ Cloud       │                   │ Cloud       │       │    │   │
│  │  │  │ Pub/Sub     │                   │ Storage     │       │    │   │
│  │  │  └─────────────┘                   └─────────────┘       │    │   │
│  │  └───────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.2 GCP 服務配置

| 服務 | 配置 | 說明 |
|------|------|------|
| **GKE** | e2-standard-4 (4 vCPU, 16GB) | 3 節點起，自動擴展至 10 節點 |
| **Cloud SQL** | db-custom-4-16384 | 4 vCPU, 16GB RAM, 500GB SSD |
| **Memorystore** | 6GB, Standard Tier | Redis 7.0, HA 配置 |
| **Cloud Pub/Sub** | 預設配置 | 自動擴展 |
| **Cloud Load Balancing** | Global HTTP(S) | SSL 終止, Cloud Armor |

### 8.3 Docker 容器設計

**多階段構建示意：**
```
Build Stage:
  • Python 3.11 base image
  • 安裝依賴 (requirements.txt)
  • 複製程式碼

Production Stage:
  • Python 3.11-slim base image
  • 從 Build Stage 複製虛擬環境
  • 非 root 用戶執行
  • 最終鏡像約 150MB
```

### 8.4 CI/CD 流程

```
┌─────────────────────────────────────────────────────────────────┐
│                       CI/CD Pipeline                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐      │
│  │  Push   │───>│  Build  │───>│  Test   │───>│  Push   │      │
│  │  Code   │    │  Image  │    │  Unit   │    │  to     │      │
│  │         │    │         │    │  E2E    │    │ Artifact│      │
│  │         │    │         │    │         │    │ Registry│      │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘      │
│                                                    │            │
│                                                    ▼            │
│                                    ┌──────────────────────────┐ │
│                                    │     Deploy to GKE        │ │
│                                    │  • Rolling Update        │ │
│                                    │  • Health Check          │ │
│                                    │  • Rollback if failed    │ │
│                                    └──────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**環境分離：**
| 環境 | 用途 | GKE Namespace |
|------|------|---------------|
| Development | 開發測試 | dev |
| Staging | 預發布測試 | staging |
| Production | 正式環境 | prod |

---

## 9. 監控與可觀測性

### 9.1 監控指標

**系統指標：**
| 指標 | 來源 | 告警閾值 |
|------|------|----------|
| CPU 使用率 | GKE | > 80% 持續 5 分鐘 |
| Memory 使用率 | GKE | > 85% |
| Pod 重啟次數 | GKE | > 3 次/小時 |
| 網路延遲 | Cloud Monitoring | P95 > 500ms |

**業務指標：**
| 指標 | 說明 | 告警閾值 |
|------|------|----------|
| 出價成功率 | 成功出價 / 總出價請求 | < 99% |
| 出價回應時間 | P95 延遲 | > 2 秒 |
| 排名更新延遲 | 出價到排名更新的時間 | > 5 秒 |
| WebSocket 連接數 | 當前活躍連接 | 監控用 |
| 訂單 vs 庫存 | 訂單數 / 庫存數 | > 100% (超賣告警) |

### 9.2 日誌收集

**結構化日誌格式：**
```json
{
  "timestamp": "2025-12-03T10:30:00.123Z",
  "level": "INFO",
  "service": "bidding-service",
  "trace_id": "abc123",
  "user_id": "user-456",
  "campaign_id": "camp-789",
  "action": "process_bid",
  "price": 1500.00,
  "score": 1723.45,
  "duration_ms": 45,
  "status": "success"
}
```

**日誌級別：**
| 級別 | 用途 |
|------|------|
| ERROR | 錯誤、異常 |
| WARN | 警告、異常流程 |
| INFO | 關鍵業務操作 |
| DEBUG | 詳細調試（僅開發環境） |

### 9.3 告警機制

| 告警名稱 | 條件 | 通知管道 |
|----------|------|----------|
| High CPU | CPU > 80% 持續 5 分鐘 | Slack + Email |
| High Error Rate | 5xx 錯誤率 > 1% | Slack + PagerDuty |
| Overselling Alert | 訂單數 > 庫存數 | PagerDuty (Critical) |
| High Latency | P95 > 2 秒 | Slack |
| Pod CrashLoop | 重啟 > 3 次/小時 | Slack |

### 9.4 Dashboard 設計

**監控儀表板包含：**
1. **系統健康總覽**: Pod 狀態、CPU/Memory、網路
2. **業務指標**: 出價量、活躍用戶、WebSocket 連接數
3. **活動即時看板**: 當前進行中活動的排名、參與人數
4. **錯誤追蹤**: 錯誤率趨勢、錯誤類型分佈

---

## 10. 壓力測試設計

### 10.1 測試工具

- **主要工具**: k6 (Grafana Labs)
- **輔助工具**: Locust (Python)
- **監控**: Cloud Monitoring + Grafana

### 10.2 測試場景

| 場景 | 用戶數 | 持續時間 | 目標 |
|------|--------|----------|------|
| **基準測試** | 100 | 5 分鐘 | 建立性能基線 |
| **高並發測試** | 1000+ | 10 分鐘 | 驗證並發處理能力 |
| **指數型負載** | 100→2000 | 10 分鐘 | 模擬截止時間接近 |
| **持久測試** | 500 | 30 分鐘 | 驗證系統穩定性 |

### 10.3 指數型出價頻率模擬

**核心需求** (PDF 原文): 「隨著截止時間接近，更新出價的頻率須呈現**指數型成長**」

這是指**每位用戶的出價頻率**要指數增長，而非只是 VU 數量增加。

```
┌─────────────────────────────────────────────────────────────────┐
│                   指數型出價頻率曲線                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  每 VU                                                          │
│  出價頻率                                           ┌──────────┐ │
│  (req/min)                                       ╱  │ Phase 3  │ │
│    │                                           ╱    │ 1200     │ │
│ 1200│                                       ╱      │ req/min  │ │
│    │                                     ╱         │ per VU   │ │
│  900│                                 ╱            └──────────┘ │
│    │                             ╱──                            │
│  600│                       ╱──                                 │
│    │                  ╱──                                       │
│  300│           ╱──                                             │
│    │      ╱──                                                   │
│   30│─────                                                      │
│    │ Phase 1        Phase 2         Phase 3                     │
│    └────────────────────────────────────────────────────────>   │
│      0-40%         40-70%          70-100%     活動進度比例       │
│                                                                 │
│  實現方式:                                                       │
│  • Phase 1 (0-40%):  sleep=2s    → ~30 req/min per VU          │
│  • Phase 2 (40-70%): sleep=0.5s  → ~120 req/min per VU         │
│  • Phase 3 (70-100%): sleep=0.05s → ~1200 req/min per VU       │
│                                                                 │
│  關鍵公式 (動態 sleep 時間指數衰減):                              │
│  sleep = baseSleep × e^(-k × elapsedRatio)                     │
│  其中 baseSleep=2.0, k=5                                        │
│                                                                 │
│  驗證: Phase 3 請求量 ≥ 3x 平均值                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 10.4 驗證指標

| 指標 | 目標值 | 說明 |
|------|--------|------|
| **成功率** | > 99% | 出價請求成功比例 |
| **P95 延遲** | < 2 秒 | 95% 請求在 2 秒內完成 |
| **P99 延遲** | < 5 秒 | 99% 請求在 5 秒內完成 |
| **排名更新延遲** | < 5 秒 | 出價後排名反映時間 |
| **超賣率** | 0% | 絕對不允許超賣 |
| **系統可用性** | > 99.5% | 測試期間服務可用時間 |

### 10.5 一致性驗證 (防超賣)

**PDF 需求**: 「在大量並發結束後，展示資料庫結果，證明沒有超賣（成交數≦庫存數）」

**驗證方式**:
1. 壓力測試完成後執行 `verify-consistency.js`
2. 以管理員身份查詢活動訂單數
3. 比對原始庫存數 K
4. 輸出驗證報告

**驗證指標**:
| 項目 | 目標 | 說明 |
|------|------|------|
| 訂單數 ≤ 庫存數 | 100% 通過 | 絕對不允許超賣 |

**API 端點**:
```
GET /api/v1/orders/campaign/{campaign_id}  (管理員權限)

Response:
{
  "campaign_id": "uuid",
  "orders": [...],
  "total": 10,
  "stock": 10,
  "is_consistent": true  // total <= stock
}
```

### 10.6 測試報告內容

1. **測試環境**: GKE 配置、資料庫配置
2. **測試數據**: 請求總數、成功/失敗數、延遲分佈
3. **資源使用**: CPU、Memory、網路峰值
4. **自動擴展**: Pod 數量變化、擴展時間
5. **指數型成長驗證**: Phase 3 請求量倍數
6. **一致性驗證**: 最終訂單數 vs 庫存數

---

## 11. 安全性考量

### 11.1 認證授權

**JWT Token 機制：**
- **簽名演算法**: RS256 (非對稱加密)
- **Access Token 有效期**: 15 分鐘
- **Refresh Token 有效期**: 7 天
- **Token 存儲**: HttpOnly Cookie (XSS 防護)

**角色權限 (RBAC)：**
| 角色 | 權限 |
|------|------|
| User | 查看活動、出價、查看自己訂單 |
| Admin | 建立活動、設定參數、查看所有訂單、監控 |

### 11.2 防止惡意請求

| 防護措施 | 說明 |
|----------|------|
| **Rate Limiting** | 用戶 10 req/s, IP 100 req/s |
| **Cloud Armor** | GCP WAF, DDoS 防護 |
| **請求驗證** | 檢查價格範圍、必填欄位 |
| **CAPTCHA** | 可疑行為觸發驗證碼 |
| **IP 黑名單** | 異常 IP 自動封鎖 |

### 11.3 數據安全

| 項目 | 措施 |
|------|------|
| **密碼存儲** | bcrypt 雜湊 (cost=12) |
| **傳輸加密** | HTTPS (TLS 1.3) |
| **資料庫加密** | Cloud SQL 靜態加密 |
| **敏感資料** | 遮罩處理 (如部分 email) |
| **日誌脫敏** | 不記錄密碼、Token |

### 11.4 安全審計

- **存取日誌**: 記錄所有 API 請求
- **管理操作日誌**: 記錄管理員操作
- **異常登入偵測**: 多次失敗嘗試告警
- **定期安全掃描**: 依賴套件漏洞檢查

---

## 附錄

### A. 名詞解釋

| 名詞 | 說明 |
|------|------|
| **Score** | 競標積分，由公式 α·P + β/(T+1) + γ·W 計算 |
| **Top K** | 排名前 K 名的暫定得標者 |
| **T (Time)** | 反應時間，從活動開始到出價的毫秒數 |
| **W (Weight)** | 會員權重，代表等級或貢獻度 |
| **超賣 (Overselling)** | 訂單數超過庫存數的錯誤情況 |

### B. 參考指標

| 指標 | 目標值 |
|------|--------|
| 並發用戶支援 | ≥ 1000 |
| 出價回應時間 (P95) | < 2 秒 |
| 排名更新延遲 | < 5 秒 |
| 超賣容忍度 | 0% |
| 系統可用性 | > 99.5% |

---

## 文件版本

| 版本 | 日期 | 修改內容 |
|------|------|----------|
| 1.0 | 2025-12-03 | 初版建立 |
