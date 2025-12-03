# 即時競標與限時搶購系統 - 實作任務清單

## 文件資訊

| 項目 | 內容 |
|------|------|
| **專案名稱** | Real-time Bidding & Flash Sale System |
| **文件版本** | 1.1 |
| **建立日期** | 2025-12-03 |
| **對應規格** | technical_spec.md v1.0 |

---

## 任務總覽

本文件將實作任務拆分為 8 個主要階段，共約 45 個子任務。每個任務標註優先級（P0 最高）與預估複雜度（1-5）。

```
Phase 1: 專案初始化          [P0] ████░░░░░░  4 tasks
Phase 2: 資料庫建置          [P0] ██████░░░░  6 tasks
Phase 3: 後端核心服務        [P0] ████████████ 12 tasks
Phase 4: 防超賣機制          [P0] ████░░░░░░  4 tasks
Phase 5: 即時推播            [P1] ████░░░░░░  4 tasks
Phase 6: 前端開發            [P1] ██████░░░░  6 tasks
Phase 7: 容器化與部署        [P1] ██████░░░░  6 tasks
Phase 8: 測試與驗證          [P0] ████░░░░░░  4 tasks
```

---

## Phase 1: 專案初始化

### Task 1.1: 專案結構建立
**優先級**: P0 | **複雜度**: 1

**目標**: 建立標準化的專案目錄結構

**執行步驟**:
- [ ] 建立專案根目錄結構
- [ ] 初始化 Git 版本控制
- [ ] 建立 `.gitignore` 文件
- [ ] 建立 `README.md` 專案說明

**目錄結構** (UV 標準 src-layout):
```
flash-sale-system/
├── backend/
│   ├── src/
│   │   └── app/
│   │       ├── __init__.py
│   │       ├── main.py        # FastAPI 應用入口
│   │       ├── api/           # API 路由
│   │       │   ├── __init__.py
│   │       │   └── v1/
│   │       │       ├── __init__.py
│   │       │       ├── auth.py
│   │       │       ├── products.py
│   │       │       ├── campaigns.py
│   │       │       ├── bids.py
│   │       │       ├── rankings.py
│   │       │       ├── orders.py
│   │       │       └── ws.py
│   │       ├── core/          # 核心配置
│   │       │   ├── __init__.py
│   │       │   ├── config.py
│   │       │   ├── database.py
│   │       │   ├── redis.py
│   │       │   └── security.py
│   │       ├── models/        # SQLAlchemy 資料模型
│   │       │   ├── __init__.py
│   │       │   ├── user.py
│   │       │   ├── product.py
│   │       │   ├── campaign.py
│   │       │   ├── bid.py
│   │       │   └── order.py
│   │       ├── schemas/       # Pydantic schemas
│   │       │   ├── __init__.py
│   │       │   ├── user.py
│   │       │   ├── product.py
│   │       │   ├── campaign.py
│   │       │   ├── bid.py
│   │       │   └── order.py
│   │       ├── services/      # 業務邏輯
│   │       │   ├── __init__.py
│   │       │   ├── user_service.py
│   │       │   ├── product_service.py
│   │       │   ├── campaign_service.py
│   │       │   ├── bid_service.py
│   │       │   ├── ranking_service.py
│   │       │   ├── order_service.py
│   │       │   ├── redis_service.py
│   │       │   ├── settlement_service.py
│   │       │   └── inventory_service.py
│   │       ├── middleware/    # 中間件
│   │       │   ├── __init__.py
│   │       │   └── rate_limit.py
│   │       └── utils/         # 工具函數
│   │           └── __init__.py
│   ├── tests/                 # 測試目錄
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_score_calculation.py
│   │   ├── test_inventory.py
│   │   ├── test_ranking.py
│   │   └── test_api/
│   ├── alembic/               # 資料庫遷移
│   │   ├── versions/
│   │   └── env.py
│   ├── scripts/               # 腳本工具
│   │   ├── seed_data.py
│   │   └── verify_consistency.py
│   ├── pyproject.toml         # UV 專案配置 (核心)
│   ├── uv.lock                # UV 鎖定檔 (自動生成)
│   ├── alembic.ini
│   ├── .env.example
│   ├── .python-version        # Python 版本 (UV 使用)
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── contexts/
│   │   └── types/
│   ├── public/
│   ├── package.json
│   └── Dockerfile
├── k6-tests/                  # 壓力測試腳本
│   ├── baseline.js
│   ├── high-concurrency.js
│   └── exponential-load.js
├── k8s/                       # Kubernetes 配置
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   ├── secrets.yaml
│   └── hpa.yaml
├── docker-compose.yml
├── .gitignore
├── README.md
└── docs/
    ├── technical_spec.md
    └── task.md
```

> **注意**: UV 使用 `src-layout` 結構，源碼放在 `src/` 目錄下，這是 Python 打包的最佳實踐，可避免直接導入未安裝的套件。

**驗收標準**:
- [ ] 目錄結構完整建立
- [ ] Git 初始化完成，首次 commit

---

### Task 1.2: 開發環境配置
**優先級**: P0 | **複雜度**: 2

**目標**: 配置本地開發環境與依賴管理

> **套件管理工具**: 使用 **UV** 進行 Python 套件管理與虛擬環境控管
> - UV 官方文檔: https://docs.astral.sh/uv/
> - 安裝方式: `curl -LsSf https://astral.sh/uv/install.sh | sh`

**執行步驟**:
- [ ] 安裝 UV 套件管理工具
- [ ] 使用 UV 初始化專案 (`uv init --lib`)
- [ ] 配置 `pyproject.toml` 定義依賴
- [ ] 建立 `.python-version` 指定 Python 版本
- [ ] 執行 `uv sync` 安裝依賴 (自動建立虛擬環境)
- [ ] 建立 `docker-compose.yml` 本地服務
- [ ] 配置環境變數模板 `.env.example`

**UV 專案初始化**:
```bash
# 安裝 UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# 進入 backend 目錄
cd backend

# 初始化專案 (使用 lib layout，會建立 src/ 目錄)
uv init --lib --name flash-sale-system

# 設定 Python 版本
echo "3.11" > .python-version

# UV 會自動建立虛擬環境，無需手動建立
# 同步依賴 (自動建立 .venv/)
uv sync

# 建立 src/app 結構 (取代預設的 src/flash_sale_system)
rm -rf src/flash_sale_system
mkdir -p src/app

# 執行任何命令時使用 uv run
uv run python --version
uv run uvicorn app.main:app --reload
```

> **注意**: 使用 `uv run` 執行命令時，UV 會自動使用專案的虛擬環境，無需手動啟動。

**核心依賴 (pyproject.toml)**:
```toml
[project]
name = "flash-sale-system"
version = "1.0.0"
description = "Real-time Bidding & Flash Sale System"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.104.1",
    "uvicorn[standard]>=0.24.0",
    "sqlalchemy>=2.0.23",
    "asyncpg>=0.29.0",
    "redis>=5.0.1",
    "pydantic>=2.5.2",
    "pydantic-settings>=2.1.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "websockets>=12.0",
    "httpx>=0.25.2",
    "python-multipart>=0.0.6",
    "alembic>=1.12.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "httpx>=0.25.2",
    "ruff>=0.1.6",
]

[project.scripts]
# 定義可執行命令
start = "uvicorn app.main:app --reload"
seed = "python -m scripts.seed_data"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/app"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"
```

**Python 版本檔 (.python-version)**:
```
3.11
```

**安裝依賴**:
```bash
# UV 會自動建立虛擬環境並安裝依賴
uv sync

# 安裝開發依賴
uv sync --dev

# 新增套件
uv add <package-name>

# 新增開發套件
uv add --dev <package-name>

# 執行程式 (自動使用虛擬環境)
uv run uvicorn app.main:app --reload

# 執行測試
uv run pytest
```

**docker-compose.yml 服務**:
```yaml
services:
  postgres:
    image: postgres:15
    ports: ["5432:5432"]
  redis:
    image: redis:7
    ports: ["6379:6379"]
```

**驗收標準**:
- [ ] `uv sync` 成功建立虛擬環境並安裝依賴
- [ ] `uv run python -c "import app"` 可正確導入
- [ ] `docker-compose up -d` 啟動本地資料庫
- [ ] 環境變數模板包含所有必要配置
- [ ] `uv.lock` 檔案自動生成

---

### Task 1.3: FastAPI 應用骨架
**優先級**: P0 | **複雜度**: 2

**目標**: 建立 FastAPI 應用程式基礎結構

**執行步驟**:
- [ ] 建立 `main.py` 應用入口
- [ ] 配置 CORS 中間件
- [ ] 建立健康檢查端點 `/health`
- [ ] 配置 OpenAPI 文檔

**程式碼位置**: `backend/src/app/main.py`

**關鍵實作**:
```python
# main.py 基礎結構
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Flash Sale System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

**驗收標準**:
- [ ] `uv run uvicorn app.main:app --reload` 成功啟動
- [ ] `/health` 端點回傳 200
- [ ] `/docs` 顯示 Swagger UI

---

### Task 1.4: 核心配置模組
**優先級**: P0 | **複雜度**: 2

**目標**: 建立統一的配置管理

**執行步驟**:
- [ ] 建立 `src/app/core/config.py` 配置類
- [ ] 建立 `src/app/core/database.py` 資料庫連接
- [ ] 建立 `src/app/core/redis.py` Redis 連接
- [ ] 建立 `src/app/core/security.py` 安全相關

**程式碼位置**: `backend/src/app/core/`

**驗收標準**:
- [ ] 配置從環境變數正確讀取
- [ ] 資料庫連接池建立成功
- [ ] Redis 連接測試通過

---

## Phase 2: 資料庫建置

### Task 2.1: PostgreSQL Schema 設計
**優先級**: P0 | **複雜度**: 3

**目標**: 建立資料庫表結構

**執行步驟**:
- [ ] 建立 `models/user.py` - 用戶模型
- [ ] 建立 `models/product.py` - 商品模型
- [ ] 建立 `models/campaign.py` - 活動模型
- [ ] 建立 `models/bid.py` - 出價模型
- [ ] 建立 `models/order.py` - 訂單模型

**資料表定義** (依據 technical_spec.md 第 2.1 節):

| 表名 | 主要欄位 | 說明 |
|------|----------|------|
| users | user_id, email, password_hash, weight | 會員資料 |
| products | product_id, name, stock, min_price, version | 商品資料 |
| campaigns | campaign_id, product_id, start_time, end_time, alpha, beta, gamma | 活動設定 |
| bids | bid_id, campaign_id, user_id, price, score, time_elapsed_ms | 出價記錄 |
| orders | order_id, campaign_id, user_id, final_price, final_rank | 訂單資料 |

**驗收標準**:
- [ ] 所有 SQLAlchemy 模型定義完成
- [ ] 外鍵關係正確設定
- [ ] 索引依據 spec 建立

---

### Task 2.2: 資料庫遷移設定
**優先級**: P0 | **複雜度**: 2

**目標**: 配置 Alembic 資料庫遷移工具

**執行步驟**:
- [ ] 初始化 Alembic (`alembic init alembic`)
- [ ] 配置 `alembic.ini` 連接字串
- [ ] 建立初始遷移腳本
- [ ] 執行遷移建立資料表

**驗收標準**:
- [ ] `alembic upgrade head` 成功執行
- [ ] 資料庫中正確建立所有表
- [ ] 可以產生新的遷移腳本

---

### Task 2.3: Redis 資料結構設計
**優先級**: P0 | **複雜度**: 2

**目標**: 實作 Redis 資料結構封裝

**執行步驟**:
- [ ] 建立 `services/redis_service.py`
- [ ] 實作排名 Sorted Set 操作
- [ ] 實作庫存計數器操作
- [ ] 實作分散式鎖操作

**Redis Key 設計** (依據 technical_spec.md 第 2.2 節):

| Key Pattern | 操作 | 說明 |
|-------------|------|------|
| `bid:{campaign_id}` | ZADD, ZREVRANGE, ZREVRANK | 競標排名 |
| `stock:{product_id}` | GET, DECR, INCR | 庫存計數 |
| `lock:product:{product_id}` | SET NX EX, DEL | 分散式鎖 |
| `campaign:{campaign_id}` | HGET, HSET | 活動快取 |

**核心方法**:
```python
class RedisService:
    async def update_ranking(campaign_id: str, user_id: str, score: float)
    async def get_top_k(campaign_id: str, k: int) -> List[dict]
    async def get_user_rank(campaign_id: str, user_id: str) -> int
    async def decrement_stock(product_id: str) -> int
    async def acquire_lock(product_id: str, timeout: int = 2) -> bool
    async def release_lock(product_id: str)
```

**驗收標準**:
- [ ] Sorted Set 排名操作正確
- [ ] 庫存原子扣減正確
- [ ] 分散式鎖獲取/釋放正確

---

### Task 2.4: 活動快取同步
**優先級**: P1 | **複雜度**: 2

**目標**: 實作活動參數快取機制

**執行步驟**:
- [ ] 活動建立時同步到 Redis
- [ ] 活動查詢優先讀取 Redis
- [ ] 實作快取失效策略

**驗收標準**:
- [ ] 活動參數可從 Redis 快速讀取
- [ ] 快取與資料庫保持一致

---

### Task 2.5: 初始測試資料
**優先級**: P1 | **複雜度**: 1

**目標**: 建立開發用種子資料

**執行步驟**:
- [ ] 建立 `scripts/seed_data.py`
- [ ] 產生測試用戶 (含不同權重 W)
- [ ] 產生測試商品
- [ ] 產生測試活動

**測試資料規格**:
- 100 個測試用戶 (權重 W: 0.5 ~ 5.0)
- 5 個測試商品
- 1 個進行中活動 (庫存 K=10)

**驗收標準**:
- [ ] 執行腳本後資料正確寫入
- [ ] 可用於後續 API 測試

---

### Task 2.6: 資料庫連接池優化
**優先級**: P2 | **複雜度**: 2

**目標**: 優化資料庫連接效能

**執行步驟**:
- [ ] 配置 SQLAlchemy 異步連接池
- [ ] 設定連接池大小與超時
- [ ] 實作連接健康檢查

**配置參數**:
```python
# 連接池配置
pool_size = 20
max_overflow = 10
pool_timeout = 30
pool_recycle = 1800
```

**驗收標準**:
- [ ] 連接池正常運作
- [ ] 高並發下連接不會耗盡

---

## Phase 3: 後端核心服務

### Task 3.1: 用戶註冊 API
**優先級**: P0 | **複雜度**: 2

**目標**: 實作用戶註冊功能

**執行步驟**:
- [ ] 建立 `schemas/user.py` 請求/回應 schema
- [ ] 建立 `services/user_service.py` 業務邏輯
- [ ] 建立 `api/v1/auth.py` 路由
- [ ] 實作密碼 bcrypt 雜湊
- [ ] 實作會員權重 W 隨機分配

**API 端點**: `POST /api/v1/auth/register`

**請求格式**:
```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "username": "user001"
}
```

**回應格式**:
```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "username": "user001",
  "weight": 2.5
}
```

**業務規則**:
- Email 必須唯一
- 密碼使用 bcrypt (cost=12) 雜湊
- 權重 W 隨機分配 (範圍: 0.5 ~ 5.0)

**驗收標準**:
- [ ] 註冊成功回傳用戶資訊
- [ ] 重複 email 回傳 400 錯誤
- [ ] 密碼正確雜湊儲存

---

### Task 3.2: 用戶登入 API
**優先級**: P0 | **複雜度**: 2

**目標**: 實作 JWT 登入認證

**執行步驟**:
- [ ] 實作密碼驗證邏輯
- [ ] 實作 JWT Token 生成
- [ ] 建立登入 API 端點
- [ ] 建立 Token 驗證中間件

**API 端點**: `POST /api/v1/auth/login`

**請求格式**:
```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

**回應格式**:
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**JWT 配置**:
- 演算法: HS256
- 有效期: 1 小時
- Payload: user_id, email, weight

**驗收標準**:
- [ ] 正確帳密可取得 Token
- [ ] 錯誤帳密回傳 401
- [ ] Token 可用於後續 API 認證

---

### Task 3.3: 用戶資訊 API
**優先級**: P1 | **複雜度**: 1

**目標**: 實作取得當前用戶資訊

**執行步驟**:
- [ ] 建立認證依賴注入 `get_current_user`
- [ ] 建立 `/api/v1/auth/me` 端點

**API 端點**: `GET /api/v1/auth/me`

**驗收標準**:
- [ ] 帶 Token 可取得用戶資訊 (含權重 W)
- [ ] 無 Token 回傳 401

---

### Task 3.4: 商品管理 API (管理員)
**優先級**: P0 | **複雜度**: 2

**目標**: 實作商品 CRUD

**執行步驟**:
- [ ] 建立 `schemas/product.py`
- [ ] 建立 `services/product_service.py`
- [ ] 建立 `api/v1/products.py`
- [ ] 實作商品列表查詢
- [ ] 實作商品建立 (管理員)

**API 端點**:
| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/v1/products` | 商品列表 |
| GET | `/api/v1/products/{id}` | 商品詳情 |
| POST | `/api/v1/products` | 建立商品 (管理員) |

**建立商品請求**:
```json
{
  "name": "限量球鞋 2025",
  "description": "限量發售 100 雙",
  "image_url": "https://...",
  "stock": 10,
  "min_price": 1000.00
}
```

**驗收標準**:
- [ ] 商品列表正確回傳
- [ ] 商品建立成功
- [ ] 庫存 stock 初始化到 Redis

---

### Task 3.5: 活動管理 API (管理員)
**優先級**: P0 | **複雜度**: 3

**目標**: 實作活動建立與管理

**執行步驟**:
- [ ] 建立 `schemas/campaign.py`
- [ ] 建立 `services/campaign_service.py`
- [ ] 建立 `api/v1/campaigns.py`
- [ ] 實作活動建立 (含參數 α, β, γ)
- [ ] 實作活動列表與詳情
- [ ] 同步活動資訊到 Redis

**API 端點**:
| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/v1/campaigns` | 活動列表 |
| GET | `/api/v1/campaigns/{id}` | 活動詳情 |
| POST | `/api/v1/campaigns` | 建立活動 (管理員) |

**建立活動請求**:
```json
{
  "product_id": "uuid",
  "start_time": "2025-12-03T10:00:00Z",
  "end_time": "2025-12-03T10:10:00Z",
  "alpha": 1.0,
  "beta": 1000.0,
  "gamma": 100.0
}
```

**活動詳情回應** (含即時統計):
```json
{
  "campaign_id": "uuid",
  "product": { "name": "...", "stock": 10, "min_price": 1000 },
  "start_time": "...",
  "end_time": "...",
  "alpha": 1.0,
  "beta": 1000.0,
  "gamma": 100.0,
  "status": "active",
  "stats": {
    "total_participants": 523,
    "max_price": 2500.00,
    "min_winning_score": 1800.50
  }
}
```

**驗收標準**:
- [ ] 活動建立成功並同步 Redis
- [ ] 活動列表顯示狀態 (pending/active/ended)
- [ ] 活動詳情包含即時統計

---

### Task 3.6: 出價 API (核心)
**優先級**: P0 | **複雜度**: 4

**目標**: 實作競標出價核心邏輯

**執行步驟**:
- [ ] 建立 `schemas/bid.py`
- [ ] 建立 `services/bid_service.py`
- [ ] 建立 `api/v1/bids.py`
- [ ] 實作積分計算公式
- [ ] 實作出價驗證邏輯
- [ ] 更新 Redis 排名

**API 端點**: `POST /api/v1/bids`

**請求格式**:
```json
{
  "campaign_id": "uuid",
  "price": 1500.00
}
```

**回應格式**:
```json
{
  "bid_id": "uuid",
  "campaign_id": "uuid",
  "user_id": "uuid",
  "price": 1500.00,
  "score": 1723.45,
  "rank": 15,
  "time_elapsed_ms": 3500,
  "created_at": "2025-12-03T10:00:03.500Z"
}
```

**積分計算公式** (依據 PDF 需求):
```python
def calculate_score(price: float, time_elapsed_ms: int, weight: float,
                    alpha: float, beta: float, gamma: float) -> float:
    """
    Score = α·P + β/(T+1) + γ·W
    """
    return alpha * price + beta / (time_elapsed_ms + 1) + gamma * weight
```

**出價處理流程**:
1. 驗證活動狀態 (必須進行中)
2. 驗證出價金額 >= 底價
3. 計算反應時間 T = now - campaign.start_time (毫秒)
4. 獲取用戶權重 W
5. 計算積分 Score
6. 更新 Redis 排名 (ZADD)
7. 異步寫入 PostgreSQL

**驗收標準**:
- [ ] 出價成功回傳積分與排名
- [ ] 積分計算公式正確
- [ ] Redis 排名即時更新
- [ ] 活動未開始/已結束回傳錯誤
- [ ] 出價低於底價回傳錯誤

---

### Task 3.7: 更新出價 API
**優先級**: P0 | **複雜度**: 3

**目標**: 實作出價更新功能

**執行步驟**:
- [ ] 在 `services/bid_service.py` 新增更新邏輯
- [ ] 重新計算反應時間 T (以新時間為準)
- [ ] 重新計算積分並更新排名

**業務規則**:
- 每次更新出價，T 以最新出價時間計算
- 相當於「覆蓋」之前的出價
- Redis 直接 ZADD 覆蓋舊分數

**驗收標準**:
- [ ] 更新出價後積分重新計算
- [ ] 反應時間 T 以新時間為準
- [ ] 排名正確更新

---

### Task 3.8: 排名查詢 API
**優先級**: P0 | **複雜度**: 2

**目標**: 實作排名看板查詢

**執行步驟**:
- [ ] 建立 `services/ranking_service.py`
- [ ] 建立 `api/v1/rankings.py`
- [ ] 實作 Top K 排名查詢
- [ ] 實作個人排名查詢

**API 端點**:
| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/v1/rankings/{campaign_id}` | Top K 排名 |
| GET | `/api/v1/rankings/{campaign_id}/me` | 我的排名 |

**排名查詢回應**:
```json
{
  "campaign_id": "uuid",
  "total_participants": 1523,
  "rankings": [
    {"rank": 1, "user_id": "uuid", "username": "user001", "score": 2523.75, "price": 2000.00},
    {"rank": 2, "user_id": "uuid", "username": "user002", "score": 2401.50, "price": 1900.00}
  ],
  "min_winning_score": 1100.25,
  "max_score": 2523.75,
  "updated_at": "2025-12-03T10:05:00Z"
}
```

**驗收標準**:
- [ ] Top K 排名正確 (K 為商品庫存)
- [ ] 個人排名查詢正確
- [ ] 統計資訊 (最高分、最低得標分) 正確

---

### Task 3.9: 出價歷史 API
**優先級**: P2 | **複雜度**: 1

**目標**: 查詢用戶出價歷史

**執行步驟**:
- [ ] 建立出價歷史查詢端點
- [ ] 從 PostgreSQL 查詢用戶出價記錄

**API 端點**: `GET /api/v1/bids/{campaign_id}/history`

**驗收標準**:
- [ ] 回傳用戶所有出價記錄
- [ ] 按時間排序

---

### Task 3.10: 活動結算服務
**優先級**: P0 | **複雜度**: 4

**目標**: 實作活動結束自動結算

**執行步驟**:
- [ ] 建立 `services/settlement_service.py`
- [ ] 實作定時檢查活動狀態
- [ ] 實作結算邏輯 (Top K 訂單建立)
- [ ] 實作防超賣驗證

**結算流程**:
1. 檢查活動是否已到結束時間
2. 獲取 Redis 排名 Top K
3. 使用防超賣機制建立訂單 (見 Phase 4)
4. 更新活動狀態為 ended
5. 發送得標/未得標通知

**定時任務** (使用 FastAPI background task 或 Celery):
```python
# 每 10 秒檢查一次活動狀態
async def check_campaign_settlement():
    # 查詢需結算的活動
    # 執行結算
```

**驗收標準**:
- [ ] 活動結束自動觸發結算
- [ ] 訂單數量 ≤ 庫存 K (絕對不超賣)
- [ ] 得標者為排名前 K 名

---

### Task 3.11: 訂單查詢 API
**優先級**: P1 | **複雜度**: 2

**目標**: 實作訂單查詢功能

**執行步驟**:
- [ ] 建立 `schemas/order.py`
- [ ] 建立 `services/order_service.py`
- [ ] 建立 `api/v1/orders.py`

**API 端點**:
| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/v1/orders` | 我的訂單列表 |
| GET | `/api/v1/orders/{campaign_id}` | 活動訂單 (管理員) |

**驗收標準**:
- [ ] 用戶可查詢自己的訂單
- [ ] 管理員可查詢活動所有訂單

---

### Task 3.12: 限流中間件
**優先級**: P1 | **複雜度**: 3

**目標**: 實作 API 限流保護

**執行步驟**:
- [ ] 建立 `middleware/rate_limit.py`
- [ ] 實作 Token Bucket 演算法
- [ ] 配置不同端點的限流規則

**限流規則** (依據 technical_spec.md 第 3.2 節):
| 限流層級 | 限制 |
|----------|------|
| 用戶限流 | 10 req/s |
| IP 限流 | 100 req/s |

**實作方式**: 使用 Redis + Lua 腳本

**驗收標準**:
- [ ] 超過限流回傳 429
- [ ] 回應包含 `Retry-After` header

---

## Phase 4: 防超賣機制

### Task 4.1: Redis 分散式鎖
**優先級**: P0 | **複雜度**: 3

**目標**: 實作分散式鎖防止並發問題

**執行步驟**:
- [ ] 在 `services/redis_service.py` 實作鎖操作
- [ ] 實作鎖獲取 (SET NX EX)
- [ ] 實作鎖釋放 (Lua 腳本確保只刪自己的鎖)
- [ ] 實作鎖超時保護 (TTL 2 秒)

**鎖獲取**:
```python
async def acquire_lock(product_id: str, owner_id: str, ttl: int = 2) -> bool:
    """
    SET lock:product:{product_id} {owner_id} NX EX {ttl}
    """
```

**鎖釋放 (Lua 腳本)**:
```lua
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
```

**驗收標準**:
- [ ] 同一時間只有一個請求可獲取鎖
- [ ] 鎖超時自動釋放
- [ ] 只能釋放自己的鎖

---

### Task 4.2: Redis 原子扣減
**優先級**: P0 | **複雜度**: 3

**目標**: 實作庫存原子扣減

**執行步驟**:
- [ ] 實作 Lua 腳本檢查並扣減庫存
- [ ] 庫存不足時拒絕扣減
- [ ] 實作庫存回滾 (INCR)

**Lua 腳本** (依據 technical_spec.md 第 5.1 節):
```lua
local stock = tonumber(redis.call("GET", KEYS[1]))
if stock and stock >= 1 then
    return redis.call("DECR", KEYS[1])
else
    return -1  -- 庫存不足
end
```

**驗收標準**:
- [ ] 庫存扣減原子性保證
- [ ] 庫存不足正確拒絕
- [ ] 失敗時可回滾

---

### Task 4.3: PostgreSQL 行級鎖
**優先級**: P0 | **複雜度**: 3

**目標**: 實作資料庫層級的一致性保證

**執行步驟**:
- [ ] 實作 SELECT ... FOR UPDATE
- [ ] 實作樂觀鎖版本號檢查
- [ ] 實作事務處理

**訂單建立事務** (依據 technical_spec.md 第 5.2 節):
```python
async def create_order_with_lock(campaign_id: str, user_id: str, ...):
    async with session.begin():
        # 1. 行級鎖
        product = await session.execute(
            select(Product).where(Product.product_id == product_id).with_for_update()
        )

        # 2. 檢查庫存
        if product.stock < 1:
            raise InsufficientStockError()

        # 3. 樂觀鎖更新
        result = await session.execute(
            update(Product)
            .where(Product.product_id == product_id)
            .where(Product.version == product.version)
            .where(Product.stock >= 1)
            .values(stock=Product.stock - 1, version=Product.version + 1)
        )

        if result.rowcount == 0:
            raise ConcurrencyError()

        # 4. 建立訂單
        order = Order(...)
        session.add(order)
```

**驗收標準**:
- [ ] 行級鎖正確生效
- [ ] 樂觀鎖衝突時正確重試
- [ ] 庫存與訂單數一致

---

### Task 4.4: 四層防護整合
**優先級**: P0 | **複雜度**: 4

**目標**: 整合四層防超賣機制

**執行步驟**:
- [ ] 建立 `services/inventory_service.py`
- [ ] 整合四層防護流程
- [ ] 實作失敗回滾機制
- [ ] 實作對賬驗證

**完整流程** (依據 technical_spec.md 第 5.1 節):
```
Layer 1: Redis 分散式鎖
    ↓
Layer 2: Redis 原子扣減
    ↓
Layer 3: PostgreSQL 行級鎖
    ↓
Layer 4: 樂觀鎖版本號
```

**失敗回滾**:
- Redis 扣減成功但 DB 失敗 → Redis INCR 回滾
- 任一層失敗 → 釋放鎖

**驗收標準**:
- [ ] 四層防護流程完整
- [ ] 任何情況下訂單數 ≤ 庫存數
- [ ] 失敗時正確回滾

---

## Phase 5: 即時推播

### Task 5.1: WebSocket 服務建立
**優先級**: P1 | **複雜度**: 3

**目標**: 建立 WebSocket 即時推播服務

**執行步驟**:
- [ ] 建立 `api/v1/ws.py` WebSocket 路由
- [ ] 實作連接管理 (ConnectionManager)
- [ ] 實作活動房間 (Room) 機制
- [ ] 實作用戶認證

**程式碼結構**:
```python
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        # {campaign_id: {user_id: websocket}}

    async def connect(self, campaign_id: str, user_id: str, websocket: WebSocket)
    async def disconnect(self, campaign_id: str, user_id: str)
    async def broadcast_to_campaign(self, campaign_id: str, message: dict)
```

**WebSocket 端點**: `ws://host/ws/{campaign_id}`

**驗收標準**:
- [ ] WebSocket 連接成功建立
- [ ] 用戶可加入/離開活動房間
- [ ] 連接斷開自動清理

---

### Task 5.2: 排名推播機制
**優先級**: P1 | **複雜度**: 3

**目標**: 實作排名變更即時推播

**執行步驟**:
- [ ] 出價成功後觸發推播
- [ ] 定期推播排名更新 (1-2 秒)
- [ ] 實作節流機制避免過度推送

**推播事件** (依據 technical_spec.md 第 4.3 節):
```json
{
  "event": "ranking_update",
  "data": {
    "campaign_id": "uuid",
    "top_k": [
      {"rank": 1, "user_id": "uuid", "score": 2500.00},
      {"rank": 2, "user_id": "uuid", "score": 2400.00}
    ],
    "total_participants": 1523,
    "min_winning_score": 1800.50,
    "max_score": 2500.00,
    "timestamp": "2025-12-03T10:05:00Z"
  }
}
```

**驗收標準**:
- [ ] 排名變更 1-2 秒內推送
- [ ] 推播內容包含 Top K 排名
- [ ] 高並發下推播穩定

---

### Task 5.3: 個人出價確認推播
**優先級**: P1 | **複雜度**: 2

**目標**: 推播個人出價結果

**執行步驟**:
- [ ] 出價成功後推播給該用戶
- [ ] 包含積分與排名資訊

**推播事件**:
```json
{
  "event": "bid_accepted",
  "data": {
    "bid_id": "uuid",
    "price": 1500.00,
    "score": 1723.45,
    "rank": 15,
    "timestamp": "2025-12-03T10:05:00Z"
  }
}
```

**驗收標準**:
- [ ] 出價者即時收到確認
- [ ] 包含正確積分與排名

---

### Task 5.4: 活動結束推播
**優先級**: P1 | **複雜度**: 2

**目標**: 活動結束通知所有用戶

**執行步驟**:
- [ ] 結算完成後推播結果
- [ ] 區分得標/未得標用戶

**推播事件**:
```json
{
  "event": "campaign_ended",
  "data": {
    "campaign_id": "uuid",
    "is_winner": true,
    "final_rank": 5,
    "final_score": 1800.50
  }
}
```

**驗收標準**:
- [ ] 所有連接用戶收到結束通知
- [ ] 得標者收到確認資訊

---

## Phase 6: 前端開發

### Task 6.1: 前端專案初始化
**優先級**: P1 | **複雜度**: 2

**目標**: 建立 React 前端專案

**執行步驟**:
- [ ] 使用 Vite 建立 React + TypeScript 專案
- [ ] 安裝必要依賴 (axios, react-router, websocket)
- [ ] 配置 Tailwind CSS (簡單樣式)
- [ ] 建立專案目錄結構

**目錄結構**:
```
frontend/
├── src/
│   ├── api/           # API 呼叫
│   ├── components/    # 共用元件
│   ├── pages/         # 頁面
│   ├── hooks/         # 自定義 hooks
│   ├── contexts/      # Context (Auth)
│   └── types/         # TypeScript 類型
```

**驗收標準**:
- [ ] `npm run dev` 成功啟動
- [ ] 基礎路由配置完成

---

### Task 6.2: 登入/註冊頁面
**優先級**: P1 | **複雜度**: 2

**目標**: 實作會員登入註冊介面

**執行步驟**:
- [ ] 建立 `pages/Login.tsx`
- [ ] 建立 `pages/Register.tsx`
- [ ] 實作 AuthContext 管理 Token
- [ ] 實作表單驗證

**頁面元素**:
- 登入: Email 輸入、密碼輸入、登入按鈕
- 註冊: Email、密碼、用戶名、註冊按鈕
- 登入後顯示會員權重 W

**驗收標準**:
- [ ] 可註冊新帳號
- [ ] 可登入並取得 Token
- [ ] 登入後跳轉到活動頁

---

### Task 6.3: 活動列表與詳情頁
**優先級**: P1 | **複雜度**: 2

**目標**: 實作活動瀏覽介面

**執行步驟**:
- [ ] 建立 `pages/Campaigns.tsx` 活動列表
- [ ] 建立 `pages/CampaignDetail.tsx` 活動詳情
- [ ] 顯示商品資訊、庫存、底價
- [ ] 顯示活動時間與狀態

**頁面元素**:
- 活動列表: 商品圖、名稱、狀態、剩餘時間
- 活動詳情: 商品資訊、參數設定、倒數計時

**驗收標準**:
- [ ] 活動列表正確顯示
- [ ] 活動詳情包含所有資訊
- [ ] 倒數計時正確運作

---

### Task 6.4: 出價介面
**優先級**: P0 | **複雜度**: 3

**目標**: 實作競標出價功能

**執行步驟**:
- [ ] 建立出價表單元件
- [ ] 實作出價 API 呼叫
- [ ] 顯示出價結果 (積分、排名)
- [ ] 實作出價更新功能

**頁面元素**:
- 出價輸入框 (數字，≥ 底價)
- 出價按鈕
- 當前積分與排名顯示
- 出價歷史

**驗收標準**:
- [ ] 可送出出價
- [ ] 出價後顯示積分與排名
- [ ] 可更新出價

---

### Task 6.5: 即時排名看板
**優先級**: P0 | **複雜度**: 4

**目標**: 實作即時排名顯示

**執行步驟**:
- [ ] 建立 `components/RankingBoard.tsx`
- [ ] 實作 WebSocket 連接
- [ ] 即時更新排名列表
- [ ] 標示當前用戶位置

**看板元素** (依據 PDF 需求):
- 前 K 名暫定得標者
- 每位得標者的積分
- 最高出價金額
- 最低得標門檻分數 (第 K 名)
- 當前參與人數

**驗收標準**:
- [ ] WebSocket 連接成功
- [ ] 排名即時更新 (< 5 秒)
- [ ] 當前用戶排名標示
- [ ] 高並發下不顯示過舊資料

---

### Task 6.6: 管理後台頁面
**優先級**: P1 | **複雜度**: 3

**目標**: 實作管理員功能介面

**執行步驟**:
- [ ] 建立 `pages/admin/CreateCampaign.tsx`
- [ ] 實作商品上架表單
- [ ] 實作活動設定 (α, β, γ)
- [ ] 實作活動結果查看

**頁面元素**:
- 商品資訊輸入 (名稱、庫存 K、底價)
- 活動時間設定
- 參數設定 (α, β, γ)
- 活動結果與訂單列表

**驗收標準**:
- [ ] 可建立商品與活動
- [ ] 可查看活動結果
- [ ] 可驗證訂單數量

---

## Phase 7: 容器化與部署

### Task 7.1: Backend Dockerfile
**優先級**: P1 | **複雜度**: 2

**目標**: 建立後端容器映像

> **注意**: 使用 **UV** 進行容器內的套件安裝，大幅加速構建速度

**執行步驟**:
- [ ] 建立 `backend/Dockerfile`
- [ ] 使用多階段構建減小映像
- [ ] 使用 UV 安裝依賴
- [ ] 配置非 root 用戶執行
- [ ] 測試本地構建

**Dockerfile 結構 (UV 官方推薦 - src-layout)**:
```dockerfile
# 使用 UV 官方映像 (包含 Python 3.11)
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# 設定環境變數
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 複製依賴定義檔案
COPY pyproject.toml uv.lock ./

# 安裝依賴 (不含開發依賴)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# 複製源碼
COPY ./src ./src
COPY ./alembic ./alembic
COPY ./alembic.ini ./

# 安裝專案本身
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# 建立非 root 用戶
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# 使用 uv run 執行，確保使用正確的虛擬環境
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**多階段構建版本 (更小的映像)**:
```dockerfile
# Build stage
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY ./src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Production stage
FROM python:3.11-slim-bookworm

WORKDIR /app

# 複製虛擬環境
COPY --from=builder /app/.venv /app/.venv

# 複製源碼
COPY ./src ./src
COPY ./alembic ./alembic
COPY ./alembic.ini ./

# 設定 PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# 建立非 root 用戶
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**驗收標準**:
- [ ] `docker build` 成功
- [ ] 映像大小 < 200MB
- [ ] 容器可正常執行
- [ ] 構建時間相比 pip 顯著減少

---

### Task 7.2: Frontend Dockerfile
**優先級**: P1 | **複雜度**: 2

**目標**: 建立前端容器映像

**執行步驟**:
- [ ] 建立 `frontend/Dockerfile`
- [ ] 使用 nginx 服務靜態檔案
- [ ] 配置環境變數注入

**驗收標準**:
- [ ] `docker build` 成功
- [ ] nginx 正確服務前端

---

### Task 7.3: Docker Compose 完整配置
**優先級**: P1 | **複雜度**: 2

**目標**: 配置完整的本地開發環境

**執行步驟**:
- [ ] 完善 `docker-compose.yml`
- [ ] 配置所有服務 (backend, frontend, postgres, redis)
- [ ] 配置網路與健康檢查
- [ ] 配置 volume 持久化

**驗收標準**:
- [ ] `docker-compose up` 啟動所有服務
- [ ] 服務間通訊正常
- [ ] 資料持久化正常

---

### Task 7.4: GKE 部署配置
**優先級**: P1 | **複雜度**: 4

**目標**: 建立 Kubernetes 部署配置

**執行步驟**:
- [ ] 建立 `k8s/deployment.yaml` (各服務)
- [ ] 建立 `k8s/service.yaml`
- [ ] 建立 `k8s/ingress.yaml`
- [ ] 建立 `k8s/configmap.yaml`
- [ ] 建立 `k8s/secrets.yaml`

**部署資源**:
| 服務 | Replicas | Resources |
|------|----------|-----------|
| backend | 3 | 500m CPU, 512Mi |
| frontend | 2 | 200m CPU, 256Mi |

**驗收標準**:
- [ ] YAML 語法正確
- [ ] 服務可部署到 GKE
- [ ] Ingress 正確路由

---

### Task 7.5: HPA 自動擴展配置
**優先級**: P0 | **複雜度**: 3

**目標**: 配置水平自動擴展

**執行步驟**:
- [ ] 建立 `k8s/hpa.yaml`
- [ ] 配置 CPU 閾值觸發 (70%)
- [ ] 配置最小/最大 Pod 數量

**HPA 配置** (依據 technical_spec.md 第 7.2 節):
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

**驗收標準**:
- [ ] CPU > 70% 觸發擴展
- [ ] Pod 數量正確增減
- [ ] 擴展後回應時間穩定

---

### Task 7.6: GCP 服務配置
**優先級**: P1 | **複雜度**: 3

**目標**: 配置 GCP 雲端服務

**執行步驟**:
- [ ] 建立 GKE 叢集
- [ ] 配置 Cloud SQL (PostgreSQL)
- [ ] 配置 Memorystore (Redis)
- [ ] 配置 Cloud Load Balancing
- [ ] 設定 Cloud Monitoring

**GCP 資源**:
| 服務 | 規格 |
|------|------|
| GKE | 3 節點 e2-standard-4 |
| Cloud SQL | db-custom-4-16384 |
| Memorystore | 6GB Standard |

**驗收標準**:
- [ ] 所有 GCP 服務建立成功
- [ ] 服務間連接正常
- [ ] 監控指標可見

---

## Phase 8: 測試與驗證

### Task 8.1: 單元測試
**優先級**: P1 | **複雜度**: 3

**目標**: 撰寫核心邏輯單元測試

**執行步驟**:
- [ ] 建立 `tests/` 測試目錄
- [ ] 撰寫積分計算測試
- [ ] 撰寫防超賣機制測試
- [ ] 撰寫 API 端點測試

**測試範圍**:
- [ ] `test_score_calculation.py` - 積分公式正確性
- [ ] `test_inventory.py` - 庫存扣減邏輯
- [ ] `test_ranking.py` - 排名操作
- [ ] `test_api_*.py` - API 端點

**驗收標準**:
- [ ] 測試覆蓋率 > 80%
- [ ] 所有測試通過

---

### Task 8.2: k6 壓力測試腳本
**優先級**: P0 | **複雜度**: 4

**目標**: 設計並實作壓力測試

**執行步驟**:
- [ ] 建立 `k6-tests/` 目錄
- [ ] 撰寫基準測試腳本
- [ ] 撰寫高並發測試腳本 (1000+ VUs)
- [ ] 撰寫指數型負載腳本

**測試場景** (依據 PDF 需求):

**場景 1: 基準測試**
```javascript
export const options = {
  vus: 100,
  duration: '5m',
};
```

**場景 2: 高並發測試 (1000+ concurrent users)**
```javascript
export const options = {
  stages: [
    { duration: '1m', target: 1000 },
    { duration: '5m', target: 1000 },
    { duration: '1m', target: 0 },
  ],
};
```

**場景 3: 指數型負載 (截止前流量暴增)**
```javascript
export const options = {
  stages: [
    { duration: '5m', target: 100 },    // 平穩期
    { duration: '2m', target: 500 },    // 開始成長
    { duration: '2m', target: 1500 },   // 加速成長
    { duration: '1m', target: 2000 },   // 最後一分鐘峰值
  ],
};
```

**測試腳本內容**:
```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export default function() {
  // 1. 登入取得 Token
  const loginRes = http.post(`${BASE_URL}/api/v1/auth/login`, {
    email: `user${__VU}@test.com`,
    password: 'password123'
  });

  const token = loginRes.json('access_token');

  // 2. 出價
  const bidRes = http.post(`${BASE_URL}/api/v1/bids`, {
    campaign_id: CAMPAIGN_ID,
    price: 1000 + Math.random() * 1000
  }, {
    headers: { Authorization: `Bearer ${token}` }
  });

  check(bidRes, {
    'bid successful': (r) => r.status === 201,
  });

  sleep(0.1);
}
```

**驗收標準**:
- [ ] 1000+ VUs 同時競標
- [ ] 指數型負載模擬正確
- [ ] 產出測試報告

---

### Task 8.3: 一致性驗證測試
**優先級**: P0 | **複雜度**: 3

**目標**: 驗證防超賣機制有效性

**執行步驟**:
- [ ] 撰寫驗證腳本 `scripts/verify_consistency.py`
- [ ] 壓力測試後自動執行驗證
- [ ] 比對訂單數與庫存數

**驗證項目**:
```python
async def verify_no_overselling(campaign_id: str):
    # 1. 獲取活動庫存 K
    campaign = await get_campaign(campaign_id)
    stock_k = campaign.product.stock

    # 2. 統計訂單數量
    order_count = await count_orders(campaign_id)

    # 3. 驗證
    assert order_count <= stock_k, f"超賣! 訂單數 {order_count} > 庫存 {stock_k}"

    # 4. 驗證得標者為 Top K
    winners = await get_orders(campaign_id)
    top_k = await get_top_k_ranking(campaign_id, stock_k)

    for order in winners:
        assert order.user_id in [r.user_id for r in top_k], "非 Top K 用戶得標"

    print(f"✓ 一致性驗證通過: 訂單數 {order_count} ≤ 庫存 {stock_k}")
```

**驗收標準**:
- [ ] 訂單數 ≤ 庫存數 K (0% 超賣)
- [ ] 得標者皆為排名前 K 名
- [ ] 驗證報告輸出

---

### Task 8.4: Demo 準備
**優先級**: P0 | **複雜度**: 2

**目標**: 準備期末 Demo 展示

**執行步驟**:
- [ ] 準備 Demo 用測試資料
- [ ] 撰寫 Demo 執行腳本
- [ ] 錄製 Demo 影片 (< 3 分鐘)
- [ ] 準備簡報 (10-15 頁)

**Demo 展示內容** (依據 PDF 需求):
1. [ ] 系統啟動、商品上架設定
2. [ ] 使用者操作：登入、出價、即時排名變化
3. [ ] 壓力測試：1000+ concurrent users
4. [ ] 指數型負載：截止前出價頻率暴增
5. [ ] Scalability：CPU 上升 → Container 增加
6. [ ] 一致性驗證：訂單數 ≤ 庫存數

**簡報大綱**:
1. 系統簡介與架構圖
2. 核心技術說明
   - 高並發寫入處理
   - 即時排名計算與推播
   - 庫存一致性保證
3. 使用的平台、工具、套件
4. Scalability 設計
5. 測試設計與數據
6. 分工架構

**驗收標準**:
- [ ] Demo 影片 < 3 分鐘
- [ ] 展示所有必要項目
- [ ] 簡報 10-15 頁

---

## 任務優先級總覽

### P0 (必須完成 - 核心功能)
| Task | 說明 | 複雜度 |
|------|------|--------|
| 1.1-1.4 | 專案初始化 | 1-2 |
| 2.1-2.3 | 資料庫建置 | 2-3 |
| 3.1-3.2 | 用戶認證 | 2 |
| 3.4-3.8 | 商品/活動/出價/排名 API | 2-4 |
| 3.10 | 活動結算 | 4 |
| 4.1-4.4 | 防超賣機制 | 3-4 |
| 6.4-6.5 | 出價介面/排名看板 | 3-4 |
| 7.5 | HPA 自動擴展 | 3 |
| 8.2-8.4 | 壓力測試/驗證/Demo | 2-4 |

### P1 (應該完成 - 完整功能)
| Task | 說明 | 複雜度 |
|------|------|--------|
| 2.4-2.6 | 快取/種子資料/連接池 | 1-2 |
| 3.3, 3.11-3.12 | 用戶資訊/訂單/限流 | 1-3 |
| 5.1-5.4 | WebSocket 即時推播 | 2-3 |
| 6.1-6.3, 6.6 | 前端頁面 | 2-3 |
| 7.1-7.4, 7.6 | 容器化/部署 | 2-4 |
| 8.1 | 單元測試 | 3 |

### P2 (可選完成 - 加分項)
| Task | 說明 | 複雜度 |
|------|------|--------|
| 3.9 | 出價歷史 | 1 |

---

## 里程碑規劃

```
Week 1: Phase 1-2 (專案初始化 + 資料庫)
        ├── Task 1.1-1.4
        └── Task 2.1-2.6

Week 2: Phase 3 (後端核心服務)
        ├── Task 3.1-3.8 (認證/商品/出價/排名)
        └── Task 3.10-3.12 (結算/訂單/限流)

Week 3: Phase 4-5 (防超賣 + 即時推播)
        ├── Task 4.1-4.4
        └── Task 5.1-5.4

Week 4: Phase 6-7 (前端 + 部署)
        ├── Task 6.1-6.6
        └── Task 7.1-7.6

Week 5: Phase 8 (測試 + Demo)
        ├── Task 8.1-8.4
        └── Final Demo 準備
```

---

## 驗收檢查清單

### 功能驗收
- [ ] 會員可註冊、登入
- [ ] 管理員可上架商品、建立活動
- [ ] 用戶可出價、更新出價
- [ ] 排名看板即時更新 (< 5 秒)
- [ ] 活動結束自動結算
- [ ] 得標者收到通知

### 技術驗收
- [ ] 支援 1000+ concurrent users
- [ ] 出價回應時間 P95 < 2 秒
- [ ] 排名更新延遲 < 5 秒
- [ ] CPU > 70% 觸發自動擴展
- [ ] 訂單數 ≤ 庫存數 (0% 超賣)

### 部署驗收
- [ ] 所有服務 Container 化
- [ ] 部署到 GCP GKE
- [ ] HPA 自動擴展正常
- [ ] 監控指標可見

### Demo 驗收
- [ ] 影片 < 3 分鐘
- [ ] 展示所有必要項目
- [ ] 簡報 10-15 頁
- [ ] 一致性驗證通過

---

## 文件版本

| 版本 | 日期 | 修改內容 |
|------|------|----------|
| 1.0 | 2025-12-03 | 初版建立 |
| 1.1 | 2025-12-03 | 調整為 UV src-layout 專案結構 |
