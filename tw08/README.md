# TW-08A — Sentinel-2 L2A 多光譜實測與可行性驗證（雲林示範區）

本目錄 `tw08/` 為獨立實驗工作區，用來以真實 **Copernicus Sentinel-2 L2A（Element84 Earth Search STAC v1）** 多光譜影像，實測並評估 **TW-01 雲林 5 × 5 km 農業調查示範區（4,863 筆農田坵塊與 181 筆 SAR 變化候選坵塊）** 的多時相植被光譜分析可行性。

> **嚴格邊界聲明**：本工作區為唯讀交叉驗證（read-only on TW-01），**未修改** `sar/`、`tw01/`、`tw03/`、`tw07` 相關程式與資料（`backend/`、`frontend/`），亦**未訓練**任何未經驗證之作物分類模型或輸出作物種類／災損因果認定。

---

## 1. 目錄結構

- [download_s2_aoi.py](file:///D:/NASA/SAR2Action/tw08/download_s2_aoi.py) — 查詢 Element84 Earth Search STAC (`sentinel-2-l2a`, MGRS `51QTG`)，僅針對 AOI 視窗裁切下載 `B02, B03, B04, B08` (10 m) 與 `B05, B8A, B11, B12, SCL` (20 m)，保留完整整數網格對齊與 SHA-256 紀錄。
- [build_tw08a.py](file:///D:/NASA/SAR2Action/tw08/build_tw08a.py) — 執行 SCL 雲／雲影遮罩與 AOI/逐坵塊 QA、計算真實 NDVI (10 m) / NDRE (20 m) / LSWI (20 m)、產製透明地圖圖層 PNG 與 GeoTIFF、匯出 181 候選與 4,863 全區農田 CSV、進行 SAR vs Sentinel-2 無母數檢定與相關分析，並寫入 [manifest.json](file:///D:/NASA/SAR2Action/tw08/sentinel2-demo-v1/manifest.json)。
- [verify_tw08a.py](file:///D:/NASA/SAR2Action/tw08/verify_tw08a.py) — 驗證全部 36 檔輸入波段 SHA-256、29 檔輸出 SHA-256、嚴格 JSON 格式（禁止 `NaN`）、10 m (`510×512`) / 20 m (`255×256`) `EPSG:32651` 網格，以及 CSV 列數與零真值標籤聲明。
- [TW08A_QA_AND_FEASIBILITY_REPORT.md](file:///D:/NASA/SAR2Action/tw08/TW08A_QA_AND_FEASIBILITY_REPORT.md) — 完整實測 QA 報告與 5 項可行性問題實證結論。
- `inputs/` — 已裁切下載的 36 個 AOI GeoTIFF（4 日期 × 9 波段）與 [stac_inventory.json](file:///D:/NASA/SAR2Action/tw08/inputs/stac_inventory.json)。
- `sentinel2-demo-v1/` — TW-08A 驗證產物輸出目錄：
  - [manifest.json](file:///D:/NASA/SAR2Action/tw08/sentinel2-demo-v1/manifest.json)
  - [candidate_181_multitemporal_metrics.csv](file:///D:/NASA/SAR2Action/tw08/sentinel2-demo-v1/candidate_181_multitemporal_metrics.csv)（181 筆、56 欄）
  - [farmland_4863_multitemporal_metrics.csv](file:///D:/NASA/SAR2Action/tw08/sentinel2-demo-v1/farmland_4863_multitemporal_metrics.csv)（4,863 筆、56 欄）
  - 診斷總覽圖：
    - [s2_multitemporal_rgb_scl_overview.png](file:///D:/NASA/SAR2Action/tw08/sentinel2-demo-v1/s2_multitemporal_rgb_scl_overview.png)
    - [s2_ndvi_ndre_lswi_timeseries_map.png](file:///D:/NASA/SAR2Action/tw08/sentinel2-demo-v1/s2_ndvi_ndre_lswi_timeseries_map.png)
    - [s2_vs_sar_candidate_comparison.png](file:///D:/NASA/SAR2Action/tw08/sentinel2-demo-v1/s2_vs_sar_candidate_comparison.png)
  - 各日期原生解析度 GeoTIFF (`ndvi_*.tif`, `ndre_*.tif`, `lswi_*.tif`, `scl_*.tif`)、可用日期差值 GeoTIFF (`delta_*_20261011_20261105.tif`) 與 WebGIS `EPSG:3857` 預覽圖 (`*_overlay.png`)。

---

## 2. 本機重現指令

請在 repo 根目錄（`D:\NASA\SAR2Action`）使用既有 `.venv`：

```powershell
# 1. 重新從 Earth Search STAC 裁切下載 AOI 所需波段 (需對外網路)
d:\NASA\SAR2Action\.venv\Scripts\python.exe D:\NASA\SAR2Action\tw08\download_s2_aoi.py

# 2. 計算 SCL QA、NDVI/NDRE/LSWI、181/4863 逐坵塊指標與診斷圖 (可離線執行)
d:\NASA\SAR2Action\.venv\Scripts\python.exe D:\NASA\SAR2Action\tw08\build_tw08a.py

# 3. 驗證輸入輸出雜湊、網格解析度、CSV 列數與零分類聲明
d:\NASA\SAR2Action\.venv\Scripts\python.exe D:\NASA\SAR2Action\tw08\verify_tw08a.py
```

---

## 3. 網格對齊與輻射校正要點

- **空間網格**：`EPSG:32651`（UTM 51N），依 MGRS `51QTG` 20 m 原生原點 `(199980.0 E, 2700000.0 N)` 對齊至 `[222140.0, 2622180.0, 227260.0, 2627280.0]`（僅將 TW-01 X 邊界微調 ±10 m 以消除半像元偏移，完整涵蓋 TW-01 AOI 全部範圍）。
  - 10 m (`B02/B03/B04/B08`, `NDVI`)：`510 × 512` 像元
  - 20 m (`B05/B8A/B11/B12/SCL`, `NDRE`, `LSWI`)：`255 × 256` 像元（精確 `2×2` 整數嵌套）
- **輻射反射率轉換**：Element84 STAC 屬性標記 `earthsearch:boa_offset_applied = true`（Processing Baseline `05.13` 產品於 COG 入庫時已扣除 `-1000` BOA offset）。經以 `2026-10-11` `SCL = 4` 植被像元實測驗證，直接採用 `reflectance = uint16_dn * 0.0001`（`B04` 中位數 DN = `670.0`、`B08` = `3115.0` → NDVI `0.6440`），若錯誤二次減 `-0.1` 會導致 `89.8%` 植被紅光轉負值。
- **雲掩膜標準**：嚴格以 20 m `SCL` 類別 `{4: Vegetation, 5: Not Vegetated, 6: Water}` 為有效像元（10 m 柵格由 20 m `SCL` 以精確 `2×2` 最近鄰區塊對映），雲及雲影 `{3, 8, 9, 10}` 與未分類／暗影等一律遮罩為 `NaN`，**不進行合成補值**。
