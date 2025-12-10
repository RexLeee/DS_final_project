# 系統架構說明文件

本文件詳細介紹「限時搶購競標系統」所採用的各項技術架構及其設計原因。

---

## 目錄

1. [系統架構總覽](#1-系統架構總覽)
2. [後端框架：FastAPI + Uvicorn + uvloop](#2-後端框架fastapi--uvicorn--uvloop)
3. [資料庫：PostgreSQL + SQLAlchemy](#3-資料庫postgresql--sqlalchemy)
4. [快取與即時排名：Redis](#4-快取與即時排名redis)
   - [4.6 Redis vs PostgreSQL 資料分布](#46-redis-vs-postgresql-資料分布)
5. [連線池代理：PgBouncer](#5-連線池代理pgbouncer)
6. [容器編排：Kubernetes + HPA](#6-容器編排kubernetes--hpa)
7. [負載均衡：GCP Ingress](#7-負載均衡gcp-ingress)
8. [即時通訊：WebSocket](#8-即時通訊websocket)
9. [容器化：Docker 多階段構建](#9-容器化docker-多階段構建)
   - [9.4 系統映像總覽](#94-系統映像總覽)
10. [防超賣機制：四層防護](#10-防超賣機制四層防護)
11. [架構決策總結](#11-架構決策總結)

---

## 1. 系統架構總覽

### 1.1 架構圖

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              用戶端 (Client)                             │
│                       React 18 + TypeScript + Vite                      │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ HTTP / WebSocket
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       GCP Ingress (L7 負載均衡)                          │
│          /api/* → Backend    /ws/* → Backend    /* → Frontend          │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐      ┌───────────────┐       ┌───────────────┐
│ Backend Pods  │      │ Frontend Pods │       │   PgBouncer   │
│   (5-50 個)   │      │   (1-5 個)    │       │    (6 個)     │
│    FastAPI    │      │     Nginx     │       │    連線池     │
└───────┬───────┘      └───────────────┘       └───────┬───────┘
        │                                               │
        ├───────────────────────────────────────────────┤
        │                                               │
        ▼                                               ▼
┌─────────────────────────┐           ┌─────────────────────────┐
│   Memorystore (Redis)   │           │  Cloud SQL (PostgreSQL) │
│   快取 / 排名 / 鎖       │           │       持久化儲存        │
└─────────────────────────┘           └─────────────────────────┘
```

### 1.2 技術棧一覽

| 層級 | 技術 | 用途 |
|------|------|------|
| 前端 | React 18 + TypeScript + Vite | 使用者介面 |
| 後端 | FastAPI + Uvicorn + uvloop | API 服務 |
| 資料庫 | PostgreSQL 15 | 持久化儲存 |
| 快取 | Redis 7 | 排名、快取、分散式鎖 |
| 連線池 | PgBouncer | 資料庫連線複用 |
| 容器編排 | Kubernetes (GKE) | 自動擴展、部署管理 |
| 負載均衡 | GCP Ingress | 流量分發 |

---

## 2. 後端框架：FastAPI + Uvicorn + uvloop

### 2.1 元件說明

| 元件 | 角色 | 說明 |
|------|------|------|
| **FastAPI** | Web 框架 | Python 非同步 Web 框架，自動生成 OpenAPI 文檔 |
| **Uvicorn** | ASGI 伺服器 | 運行 FastAPI 應用的高效能伺服器 |
| **uvloop** | 事件循環 | 取代 Python 預設的 asyncio，效能提升 2-3 倍 |

### 2.2 為什麼選擇非同步框架？

#### 傳統同步框架的問題

```python
# Flask（同步框架）
def get_user():
    user = db.query(...)  # 阻塞等待資料庫回應
    return user           # 等待期間無法處理其他請求
```

當資料庫查詢需要 50ms 時，這個 Worker 在這 50ms 內完全閒置，無法處理其他請求。

#### 非同步框架的優勢

```python
# FastAPI（非同步框架）
async def get_user():
    user = await db.query(...)  # 等待時釋放控制權
    return user                  # 其他請求可以在等待期間被處理
```

**關鍵差異：** `await` 讓 Worker 在等待 I/O 時可以處理其他請求。

### 2.3 效能對比

| 框架類型 | 單 Worker 並發能力 | 適用場景 |
|----------|-------------------|----------|
| 同步（Flask） | ~10-20 請求/秒 | 低流量、CPU 密集 |
| 非同步（FastAPI） | ~500-1000 請求/秒 | 高並發、I/O 密集 |

### 2.4 本專案配置

```bash
# Uvicorn 啟動參數
uvicorn app.main:app \
  --workers 1 \           # 單 Worker（HPA 負責橫向擴展）
  --loop uvloop \         # 使用 uvloop 提升效能
  --http httptools \      # 使用 httptools 加速 HTTP 解析
  --limit-concurrency 150 # 限制單 Pod 並發數
```

---

## 3. 資料庫：PostgreSQL + SQLAlchemy

### 3.1 為什麼選擇 PostgreSQL？

| 特性 | 說明 | 本專案應用 |
|------|------|-----------|
| **ACID 交易** | 保證資料一致性 | 訂單創建、庫存扣減 |
| **UPSERT** | INSERT 或 UPDATE 原子操作 | 出價更新 |
| **行級鎖** | FOR UPDATE 鎖定特定行 | 防止並發修改同一筆資料 |
| **豐富索引** | B-tree、GIN、GiST | 加速查詢 |

### 3.2 UPSERT 原子操作

#### 問題場景

用戶可能在短時間內多次出價，傳統做法需要：
1. 查詢是否已有出價
2. 有則 UPDATE，無則 INSERT

這兩步之間可能發生競爭條件（Race Condition）。

#### 解決方案：UPSERT

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

# 單一 SQL 完成「有就更新，沒有就新增」
stmt = pg_insert(Bid).values(
    campaign_id=campaign_id,
    user_id=user_id,
    price=price,
    score=score,
)
stmt = stmt.on_conflict_do_update(
    index_elements=['campaign_id', 'user_id'],  # 唯一約束
    set_={
        'price': price,
        'score': score,
        'bid_number': Bid.bid_number + 1,
    }
)
await db.execute(stmt)
```

**優點：**
- 原子操作，無競爭條件
- 單一 SQL，減少資料庫往返
- 利用資料庫層級的唯一約束保證一致性

### 3.3 SQLAlchemy 2.0 非同步支援

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# 建立非同步引擎
engine = create_async_engine(
    "postgresql+asyncpg://...",
    pool_size=8,
    max_overflow=15,
    pool_pre_ping=True,  # 使用前檢查連線有效性
)

# 非同步查詢
async with AsyncSession(engine) as session:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
```

---

## 4. 快取與即時排名：Redis

### 4.1 Redis 在本專案的四大角色

```
┌─────────────────────────────────────────────────────────────────┐
│                         Redis 角色                               │
├─────────────┬─────────────┬─────────────┬─────────────────────────┤
│  即時排名    │   庫存管理   │  分散式鎖   │      快取層            │
│  (Ranking)  │ (Inventory) │   (Lock)    │     (Cache)            │
└─────────────┴─────────────┴─────────────┴─────────────────────────┘
```

### 4.2 角色一：即時排名系統

#### 為什麼不用 PostgreSQL 做排名？

```sql
-- PostgreSQL 排名查詢
SELECT user_id, score,
       RANK() OVER (ORDER BY score DESC) as rank
FROM bids
WHERE campaign_id = ?
ORDER BY score DESC
LIMIT 10;
```

**問題：** 每次查詢都需要全表掃描並排序，時間複雜度 O(N log N)。

#### Redis Sorted Set 解決方案

```python
# 更新排名：O(log N)
await redis.zadd(f"bid:{campaign_id}", {user_id: score})

# 查詢排名：O(log N)
rank = await redis.zrevrank(f"bid:{campaign_id}", user_id)

# 取得 Top 10：O(log N + 10)
top10 = await redis.zrevrange(f"bid:{campaign_id}", 0, 9, withscores=True)
```

#### 效能對比

| 操作 | PostgreSQL | Redis Sorted Set |
|------|------------|------------------|
| 更新排名 | O(N) 重建索引 | O(log N) |
| 查詢單人排名 | O(N log N) | O(log N) |
| 取得 Top K | O(N log N) | O(log N + K) |

**1000 人參與時：** Redis 比 PostgreSQL 快約 100 倍。

### 4.3 角色二：庫存管理（原子操作）

#### 問題：並發扣庫存

```
時間軸：
Client A: GET stock → 1
Client B: GET stock → 1
Client A: DECR → 0
Client B: DECR → -1  ❌ 超賣！
```

#### 解決方案：Lua Script

```lua
-- 原子扣庫存腳本
local stock = tonumber(redis.call("GET", KEYS[1]))
if stock and stock >= 1 then
    return redis.call("DECR", KEYS[1])  -- 庫存足夠，扣減
else
    return -1  -- 庫存不足，拒絕
end
```

**關鍵：** Lua Script 在 Redis 中是原子執行的，中間不會被其他操作打斷。

### 4.4 角色三：分散式鎖

#### 為什麼需要分散式鎖？

在多 Pod 環境下，需要確保同一商品的結算只被一個 Pod 執行。

#### 實現方式

```python
# 獲取鎖（原子操作）
# NX: 只有 key 不存在時才設定
# EX: 設定過期時間（防止死鎖）
acquired = await redis.set(
    f"lock:product:{product_id}",
    owner_id,
    nx=True,
    ex=2  # 2 秒後自動過期
)

# 釋放鎖（Lua Script 確保只有 owner 能釋放）
RELEASE_LOCK_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""
```

### 4.5 角色四：快取層

| Key Pattern | 內容 | TTL | 用途 |
|-------------|------|-----|------|
| `campaign:{id}` | 活動參數 | 無 | 避免每次出價都查 DB |
| `user:{id}` | 用戶資料 | 30 秒 | 快取用戶權重 |
| `bid_details:{campaign}:{user}` | 出價明細 | 無 | 排行榜顯示用 |

### 4.6 Redis vs PostgreSQL 資料分布

#### 只在 Redis（快取/暫存）

| Key Pattern | 資料結構 | 用途 | 生命週期 |
|-------------|----------|------|----------|
| `bid:{campaign_id}` | Sorted Set | 即時排名（user_id → score） | 活動結束後清理 |
| `bid_details:{campaign_id}:{user_id}` | Hash | 出價詳情（price, username） | 活動結束後清理 |
| `stock:{product_id}` | String | 即時庫存計數器 | 與 DB 同步 |
| `lock:product:{product_id}` | String | 分散式鎖 | TTL 2 秒自動過期 |
| `campaign:{campaign_id}` | Hash | 活動參數快取（alpha, beta, gamma） | 可設 TTL |
| `user:{user_id}` | Hash | 用戶資料快取 | TTL 30 秒 |

#### 只在 PostgreSQL（持久化）

| Table | 用途 |
|-------|------|
| `users` | 用戶帳號（email, password_hash, weight, is_admin） |
| `products` | 商品主檔（name, stock, min_price, version） |
| `campaigns` | 活動主檔（start_time, end_time, alpha/beta/gamma） |
| `orders` | 成交訂單（final_price, final_rank, status） |

#### 兩邊都有（雙寫）

| 資料 | Redis | PostgreSQL |
|------|-------|------------|
| **出價 (Bid)** | `bid:{campaign_id}` Sorted Set + `bid_details` Hash | `bids` 表（完整記錄） |
| **庫存** | `stock:{product_id}` 計數器 | `products.stock` 欄位 |

#### 資料流向圖

```
用戶出價
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                      Redis (熱資料)                      │
│  ┌─────────────────┐  ┌────────────────────────────┐   │
│  │ bid:{campaign}  │  │ bid_details:{campaign}:{user}│  │
│  │ (Sorted Set)    │  │ (Hash: price, username)      │  │
│  │ user_id → score │  └────────────────────────────┘   │
│  └─────────────────┘                                    │
│  ┌─────────────────┐  ┌─────────────────┐              │
│  │ stock:{product} │  │ lock:product:*  │              │
│  │ (計數器)        │  │ (分散式鎖)      │              │
│  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────┘
    │                              │
    │ 同步寫入                     │ 結算時讀取 Top-K
    ▼                              ▼
┌─────────────────────────────────────────────────────────┐
│                   PostgreSQL (冷資料)                    │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐     │
│  │ users   │ │ products │ │ campaigns│ │  bids   │     │
│  └─────────┘ └──────────┘ └──────────┘ └─────────┘     │
│                    │                         │          │
│                    │ 結算扣減 (四層防護)      │          │
│                    ▼                         ▼          │
│              ┌──────────┐              ┌─────────┐     │
│              │ orders   │◄─────────────│ Top-K   │     │
│              │ (成交單) │              │ 得標者  │     │
│              └──────────┘              └─────────┘     │
└─────────────────────────────────────────────────────────┘
```

#### 設計原則

| 原則 | 說明 |
|------|------|
| **Redis 負責即時性** | 排名查詢、庫存快速檢查、分散式鎖 |
| **PostgreSQL 負責持久性** | 訂單記錄、用戶資料、最終庫存 |
| **雙寫保一致** | 出價同時寫 Redis + PG，庫存扣減時四層防護確保一致 |
| **Redis 是 PG 的快取** | 活動參數、用戶資料可從 Redis 快取讀取 |
| **Redis 失敗可容忍** | 即使 Redis 出問題，PG 仍是最終 Source of Truth |

---

## 5. 連線池代理：PgBouncer

### 5.1 問題背景

```
Cloud SQL PostgreSQL 限制：max_connections = 200

Backend Pods 需求：
  50 Pods × 1 Worker × (pool_size=8 + max_overflow=15)
  = 50 × 23 = 1,150 連線

1,150 > 200 ❌ 無法直接連接
```

### 5.2 PgBouncer 解決方案

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Backend Pods   │     │    PgBouncer    │     │   PostgreSQL    │
│  (1,150 連線)   │ ──► │   (連線複用)    │ ──► │  (180 連線)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### 5.3 Transaction Mode 原理

```
傳統 Session Mode：
  每個 App 連線 = 一個 DB 連線（1:1）

Transaction Mode：
  App 連線只在「交易期間」佔用 DB 連線
  交易結束立即釋放給其他請求
```

**時間軸示意：**

```
App 連線 1: ──[交易A]────────────────[交易D]──────────
App 連線 2: ────────[交易B]──────────────────[交易E]──
App 連線 3: ──────────────[交易C]─────────────────────

                    ↓ PgBouncer 復用 ↓

DB 連線 1:  ──[A]───[B]───[C]───[D]───[E]────────────
```

### 5.4 本專案配置

```yaml
# k8s/pgbouncer-deployment.yaml
env:
  - name: POOL_MODE
    value: "transaction"       # 交易模式
  - name: MAX_CLIENT_CONN
    value: "2000"              # 最大客戶端連線
  - name: MAX_DB_CONNECTIONS
    value: "30"                # 每個 Pod 到 DB 的連線數
  # 6 Pods × 30 = 180 DB 連線
```

### 5.5 連線數計算

| 層級 | 計算 | 數量 |
|------|------|------|
| App 端最大連線 | 50 Pods × 23 | 1,150 |
| PgBouncer 到 DB | 6 Pods × 30 | 180 |
| Cloud SQL 限制 | - | 200 |
| **連線複用比** | 1,150 : 180 | **6.4 : 1** |

---

## 6. 容器編排：Kubernetes + HPA

### 6.1 為什麼需要 Kubernetes？

| 需求 | Kubernetes 解決方案 |
|------|---------------------|
| 高可用 | 多副本部署，自動重啟失敗的 Pod |
| 自動擴展 | HPA 根據 CPU/Memory 自動調整 Pod 數量 |
| 負載均衡 | Service 自動分發流量到各 Pod |
| 滾動更新 | 零停機部署新版本 |
| 資源管理 | 限制每個 Pod 的 CPU/Memory 使用 |

### 6.2 HPA（Horizontal Pod Autoscaler）

#### 工作原理

```
              監控指標
                 │
                 ▼
┌─────────────────────────────────┐
│             HPA                 │
│  if CPU > 50%: 擴展             │
│  if CPU < 50%: 縮減             │
└─────────────────────────────────┘
                 │
                 ▼
         調整 Pod 數量
```

#### 本專案配置

```yaml
# k8s/hpa.yaml - Backend HPA
spec:
  scaleTargetRef:
    name: backend
  minReplicas: 5          # 最少 5 個 Pod
  maxReplicas: 50         # 最多 50 個 Pod
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 50   # CPU 使用率閾值
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0   # 立即擴展
      policies:
        - type: Pods
          value: 10                    # 每次最多加 10 個
          periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300  # 5 分鐘穩定期
      policies:
        - type: Pods
          value: 2                     # 每次最多減 2 個
          periodSeconds: 60
```

#### 擴展策略說明

| 方向 | 策略 | 原因 |
|------|------|------|
| **擴展** | 快速（無穩定期） | 流量暴增時快速應對 |
| **縮減** | 緩慢（5 分鐘穩定期） | 避免流量波動導致頻繁縮放 |

### 6.3 資源配置

```yaml
# k8s/backend-deployment.yaml
resources:
  requests:
    cpu: "200m"      # 請求 0.2 核心
    memory: "256Mi"  # 請求 256MB 記憶體
  limits:
    cpu: "500m"      # 最多使用 0.5 核心
    memory: "512Mi"  # 最多使用 512MB 記憶體
```

---

## 7. 負載均衡：GCP Ingress

### 7.1 架構角色

```
Internet
    │
    ▼
┌─────────────────────────────────────┐
│         GCP Ingress                 │
│    (L7 HTTP/HTTPS 負載均衡)         │
│                                     │
│  路由規則：                          │
│  • /api/*  ──► Backend Service      │
│  • /ws/*   ──► Backend Service      │
│  • /*      ──► Frontend Service     │
└─────────────────────────────────────┘
    │
    ├──────────────┬──────────────┐
    ▼              ▼              ▼
 Backend       Backend        Frontend
  Pod 1         Pod 2          Pod 1
```

### 7.2 為什麼用 L7 負載均衡？

| 層級 | 功能 | 適用場景 |
|------|------|----------|
| **L4（TCP）** | 只看 IP:Port | 簡單分流 |
| **L7（HTTP）** | 可解析 URL、Header | 路徑分流、Header 路由 |

本專案需要根據 URL 路徑分流到不同服務，因此選擇 L7。

### 7.3 配置範例

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: flash-sale-ingress
  annotations:
    kubernetes.io/ingress.class: "gce"
    kubernetes.io/ingress.global-static-ip-name: "flash-sale-ip"
spec:
  rules:
    - http:
        paths:
          - path: /api/*
            pathType: ImplementationSpecific
            backend:
              service:
                name: backend
                port:
                  number: 8000
          - path: /ws/*
            pathType: ImplementationSpecific
            backend:
              service:
                name: backend
                port:
                  number: 8000
          - path: /*
            pathType: ImplementationSpecific
            backend:
              service:
                name: frontend
                port:
                  number: 80
```

---

## 8. 即時通訊：WebSocket

### 8.1 為什麼需要 WebSocket？

#### HTTP 輪詢的問題

```
Client: 排名更新了嗎？ ──► Server: 沒有
Client: 排名更新了嗎？ ──► Server: 沒有
Client: 排名更新了嗎？ ──► Server: 沒有
Client: 排名更新了嗎？ ──► Server: 有！更新資料
```

**問題：**
- 大量無效請求浪費頻寬
- 延遲取決於輪詢間隔
- 伺服器負載高

#### WebSocket 推播

```
Client ◄────────────────── Server: 連線建立
Client ◄────────────────── Server: 排名更新！
Client ◄────────────────── Server: 排名更新！
Client ◄────────────────── Server: 活動結束！
```

**優點：**
- 伺服器主動推送，零延遲
- 長連線，減少連線開銷
- 雙向通訊

### 8.2 本專案 WebSocket 事件

| 事件類型 | 觸發時機 | 推送內容 |
|----------|----------|----------|
| `ranking_update` | 每 2 秒 | Top K 排名列表 |
| `bid_accepted` | 出價成功 | 用戶當前排名 |
| `campaign_ended` | 活動結束 | 最終結果 |

### 8.3 Connection Manager 實現

```python
# backend/src/app/services/ws_manager.py
class ConnectionManager:
    def __init__(self):
        # 結構：{campaign_id: {user_id: WebSocket}}
        self.active_connections: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, campaign_id: str, user_id: str):
        await websocket.accept()
        if campaign_id not in self.active_connections:
            self.active_connections[campaign_id] = {}
        self.active_connections[campaign_id][user_id] = websocket

    async def broadcast_to_campaign(self, campaign_id: str, message: dict):
        if campaign_id in self.active_connections:
            for websocket in self.active_connections[campaign_id].values():
                await websocket.send_json(message)
```

### 8.4 背景廣播任務

```python
# backend/src/app/main.py
async def ranking_broadcast_loop():
    """每 2 秒廣播排名更新"""
    while True:
        try:
            # 取得所有進行中的活動
            active_campaigns = await get_active_campaigns()

            for campaign in active_campaigns:
                # 從 Redis 取得 Top K 排名
                rankings = await redis_service.get_top_k(campaign.id, k=10)

                # 廣播給該活動的所有連線用戶
                await ws_manager.broadcast_to_campaign(
                    campaign.id,
                    {"type": "ranking_update", "data": rankings}
                )
        except Exception as e:
            logger.error(f"Broadcast error: {e}")

        await asyncio.sleep(2)  # 每 2 秒執行一次
```

---

## 9. 容器化：Docker 多階段構建

### 9.1 為什麼用多階段構建？

#### 單階段構建的問題

```dockerfile
# 單階段：包含所有構建工具
FROM python:3.11
RUN pip install poetry
RUN poetry install
# 映像大小：~1.5GB（包含編譯器、開發工具等）
```

#### 多階段構建

```dockerfile
# 階段 1：構建環境
FROM python:3.11 AS builder
RUN pip install uv
COPY pyproject.toml .
RUN uv sync --frozen

# 階段 2：運行環境（只複製必要檔案）
FROM python:3.11-slim
COPY --from=builder /app/.venv /app/.venv
COPY ./src /app/src
# 映像大小：~300MB
```

**效果：** 映像從 1.5GB 縮小到 300MB，部署更快、更安全。

### 9.2 Backend Dockerfile

```dockerfile
# backend/Dockerfile
# ===== Build Stage =====
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY ./src ./src

# ===== Production Stage =====
FROM python:3.11-slim-bookworm

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--loop", "uvloop", "--http", "httptools"]
```

### 9.3 Frontend Dockerfile

```dockerfile
# frontend/Dockerfile
# ===== Build Stage =====
FROM node:18-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# ===== Production Stage =====
FROM nginx:1.25-alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
```

### 9.4 系統映像總覽

本系統共有 **3 個自建映像**，推送至 GCP Artifact Registry：

| Image | 來源 | Base Image | 用途 |
|-------|------|------------|------|
| `backend:latest` | `backend/Dockerfile` | `python:3.11-slim-bookworm` | FastAPI 後端 API |
| `frontend:latest` | `frontend/Dockerfile` | `nginx:1.25-alpine` | React 前端靜態檔 |
| `pgbouncer:latest` | 外部/自建 | `edoburu/pgbouncer` | 資料庫連線池代理 |

#### 映像 Registry 路徑

```
us-central1-docker.pkg.dev/ds-final-project-480207/flash-sale-repo/
├── backend:latest      # FastAPI + Uvicorn (~300MB)
├── frontend:latest     # Nginx + React 靜態檔 (~50MB)
└── pgbouncer:latest    # PgBouncer 連線池 (~30MB)
```

#### 各映像構建階段

| 映像 | Builder Stage | Production Stage |
|------|---------------|------------------|
| **backend** | `ghcr.io/astral-sh/uv:python3.11-bookworm-slim` | `python:3.11-slim-bookworm` |
| **frontend** | `node:18-alpine` | `nginx:1.25-alpine` |
| **pgbouncer** | - | `edoburu/pgbouncer` |

#### 部署架構

```
┌─────────────────────────────────────────────────────────────┐
│              GCP Artifact Registry                          │
│         flash-sale-repo (us-central1)                       │
├─────────────────┬─────────────────┬─────────────────────────┤
│  backend:latest │ frontend:latest │    pgbouncer:latest     │
└────────┬────────┴────────┬────────┴────────────┬────────────┘
         │                 │                     │
         ▼                 ▼                     ▼
    ┌─────────┐      ┌─────────┐           ┌─────────┐
    │ Backend │      │Frontend │           │PgBouncer│
    │ 5-50 Pod│      │ 1-5 Pod │           │  6 Pod  │
    │  (HPA)  │      │  (HPA)  │           │ (固定)  │
    └─────────┘      └─────────┘           └─────────┘
```

#### 外部託管服務（非容器化）

| 服務 | 提供者 | 說明 |
|------|--------|------|
| PostgreSQL 15 | GCP Cloud SQL | 託管關聯式資料庫 |
| Redis 7 | GCP Memorystore | 託管快取與排名服務 |

---

## 10. 防超賣機制：四層防護

### 10.1 為什麼需要四層？

在高並發搶購場景下，單一防護機制可能失效：

```
場景：庫存剩 1 件，1000 人同時搶購

只用 Redis：網路分區時可能不一致
只用 DB 鎖：效能瓶頸
只用樂觀鎖：高衝突時重試風暴
```

**解決方案：** 多層防護，每層解決不同問題。

### 10.2 四層防護架構

```
┌─────────────────────────────────────────────────────────────────┐
│                        Layer 1: Redis 分散式鎖                   │
│                  確保同一時間只有一個請求處理                      │
│                     SET lock:product:{id} NX EX 2                │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Layer 2: Redis 原子扣減                    │
│                      Lua Script: GET + DECR                      │
│                      確保「檢查+扣減」原子執行                     │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Layer 3: PostgreSQL 行級鎖                   │
│                      SELECT ... FOR UPDATE                       │
│                      鎖定該行防止並發讀取                         │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Layer 4: 樂觀鎖                           │
│                  UPDATE ... WHERE version = ?                    │
│                      最後一道防線：版本號檢查                      │
└─────────────────────────────────────────────────────────────────┘
```

### 10.3 各層實現細節

#### Layer 1: Redis 分散式鎖

```python
async def acquire_lock(product_id: str, ttl: int = 2) -> tuple[bool, str]:
    owner_id = str(uuid.uuid4())
    acquired = await redis.set(
        f"lock:product:{product_id}",
        owner_id,
        nx=True,   # 只有 key 不存在時才設定
        ex=ttl     # 2 秒後自動過期（防死鎖）
    )
    return (acquired is not None, owner_id)
```

#### Layer 2: Redis 原子扣減

```lua
-- Lua Script
local stock = tonumber(redis.call("GET", KEYS[1]))
if stock and stock >= 1 then
    return redis.call("DECR", KEYS[1])
else
    return -1  -- 庫存不足
end
```

#### Layer 3: PostgreSQL 行級鎖

```python
# SELECT ... FOR UPDATE 鎖定該行
result = await session.execute(
    select(Product)
    .where(Product.id == product_id)
    .with_for_update()  # 行級鎖
)
product = result.scalar_one()
```

#### Layer 4: 樂觀鎖

```python
# UPDATE 時檢查版本號
result = await session.execute(
    update(Product)
    .where(
        Product.id == product_id,
        Product.version == expected_version  # 版本檢查
    )
    .values(
        stock=Product.stock - 1,
        version=Product.version + 1
    )
)
if result.rowcount == 0:
    raise OptimisticLockError("版本已變更，請重試")
```

### 10.4 各層職責

| 層級 | 機制 | 職責 | 失效場景處理 |
|------|------|------|-------------|
| Layer 1 | Redis 鎖 | 限流，減少 DB 壓力 | Redis 故障時跳過 |
| Layer 2 | Redis 原子扣減 | 快速判斷庫存 | 降級到 DB 檢查 |
| Layer 3 | DB 行級鎖 | 防止並發讀取舊值 | 等待鎖釋放 |
| Layer 4 | 樂觀鎖 | 最終一致性保證 | 拋出錯誤，請求重試 |

---

## 11. 架構決策總結

### 11.1 技術選型原則

| 需求 | 選擇 | 原因 |
|------|------|------|
| 高並發 API | FastAPI + uvloop | 非同步處理，單 Worker 高吞吐 |
| 資料持久化 | PostgreSQL | ACID、UPSERT、成熟穩定 |
| 即時排名 | Redis Sorted Set | O(log N) 時間複雜度 |
| 連線複用 | PgBouncer | 解決連線數限制（1150→180） |
| 自動擴縮 | Kubernetes HPA | 流量驅動，成本優化 |
| 即時推播 | WebSocket | 低延遲，省頻寬 |
| 防超賣 | 四層機制 | 多重保險，確保一致性 |

### 11.2 資料流總覽

```
用戶出價請求
     │
     ▼
┌─────────────────┐
│ 1. 驗證 Campaign │ ──► Redis Cache（快取命中不查 DB）
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ 2. 計算 Score    │ ──► 純 CPU 計算（Score = α×P + β/(T+1) + γ×W）
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ 3. 寫入出價      │ ──► PostgreSQL UPSERT（原子操作）
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ 4. 更新排名      │ ──► Redis ZADD + ZREVRANK（Pipeline 批次）
└─────────────────┘
     │
     ▼
  回傳排名給用戶
```

### 11.3 設計核心理念

1. **讀寫分離**
   - 讀操作：Redis（快）
   - 寫操作：PostgreSQL（可靠）

2. **連線複用**
   - PgBouncer Transaction Mode
   - 6.4:1 連線複用比

3. **彈性擴展**
   - Kubernetes HPA 自動擴縮
   - 5-50 Pods 動態調整

4. **多層防護**
   - 四層防超賣機制
   - 每層解決不同層面的問題

5. **即時推播**
   - WebSocket 取代輪詢
   - 每 2 秒廣播排名更新

---

## 附錄：關鍵檔案位置

| 功能 | 檔案路徑 |
|------|----------|
| 出價服務 | `backend/src/app/services/bid_service.py` |
| Redis 服務 | `backend/src/app/services/redis_service.py` |
| 庫存服務 | `backend/src/app/services/inventory_service.py` |
| WebSocket | `backend/src/app/services/ws_manager.py` |
| 資料庫配置 | `backend/src/app/core/database.py` |
| Backend 部署 | `k8s/backend-deployment.yaml` |
| PgBouncer 部署 | `k8s/pgbouncer-deployment.yaml` |
| HPA 配置 | `k8s/hpa.yaml` |
| Ingress 配置 | `k8s/ingress.yaml` |
