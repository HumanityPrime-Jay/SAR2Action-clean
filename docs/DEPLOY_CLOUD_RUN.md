# 部署到 Google Cloud Run（Mac 操作版）

完成後會得到一個公開網址，例如 `https://sar2action-xxxxx.a.run.app`：

- `https://.../?demo=A`：NISAR 快取證據 + Gemini
- `https://.../?demo=B`：合成資料示範

架構很簡單：一個容器同時跑 FastAPI 後端，也提供 React 前端，所以前端和 API 在同一個網址。

---

## 0. 一次性準備

```bash
# 安裝 Google Cloud CLI
brew install --cask google-cloud-sdk

# 登入（會開瀏覽器）
gcloud auth login
```

到 <https://console.cloud.google.com> 做兩件事：

1. **建立專案**（例如 `sar2action-2026`），記下「專案 ID」。
2. **帳單 → 連結帳單帳戶**。Cloud Run 要求綁卡，但這個流量通常落在免費額度內。

```bash
# 把下面換成你的專案 ID
export PROJECT_ID=sar2action-2026
export REGION=asia-east1        # 台灣（彰化）機房

gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION

# 開啟需要的服務（約 1 分鐘）
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com
```

## 1. 放入科學快取資料（Demo A 需要）

向隊友拿 cache 檔，放進專案的 `data/cache/`（**不要 commit**，`.gitignore` 已經排除）：

```
data/cache/evidence_store.json
data/cache/fingerprint_store.json
data/cache/analysis_store.json
data/cache/layer_store.json      （有的話）
data/cache/layer_pngs/...        （有的話）
```

`.gcloudignore` 有刻意設定：部署時會上傳 `data/cache/`，但**不會**上傳金鑰檔、`.env`、原始 HDF5 檔。

## 2. 把 Gemini 金鑰放進 Secret Manager（只做一次）

金鑰不放程式碼、不放 GitHub，只存在 Google Cloud 的加密保管庫。

```bash
# 執行後貼上金鑰，按 Enter，再按 Ctrl+D
# （這樣金鑰不會留在終端機歷史紀錄）
gcloud secrets create gemini-api-key --data-file=-

# 允許 Cloud Run 讀取這個金鑰
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding gemini-api-key \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## 3. 部署（之後每次更新都只要跑這一段）

在專案根目錄（有 `Dockerfile` 的那層）執行：

```bash
gcloud run deploy sar2action \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --memory 2Gi --cpu 1 \
  --max-instances 1 --min-instances 0 \
  --session-affinity \
  --timeout 300 \
  --set-env-vars "SAR2ACTION_LLM_PROVIDER=gemini,SAR2ACTION_GEMINI_MODEL=gemini-3.1-flash-lite,SAR2ACTION_CORS_ORIGINS=" \
  --set-secrets "GEMINI_API_KEY=gemini-api-key:latest"
```

- 第一次會問要不要建立 Artifact Registry，回答 `Y`。
- 建置約 5–10 分鐘，在雲端完成，所以 M5 Mac 不用裝 Docker，也沒有 ARM/x86 架構問題。
- 完成後終端機會印出 `Service URL: https://...`。

### 參數說明

| 參數 | 為什麼 |
|---|---|
| `--max-instances 1` | **必要**。後端把調查 session 存在記憶體，多台機器會讓使用者的調查進度遺失。這也順便限制了成本上限。 |
| `--session-affinity` | 同一位使用者盡量連到同一台。 |
| `--memory 2Gi` | numpy、geopandas、rasterio 載入需要記憶體。 |
| `--min-instances 0` | 沒人用時不收費，但第一次打開會慢約 10–20 秒（冷啟動）。 |
| `SAR2ACTION_CORS_ORIGINS=`（空值） | 前後端同網址，不需要跨網域，所以關掉 CORS。比原本的 `*` 安全。 |

**評審期間建議**：把 `--min-instances 1` 打開，評審點進去就不會冷啟動。費用大約每天幾十元台幣，比賽結束後改回 0：

```bash
gcloud run services update sar2action --min-instances 1   # 評審期間
gcloud run services update sar2action --min-instances 0   # 比賽結束後
```

## 4. 驗證

```bash
URL=$(gcloud run services describe sar2action --format='value(status.url)')
curl $URL/api/health
curl $URL/api/agent/status     # 應看到 provider: gemini、status: online；cached_evidence 不是 blocked
open "$URL/?demo=A"
open "$URL/?demo=B"
```

看 log（出錯時第一個要看）：

```bash
gcloud run services logs read sar2action --limit 50
```

## 5. 防止被刷爆額度（強烈建議）

網站公開、又沒有登入，陌生人可以一直打 Gemini。

1. **Google AI Studio**：在 API key 所屬的專案設定每日請求上限（quota），或用免費層的金鑰。
2. **Google Cloud 預算警示**：到 Console 的「帳單 → 預算與快訊」，設定例如 NT$300 的警示。
3. `--max-instances 1` 已經限制了 Cloud Run 本身的費用上限。

## 常見問題

| 狀況 | 處理 |
|---|---|
| Demo A 顯示 data unavailable / blocked | `data/cache/` 沒有檔案，或檔名不對。放好後重新部署。 |
| `/api/agent/status` 顯示 provider 不是 gemini | 檢查 `--set-env-vars` 和 secret 名稱是否正確。 |
| 部署時出現 Permission denied on secret | 第 2 步的 `add-iam-policy-binding` 沒有執行。 |
| 地圖底圖不顯示 | 前端用的是 OSM 公開圖磚，屬於低流量用途。如果被限流，之後可以換成 MapTiler 或 Carto 的底圖。 |
| 想下線 | `gcloud run services delete sar2action` |
