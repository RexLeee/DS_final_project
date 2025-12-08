# K6 負載測試 - 限時搶購系統

## 前置需求

- 安裝 [k6](https://k6.io/docs/getting-started/installation/)
- kubectl 已設定 GKE 叢集存取權限
- Backend 已部署至 GKE

## 環境變數

| 變數               | 說明              | 預設值                    |
| ------------------ | ----------------- | ------------------------- |
| `BASE_URL`       | Backend API 網址  | `http://localhost:8000` |
| `CAMPAIGN_ID`    | 進行中的活動 UUID | (必填)                    |
| `USER_POOL_SIZE` | 測試使用者數量    | `1000`                  |

## 快速開始

### 1. 取得 Backend Pod 名稱

```bash
POD=$(kubectl get pods -n flash-sale -l app=backend -o jsonpath='{.items[0].metadata.name}')
echo "Backend pod: $POD"
```

### 2. 清除舊資料（選用）

```bash
kubectl exec -n flash-sale $POD -- python -c "
import asyncio
from app.core.database import engine
from app.models import Bid, Order, Campaign
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

async def clear_all():
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        await db.execute(delete(Order))
        await db.execute(delete(Bid))
        await db.execute(delete(Campaign))
        await db.commit()
        print('資料庫已清空！')

asyncio.run(clear_all())
"
```

### 3. 建立測試資料

```bash
# 建立 60 分鐘的活動
kubectl exec -n flash-sale $POD -- python -m scripts.seed_data --duration 60
```

輸出範例：

```
============================================================
Seed data complete!
  Users: 1001
  Products: 5
  Active Campaign: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx  <-- 複製這個！
============================================================
```

### 4. 執行測試

```bash
# 設定變數
export BASE_URL=<url>
export CAMPAIGN_ID=<貼上活動ID>

# 執行基準測試（100 VUs，5 分鐘）
k6 run baseline.js -e BASE_URL=$BASE_URL -e CAMPAIGN_ID=$CAMPAIGN_ID

# 執行高併發測試（1000 VUs）
k6 run high-concurrency.js -e BASE_URL=$BASE_URL -e CAMPAIGN_ID=$CAMPAIGN_ID

# 執行指數成長負載測試
k6 run exponential-load.js -e BASE_URL=$BASE_URL -e CAMPAIGN_ID=$CAMPAIGN_ID

# 執行完整示範測試（涵蓋所有 PDF 需求）
k6 run full-demo-test.js -e BASE_URL=$BASE_URL -e CAMPAIGN_ID=$CAMPAIGN_ID
```

## 測試檔案說明

| 檔案                    | 說明                      | VUs  | 時長    |
| ----------------------- | ------------------------- | ---- | ------- |
| `baseline.js`         | 系統功能驗證              | 100  | 5 分鐘  |
| `high-concurrency.js` | 1000+ 併發使用者          | 1000 | 10 分鐘 |
| `exponential-load.js` | 出價頻率指數成長          | 1000 | 10 分鐘 |
| `full-demo-test.js`   | 完整示範（所有 PDF 需求） | 1000 | 9 分鐘  |

## PDF 需求對照

| 需求                              | 對應測試檔案                                   |
| --------------------------------- | ---------------------------------------------- |
| 模擬至少 1000 個 concurrent users | `high-concurrency.js`, `full-demo-test.js` |
| 出價頻率呈現指數型成長            | `exponential-load.js`, `full-demo-test.js` |
| HPA 自動擴展展示                  | `high-concurrency.js`, `full-demo-test.js` |
| 不可超賣（一致性檢查）            | `verify-consistency.js`                      |

## 測試期間監控指令

```bash
# 監看 HPA 擴展狀態
kubectl get hpa -n flash-sale -w

# 監看 Pod 數量變化
kubectl get pods -n flash-sale -w

# 查看 Backend 日誌
kubectl logs -n flash-sale -l app=backend -f --tail=100
```
