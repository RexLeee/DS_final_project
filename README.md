# Real-time Bidding & Flash Sale System

即時競標與限時搶購系統 - 分散式系統與雲端應用開發實務期末專案

一個專為高並發場景設計的即時競標系統，支援 1000+ 並發用戶，提供毫秒級的出價處理與即時排名更新。

---

## 目錄

- [系統簡介與架構圖](#系統簡介與架構圖)
- [核心技術說明](#核心技術說明)
- [使用的平台、工具、套件](#使用的平台工具套件)
- [Scalability 設計](#scalability-設計)
- [系統測試設計與壓力測試數據](#系統測試設計與壓力測試數據)
- [系統的容錯能力](#系統的容錯能力)

---

## 系統簡介與架構圖

### 系統簡介

本系統為即時競標與限時搶購平台，核心功能包括：
- **即時競標**：用戶可對商品出價，系統即時計算排名
- **限時搶購**：活動結束時，排名前 K 名用戶自動成為得標者
- **庫存保護**：四層防超賣機制確保庫存一致性

### 高層架構圖

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Client Layer                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                     React 18 + TypeScript + Vite                         │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │    │
│  │  │ AuthCtx  │  │ BidForm  │  │ Ranking  │  │WebSocket │  │ Countdown│   │    │
│  │  │ Provider │  │Component │  │  Board   │  │  Hook    │  │  Timer   │   │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │ HTTP/WebSocket
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Load Balancer Layer                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │              GCP Ingress (Static IP + Container-Native LB)               │    │
│  │   /api/* ──► Backend Service      /* ──► Frontend Service               │    │
│  │   /ws/*  ──► Backend Service      /health ──► Backend Service           │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Application Layer                                      │
│  ┌───────────────────────────────────┐  ┌────────────────────────────────────┐  │
│  │         Backend Service           │  │        Frontend Service            │  │
│  │     (FastAPI + Uvicorn + uvloop)  │  │       (Nginx + Static Files)       │  │
│  │                                   │  │                                    │  │
│  │  ┌─────────────────────────────┐  │  │  Replicas: 1-5 (HPA)              │  │
│  │  │      Middleware Layer       │  │  │  Resources: 50m-150m CPU          │  │
│  │  │  • Rate Limiter (Lua)       │  │  └────────────────────────────────────┘  │
│  │  │  • Prometheus Metrics       │  │                                          │
│  │  │  • CORS Handler             │  │                                          │
│  │  └─────────────────────────────┘  │                                          │
│  │                                   │                                          │
│  │  ┌─────────────────────────────┐  │                                          │
│  │  │      Service Layer          │  │                                          │
│  │  │  • BidService (出價邏輯)    │  │                                          │
│  │  │  • RedisService (快取排名)  │  │                                          │
│  │  │  • InventoryService (庫存)  │  │                                          │
│  │  │  • SettlementService (結算) │  │                                          │
│  │  │  • WebSocketManager (推播)  │  │                                          │
│  │  └─────────────────────────────┘  │                                          │
│  │                                   │                                          │
│  │  Replicas: 5-50 (HPA)            │                                          │
│  │  Resources: 200m-400m CPU         │                                          │
│  └───────────────────────────────────┘                                          │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
┌───────────────────────┐ ┌─────────────────┐ ┌─────────────────────────────────┐
│   Connection Pooler   │ │   Cache Layer   │ │        Database Layer           │
│                       │ │                 │ │                                 │
│  ┌─────────────────┐  │ │  ┌───────────┐  │ │  ┌─────────────────────────┐   │
│  │    PgBouncer    │  │ │  │   Redis   │  │ │  │     Cloud SQL           │   │
│  │   (6 Replicas)  │  │ │  │ Memorystore│ │ │  │    PostgreSQL 15        │   │
│  │                 │  │ │  │           │  │ │  │                         │   │
│  │ • Transaction   │  │ │  │ • Sorted  │  │ │  │ • Users Table           │   │
│  │   Mode          │  │ │  │   Sets    │  │ │  │ • Products Table        │   │
│  │ • 2000 Client   │  │ │  │   (排名)  │  │ │  │ • Campaigns Table       │   │
│  │   Connections   │  │ │  │ • Hash    │  │ │  │ • Bids Table            │   │
│  │ • 30 DB Conn    │  │ │  │   (快取)  │  │ │  │ • Orders Table          │   │
│  │   per Instance  │  │ │  │ • Lua     │  │ │  │                         │   │
│  │ • 180 Total DB  │  │ │  │  Scripts  │  │ │  │ max_connections: 200    │   │
│  │   Connections   │  │ │  │   (原子)  │  │ │  └─────────────────────────┘   │
│  └─────────────────┘  │ │  └───────────┘  │ │                                 │
└───────────────────────┘ └─────────────────┘ └─────────────────────────────────┘
```

### 資料流程圖

#### 出價流程 (Bidding Flow)

```
┌────────┐    HTTP POST     ┌──────────────┐    Validate    ┌─────────────┐
│ Client │ ───────────────► │   Backend    │ ─────────────► │ Redis Cache │
│        │                  │ Rate Limiter │                │ (Campaign)  │
└────────┘                  └──────────────┘                └─────────────┘
                                   │                               │
                                   │ Calculate Score               │ Cache Hit
                                   ▼                               ▼
                            ┌──────────────┐    UPSERT      ┌─────────────┐
                            │  BidService  │ ─────────────► │ PostgreSQL  │
                            │ Score=α×P+   │                │   (Bids)    │
                            │ β/(T+1)+γ×W  │                └─────────────┘
                            └──────────────┘
                                   │
                                   │ Pipeline (3 ops → 1 RTT)
                                   ▼
                            ┌──────────────┐    Broadcast   ┌─────────────┐
                            │    Redis     │ ─────────────► │  WebSocket  │
                            │ Sorted Set   │                │   Manager   │
                            │  (Rankings)  │                └─────────────┘
                            └──────────────┘                       │
                                                                   │
                                   ┌───────────────────────────────┘
                                   │ bid_accepted event
                                   ▼
                            ┌─────────────┐
                            │   Client    │
                            │ (Real-time) │
                            └─────────────┘
```

#### 結算流程 (Settlement Flow)

```
┌─────────────────┐   Every 10s   ┌──────────────────┐
│ Settlement Loop │ ────────────► │ Query Campaigns  │
│ (Background)    │               │ status='active'  │
└─────────────────┘               │ end_time < now   │
                                  └──────────────────┘
                                          │
                                          ▼
                                  ┌──────────────────┐
                                  │ Get Top K from   │
                                  │ Redis Sorted Set │
                                  └──────────────────┘
                                          │
                   ┌──────────────────────┼──────────────────────┐
                   │                      │                      │
                   ▼                      ▼                      ▼
            ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
            │  Winner #1  │        │  Winner #2  │        │  Winner #K  │
            └─────────────┘        └─────────────┘        └─────────────┘
                   │                      │                      │
                   └──────────────────────┼──────────────────────┘
                                          │
                                          ▼
                          ┌───────────────────────────────┐
                          │    Four-Layer Protection      │
                          │                               │
                          │ Layer 1: Redis 分散式鎖       │
                          │ Layer 2: Redis 原子扣減       │
                          │ Layer 3: PostgreSQL 行級鎖    │
                          │ Layer 4: 樂觀鎖 (version)     │
                          └───────────────────────────────┘
                                          │
                                          ▼
                          ┌───────────────────────────────┐
                          │      Create Order Records     │
                          │   Broadcast campaign_ended    │
                          └───────────────────────────────┘
```

---

## 核心技術說明

### 1. 如何處理高並發的寫入（大量的出價更新）？

#### 1.1 PostgreSQL UPSERT 原子操作

每位用戶每場活動僅一筆有效出價，使用 `INSERT ... ON CONFLICT DO UPDATE` 實現原子性更新：

```python
# backend/src/app/services/bid_service.py
stmt = pg_insert(Bid).values(
    bid_id=uuid.uuid4(),
    campaign_id=campaign_id,
    user_id=user.user_id,
    price=price,
    score=Decimal(str(score)),
)

# 衝突時更新現有出價（基於唯一索引 campaign_id + user_id）
stmt = stmt.on_conflict_do_update(
    index_elements=['campaign_id', 'user_id'],
    set_={
        'price': price,
        'score': Decimal(str(score)),
        'bid_number': Bid.bid_number + 1,  # 追蹤出價次數
    }
).returning(Bid)
```

**優勢**：單一 SQL 語句完成檢查+插入/更新，消除競態條件。

#### 1.2 Redis Pipeline 批次處理

將多個 Redis 操作合併為單一網路來回（RTT），減少 40-60% 延遲：

```python
# backend/src/app/services/redis_service.py
async def update_ranking_and_get_rank(self, campaign_id, user_id, score, price, username):
    """將 ZADD + HSET + ZREVRANK 合併為單一 Pipeline 調用"""
    pipe = self.redis.pipeline()
    pipe.zadd(f"bid:{campaign_id}", {user_id: score})
    pipe.hset(f"bid_details:{campaign_id}:{user_id}", mapping={"price": str(price), "username": username})
    pipe.zrevrank(f"bid:{campaign_id}", user_id)
    results = await pipe.execute()
    return results[-1] + 1 if results[-1] is not None else None
```

#### 1.3 Lua 腳本原子操作

速率限制使用 Lua 腳本將 4+ 操作合併為 1 次原子調用：

```lua
-- backend/src/app/middleware/rate_limit.py
-- 滑動窗口速率限制（原子執行）
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)  -- 移除過期請求
local count = redis.call('ZCARD', key)                 -- 計算窗口內請求數

if count < limit then
    redis.call('ZADD', key, now, ARGV[4])              -- 記錄新請求
    redis.call('EXPIRE', key, window + 1)
    return {1, 0}  -- 允許
else
    return {0, retry_after}  -- 拒絕
end
```

#### 1.4 連線池架構

```
┌─────────────────────────────────────────────────────────────────┐
│                    連線池架構                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Backend Pods (最多 50 個)                                       │
│  └── SQLAlchemy AsyncEngine                                     │
│      └── pool_size=8, max_overflow=15 → 每 Pod 最多 23 連線     │
│                                                                  │
│  PgBouncer (6 Replicas)                                         │
│  └── Transaction Mode (支援 UPSERT)                             │
│  └── max_client_conn=2000                                        │
│  └── max_db_connections=30/pod → 共 180 DB 連線                  │
│                                                                  │
│  Cloud SQL PostgreSQL                                            │
│  └── max_connections=200                                         │
│                                                                  │
│  連線複用比: 1150:180 = 6.4:1                                    │
└─────────────────────────────────────────────────────────────────┘
```

#### 1.5 速率限制配置

| 層級 | 限制 | 說明 |
|------|------|------|
| User | 100 req/s | 每位登入用戶的請求限制 |
| IP | 10,000 req/s | 每個 IP 的請求限制 |

---

### 2. 如何計算並推播即時排名？

#### 2.1 計分公式

```
Score = α × P + β / (T + 1) + γ × W
```

#### 2.2 參數說明

| 參數 | 說明 | 預設值 | 範圍 |
|------|------|--------|------|
| **P** | 出價金額 | 用戶輸入 | ≥ min_price |
| **T** | 活動開始後經過的毫秒數 | 系統計算 | ≥ 0 |
| **W** | 會員權重 | 註冊時隨機分配 | 0.5 - 5.0 |
| **K** | 活動商品庫存（得標名額） | 活動設定 | ≥ 1 |
| **α (alpha)** | 價格權重係數 | 1.0000 | 可調整 |
| **β (beta)** | 時間權重係數 | 1000.0000 | 可調整 |
| **γ (gamma)** | 會員權重係數 | 100.0000 | 可調整 |

#### 2.3 分數計算實現

```python
# backend/src/app/services/bid_service.py
def calculate_score(price, time_elapsed_ms, weight, alpha, beta, gamma) -> float:
    """
    計分公式: Score = α·P + β/(T+1) + γ·W

    設計理念:
    • 越高的出價 → 越高的分數
    • 越早出價 → 越高的分數（時間衰減）
    • 越高的會員等級 → 越高的分數
    """
    return float(alpha * price + beta / (time_elapsed_ms + 1) + gamma * weight)
```

#### 2.4 Redis Sorted Set 排名機制

```
┌─────────────────────────────────────────┐
│ Key: bid:{campaign_id}                  │
├─────────────────────────────────────────┤
│ Score (分數)  │ Member (user_id)        │
├───────────────┼─────────────────────────┤
│ 15000.50     │ uuid-user-1             │  ← Rank #1
│ 14800.25     │ uuid-user-2             │  ← Rank #2
│ 14500.00     │ uuid-user-3             │  ← Rank #3
│ ...          │ ...                     │
│ 12000.00     │ uuid-user-K             │  ← Rank #K (最後得標者)
└───────────────┴─────────────────────────┘

操作複雜度:
• ZADD (更新分數): O(log N)
• ZREVRANGE (取 Top K): O(log N + K)
• ZREVRANK (取排名): O(log N)
• ZCARD (總人數): O(1)
```

#### 2.5 WebSocket 即時推播

```python
# backend/src/app/services/ws_manager.py
class ConnectionManager:
    """Room-based WebSocket 連線管理"""
    # 結構: {campaign_id: {user_id: WebSocket}}
    active_connections: dict[str, dict[str, WebSocket]] = {}
```

**廣播間隔與事件類型**：

| 事件類型 | 觸發時機 | 間隔 |
|----------|----------|------|
| `ranking_update` | 定時廣播 Top K 排名 | 每 **2 秒** |
| `bid_accepted` | 用戶出價成功時立即推送 | 即時 |
| `campaign_ended` | 活動結算完成時 | 即時 |

**排名廣播資料結構**：
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

### 3. 如何保證庫存一致性？

#### 3.1 四層防超賣機制

| 層級 | 機制 | 實現 | 保護目的 |
|------|------|------|----------|
| **Layer 1** | Redis 分散式鎖 | `SET lock:product:{id} {uuid} NX EX 2` | 確保同一時間只有一個請求可操作庫存 |
| **Layer 2** | Redis 原子扣減 | Lua Script: `GET` + `DECR` 原子執行 | 單一操作保證原子性 |
| **Layer 3** | PostgreSQL 行級鎖 | `SELECT ... FOR UPDATE` | 鎖定該行，防止並發讀寫 |
| **Layer 4** | 樂觀鎖 | `UPDATE ... WHERE version = ?` | 版本號檢查，確保無並發衝突 |

#### 3.2 Layer 1: Redis 分散式鎖

```python
# backend/src/app/services/redis_service.py
async def acquire_lock(self, product_id: str, owner_id: str, ttl: int = 2):
    """獲取分散式鎖，TTL=2秒防止死鎖"""
    key = f"lock:product:{product_id}"
    acquired = await self.redis.set(key, owner_id, nx=True, ex=ttl)
    return acquired is not None
```

#### 3.3 Layer 2: Redis 原子扣減 (Lua Script)

```lua
-- backend/src/app/services/redis_service.py
local stock = tonumber(redis.call("GET", KEYS[1]))
if stock and stock >= 1 then
    return redis.call("DECR", KEYS[1])  -- 扣減成功，返回新庫存
else
    return -1  -- 庫存不足
end
```

#### 3.4 Layer 3 & 4: PostgreSQL 行級鎖 + 樂觀鎖

```python
# backend/src/app/services/inventory_service.py
async def _db_decrement_with_lock(self, product_id: UUID):
    # Layer 3: SELECT FOR UPDATE (行級鎖)
    result = await self.db.execute(
        select(Product).where(Product.product_id == product_id).with_for_update()
    )
    product = result.scalar_one()

    current_version = product.version

    # Layer 4: 樂觀鎖版本檢查
    result = await self.db.execute(
        update(Product)
        .where(Product.product_id == product_id)
        .where(Product.version == current_version)  # 版本檢查
        .where(Product.stock >= 1)
        .values(stock=Product.stock - 1, version=Product.version + 1)
    )

    if result.rowcount == 0:
        raise ConcurrencyError("Concurrent update conflict")
```

#### 3.5 完整保護流程

```python
# backend/src/app/services/inventory_service.py
async def decrement_stock_with_protection(self, product_id: UUID):
    """四層保護的庫存扣減"""

    # Layer 1: 獲取分散式鎖
    acquired, owner_id = await self.redis_service.acquire_lock(product_id)
    if not acquired:
        return False

    try:
        # Layer 2: Redis 原子扣減
        new_stock = await self.redis_service.decrement_stock(product_id)
        if new_stock < 0:
            return False

        try:
            # Layer 3 & 4: PostgreSQL 保護
            await self._db_decrement_with_lock(product_id)
            return True
        except (InsufficientStockError, ConcurrencyError):
            # 回滾 Redis 庫存
            await self.redis_service.increment_stock(product_id)
            return False
    finally:
        # 釋放分散式鎖
        await self.redis_service.release_lock(product_id, owner_id)
```

#### 3.6 安全鎖釋放 (Owner 驗證)

```lua
-- 只有鎖的擁有者才能釋放
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0  -- 非擁有者，拒絕釋放
end
```

---

## 使用的平台、工具、套件

### 後端技術

| 技術 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 主程式語言 |
| FastAPI | Latest | Web API 框架、自動 OpenAPI 文檔 |
| Uvicorn | Latest | ASGI 伺服器 |
| uvloop | Latest | 高效能事件循環（2-3x 效能提升）|
| httptools | Latest | 高效能 HTTP 解析器 |
| SQLAlchemy | 2.0+ | 非同步 ORM |
| asyncpg | Latest | PostgreSQL 非同步驅動 |
| redis-py | Latest | Redis 非同步客戶端 |
| Pydantic | 2.0+ | 資料驗證與序列化 |
| PyJWT | Latest | JWT 編碼/解碼 |
| passlib | Latest | 密碼雜湊 (bcrypt) |

### 前端技術

| 技術 | 版本 | 用途 |
|------|------|------|
| React | 18+ | UI 框架 |
| TypeScript | 5.6+ | 靜態型別檢查 |
| Vite | 6.0+ | 建置工具 |
| Tailwind CSS | 4.0+ | CSS 框架 |
| Axios | Latest | HTTP 客戶端 |
| React Router | 7+ | 路由管理 |

### 資料庫與快取

| 技術 | 版本 | 用途 |
|------|------|------|
| PostgreSQL | 15 | 主資料庫（ACID、UPSERT） |
| Redis | 7 | 快取、排名、分散式鎖 |
| PgBouncer | Latest | 連線池代理（Transaction Mode）|

### 基礎設施

| 技術 | 用途 |
|------|------|
| GKE Autopilot | Kubernetes 容器編排 |
| Cloud SQL | 託管 PostgreSQL |
| Memorystore | 託管 Redis |
| Docker | 容器化 |
| Nginx | 前端靜態檔案伺服 |

### 測試工具

| 技術 | 用途 |
|------|------|
| k6 | 負載測試 |
| pytest | 單元測試 |

---

## Scalability 設計

### HPA 自動擴展配置

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  minReplicas: 5         # 預留基礎容量
  maxReplicas: 50        # 大規模擴展上限
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          averageUtilization: 50    # 低閾值快速觸發
    - type: Resource
      resource:
        name: memory
        target:
          averageUtilization: 70
```

### 擴展行為策略

| 動作 | 策略 | 說明 |
|------|------|------|
| **Scale Up** | 無穩定窗口 | 立即擴展，應對閃購流量 |
| | 每 15 秒 +10 pods | 快速擴展 |
| | 或 +200% | 大幅擴展 |
| **Scale Down** | 5 分鐘穩定期 | 避免縮容抖動 |
| | 每 60 秒 -2 pods | 緩慢縮容 |

### 連線數學

```
Backend 連線計算:
┌─────────────────────────────────────────┐
│ Backend Pods: 最多 50 個                │
│ 每個 Pod: pool_size=8, max_overflow=15  │
│ → 每 Pod 最多 23 連線                   │
│ → Backend 總連線: 50 × 23 = 1,150       │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ PgBouncer: 6 Replicas                   │
│ 每個: max_db_connections=30             │
│ → PgBouncer 總連線: 6 × 30 = 180        │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ Cloud SQL: max_connections=200          │
│                                         │
│ 連線複用比: 1,150 : 180 = 6.4 : 1       │
└─────────────────────────────────────────┘
```

### 流量暴增應對流程

```
1. 流量暴增 → CPU 使用率 > 50%
2. HPA 觸發 → 立即擴展（無穩定窗口）
3. 每 15 秒新增 10 pods（或 200%）
4. PgBouncer 連線池緩衝新增連線
5. 新 Pod 啟動並加入負載均衡
6. 系統容量擴展完成
```

---

## 系統測試設計與壓力測試數據

### 測試腳本

| 腳本 | 用途 | VUs |
|------|------|-----|
| `baseline.js` | 基準測試 | 100 |
| `high-concurrency.js` | 高並發測試 | 1000 |
| `exponential-load.js` | 指數增長測試 | 漸增 |
| `full-demo-test.js` | 完整演示測試 | ramping |
| `verify-consistency.js` | 資料一致性驗證 | 1 |

### High Concurrency Test 配置

```
測試階段:
├── Ramp-up (4 分鐘)
│   ├── 0 → 250 VUs (1 min)
│   ├── 250 → 500 VUs (1 min)
│   ├── 500 → 750 VUs (1 min)
│   └── 750 → 1000 VUs (1 min)
│
├── Sustain (5 分鐘)
│   └── 維持 1000 VUs（觀察 HPA 擴展）
│
└── Cooldown (1 分鐘)
    └── 1000 → 0 VUs
```

### 壓力測試數據

| 指標 | 目標值 | 實測值 |
|------|--------|--------|
| 並發用戶數 | 1000 VUs | (待補充) |
| P95 延遲 | < 2 秒 | (待補充) |
| 出價成功率 | > 80% | (待補充) |
| 失敗率 | < 20% | (待補充) |
| 庫存一致性 | orders ≤ stock | (待補充) |

### 一致性驗證

```bash
# 執行一致性驗證測試
k6 run -e CAMPAIGN_ID=<uuid> k6-tests/verify-consistency.js
```

驗證項目：
- ✅ 訂單數量 ≤ 商品庫存
- ✅ 無重複訂單（每用戶每活動最多一筆）
- ✅ 得標者為排名前 K 名

---

## 系統的容錯能力

### 容錯機制總覽

| 機制 | 實現 | 說明 |
|------|------|------|
| **背景任務重試** | 排名廣播: 2 秒 / 結算檢查: 10 秒 | 失敗時自動重試 |
| **Per-Campaign 錯誤隔離** | try-except per campaign | 單一活動失敗不影響其他活動 |
| **連線池健康檢查** | `pool_pre_ping=True` | 使用前驗證連線有效性 |
| **Redis 自動重連** | `retry_on_timeout=True` | 超時時自動重試 |
| **Lock TTL 防死鎖** | `EX 2` (2 秒過期) | 鎖自動過期，防止死鎖 |
| **Graceful Shutdown** | asyncio.CancelledError 處理 | 優雅關閉背景任務 |

### 背景任務錯誤處理

```python
# backend/src/app/main.py
async def ranking_broadcast_loop():
    while True:
        try:
            for campaign_id in active_campaigns:
                try:
                    # 每個活動獨立處理，錯誤不影響其他活動
                    await broadcast_ranking_update(campaign_id)
                except Exception as e:
                    logger.error(f"Campaign {campaign_id} broadcast failed: {e}")
                    # 繼續處理下一個活動

            await asyncio.sleep(2)
        except asyncio.CancelledError:
            break  # 優雅關閉
        except Exception as e:
            logger.error(f"Broadcast loop error: {e}")
            await asyncio.sleep(2)  # 重試
```

### 連線池容錯配置

```python
# Database (backend/src/app/core/database.py)
engine = create_async_engine(
    pool_pre_ping=True,      # 使用前驗證連線
    pool_recycle=180,        # 定期回收連線
    pool_timeout=30,         # 等待連線超時
)

# Redis (backend/src/app/core/redis.py)
redis_pool = ConnectionPool.from_url(
    retry_on_timeout=True,       # 超時自動重試
    health_check_interval=15,    # 定期健康檢查
    socket_timeout=10.0,         # Socket 超時
)
```

### 優雅降級策略

| 故障場景 | 降級行為 |
|----------|----------|
| Redis 不可用 | 速率限制跳過，允許請求通過 |
| DB 短暫不可用 | 結算任務下一週期重試 |
| WebSocket 斷開 | 客戶端自動重連 |
| Pod 異常終止 | Kubernetes 自動重啟 |

---

## 專案結構

```
flash-sale-system/
├── backend/                    # 後端服務
│   └── src/app/
│       ├── api/v1/            # API 路由
│       ├── core/              # 核心配置（DB、Redis、Security）
│       ├── middleware/        # 中介軟體（Rate Limit、Metrics）
│       ├── models/            # SQLAlchemy 資料模型
│       ├── schemas/           # Pydantic Schema
│       ├── services/          # 業務邏輯（Bid、Redis、Inventory、Settlement）
│       └── main.py            # 應用入口
│
├── frontend/                   # 前端應用
│   └── src/
│       ├── api/               # API 客戶端
│       ├── components/        # React 元件
│       ├── contexts/          # 狀態管理
│       ├── hooks/             # 自訂 Hooks（WebSocket、Countdown）
│       └── pages/             # 頁面元件
│
├── k8s/                        # Kubernetes 配置
│   ├── hpa.yaml               # 自動擴展
│   ├── pgbouncer-deployment.yaml
│   └── ...
│
├── k6-tests/                   # 負載測試腳本
│   ├── high-concurrency.js
│   └── verify-consistency.js
│
└── docker-compose.yml          # 本地開發環境
```
