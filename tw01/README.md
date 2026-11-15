# Phase TW-01 — 雲林農業監測

獨立工作區位於 `tw01`。原目錄未提供 Git metadata，因此在此目錄保存本階段處理程式、來源及交付資料。

## 建置與驗收

從 SAR2Action 目錄執行下列指令。下載程式沿用本機 Earthdata 認證，下載檔寫入 `tw01/inputs`。農田 ZIP 也放在這個目錄，名稱為 `yunlin-parcels.zip`。

```powershell
.\.venv\Scripts\python.exe -B tw01/download_rtc.py
.\.venv\Scripts\python.exe -B tw01/build_demo.py
.\.venv\Scripts\python.exe -B tw01/verify_demo.py
```

原始資料來自 [ASF 災前紀錄](https://cmr.earthdata.nasa.gov/search/concepts/G4367321249-ASF.umm_json)、[ASF 災後紀錄](https://cmr.earthdata.nasa.gov/search/concepts/G4389918405-ASF.umm_json) 及[農業部雲林農田坵塊圖](https://data.moa.gov.tw/GetOpenDataFile.aspx?id=I75&FileType=DataMore&RID=44143)。輸入及發布資產的雜湊都記錄於 manifest。公開分享以生成的資料包為範圍。

## UI 與 Agent

載入 `taiwan-agricultural-demo-v1/manifest.json` 並使用同目錄的 `schema.json` 驗證。資產 href 相對於 manifest。AOI 和坵塊 GeoJSON 為 WGS84。當狀態為 `verified_observation`，可讀取 `evidence_id`、`analysis.layers`、`analysis.polarizations.VV/VH` 和共同有效覆蓋率。MapLibre image source 可使用各圖層的 `overlay.href` 和 `overlay.coordinates_lon_lat`，順序為左上、右上、右下、左下。其他狀態請顯示資料尚未可用及 `missing_assets` 或 `failure_reason`。縣級農損單獨位於 `official_background`。

RTC 採同一 Sentinel-1D burst 的 gamma0。每個像元須在兩期 VV、VH 均為有限正功率，且兩期產品 mask 均為 0。無法證明格網完全相同時停止。面積與覆蓋統計以 AOI 內像元中心計算。候選區和坵塊的 3 dB 門檻僅供勘查優先排序，並非損失模型。未建立獨立穩定參考區以量測輻射偏移。

初版開發紀錄（2026-11-14）含 ASF 公開紀錄對帳、坵塊 ZIP CRC、5 × 5 km 裁切、兩期 RTC 檔案取得門檻、manifest schema 與 SHA-256 驗收。官方開工規則與既有成果使用邊界由 [NASA GO Team 開工公告](https://github.com/nasa/spaceapps/discussions/1777) 及 Local Lead 書面判定。臺灣 RTC 是 Sentinel-1D 應用，核心 NISAR 案例及既有快取須另行取得重用確認。

同日通過實資料建置及驗收。ASF 專用應用程式核准後取得兩期共六檔，均與 CMR 檔案大小相符。六檔共用 EPSG:32651、30 m、1,564 列 × 3,305 欄及相同 transform。兩期 mask 在 AOI 內皆為 class 0，VV/VH 各期均有 27,785 個有效像元。來源 Sentinel-1 處理器版本為 4.3 與 4.11，OPERA 處理版本及 RTC 算法一致。未施加幅度偏移校正。

`verify_demo.py` 驗證資料包 schema、輸出 SHA-256、PNG、AOI 面積、坵塊幾何、GeoTIFF 格網、共同有效像元、統計中位數與候選 raster。實際結果為 4,863 個農田圖徵，幾何聯集 18.769 km²。1,070 筆通過坵塊篩選像元門檻，其中 181 筆為待查候選。AOI 候選 raster 含 5,603 個像元。
