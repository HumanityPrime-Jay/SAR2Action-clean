"""Read-only service for TW-05: Taiwan Agricultural Surface Change Investigation.

Dynamically loads real verified satellite packages from:
- `tw03/nisar-demo-v1/` (NISAR L-band HH/HV 20 m GCOV, pre-typhoon 2026-10-04 -> 2026-10-16)
- `tw01/taiwan-agricultural-demo-v1/` (Sentinel-1D C-band VV/VH 30 m OPERA RTC, cross-event 2026-10-14 -> 2026-10-26)

Does NOT modify `sar/`, `tw01/`, `tw03/`, or synthesize numbers when assets are missing.
"""

from __future__ import annotations

import csv
import json
import math
import pathlib
from typing import Any, Literal

from fastapi import HTTPException

from backend.app.schemas.taiwan_agro import (
    TwAgroCandidateParcel,
    TwAgroDisasterAnnouncement,
    TwAgroDistributionStats,
    TwAgroFrameworkSeparationItem,
    TwAgroLayerOverlay,
    TwAgroLegendStop,
    TwAgroOverviewResponse,
    TwAgroParcelOpticalEpoch,
    TwAgroParcelOpticalMetrics,
    TwAgroParcelScreeningSummary,
    TwAgroPolarizationStats,
    TwAgroReliefCardInfo,
    TwAgroReliefCatalog,
    TwAgroReliefEstimateRequest,
    TwAgroReliefEstimateResponse,
    TwAgroReliefScheduleItem,
    TwAgroSceneProvenance,
    TwAgroSensorPackage,
    TwAgroSentinel2ClearDelta,
    TwAgroSentinel2Package,
    TwAgroSentinel2SceneSummary,
)

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_TW01_DIR = PROJECT_ROOT / "tw01" / "taiwan-agricultural-demo-v1"
DEFAULT_TW03_DIR = PROJECT_ROOT / "tw03" / "nisar-demo-v1"
DEFAULT_DATA_DIR = PROJECT_ROOT / "backend" / "data"

ALLOWED_TW01_ASSETS = frozenset({
    "delta_vv_overlay.png",
    "delta_vh_overlay.png",
    "farmland.png",
    "radar-change.png",
})
ALLOWED_TW03_ASSETS = frozenset({
    "delta_hh.png",
    "delta_hv.png",
})
DEFAULT_TW08_DIR = PROJECT_ROOT / "tw08" / "sentinel2-demo-v1"
ALLOWED_TW08_ASSETS = frozenset({
    "ndvi_20261011_overlay.png",
    "ndvi_20261016_overlay.png",
    "ndvi_20261026_overlay.png",
    "ndvi_20261105_overlay.png",
    "delta_ndvi_20261011_20261105_overlay.png",
    "s2_multitemporal_rgb_scl_overview.png",
    "s2_ndvi_ndre_lswi_timeseries_map.png",
    "s2_vs_sar_candidate_comparison.png",
})

def _float_or_none(raw: str | None) -> float | None:
    if raw is None or raw == "":
        return None
    val = float(raw)
    return val if math.isfinite(val) else None


def _bbox_from_corners(corners: list[list[float]]) -> list[float]:
    lons = [pt[0] for pt in corners]
    lats = [pt[1] for pt in corners]
    return [min(lons), min(lats), max(lons), max(lats)]


def _format_area_ha(area_ha: float) -> str:
    if abs(area_ha * 10_000.0 - round(area_ha * 10_000.0)) < 1e-6:
        return f"{area_ha:.4f}"
    return f"{area_ha:.8f}".rstrip("0").rstrip(".")


def _compute_geom_centroid_and_bbox(geometry: dict[str, Any]) -> tuple[list[float], list[float]]:
    """Compute bounding box and vertex centroid of a WGS84 Polygon or MultiPolygon."""
    gtype = geometry.get("type")
    coords = geometry.get("coordinates", [])
    pts: list[list[float]] = []

    if gtype == "Polygon" and coords:
        pts = list(coords[0])
    elif gtype == "MultiPolygon" and coords:
        for poly in coords:
            if poly and poly[0]:
                pts.extend(poly[0])

    if not pts:
        return [120.30, 23.71], [120.275, 23.687, 120.325, 23.733]

    # Exclude closing duplicate vertex when averaging centroid if ring is closed
    ring_pts = pts[:-1] if len(pts) > 1 and pts[0] == pts[-1] else pts
    mean_lon = sum(p[0] for p in ring_pts) / len(ring_pts)
    mean_lat = sum(p[1] for p in ring_pts) / len(ring_pts)
    lons = [p[0] for p in pts]
    lats = [p[1] for p in pts]
    return [round(mean_lon, 6), round(mean_lat, 6)], [
        min(lons),
        min(lats),
        max(lons),
        max(lats),
    ]


def _geometry_touches_bbox(
    geometry: dict[str, Any],
    aoi_bbox: list[float] | None,
    tol: float = 2e-4,
) -> bool:
    """Return True if any vertex of Polygon/MultiPolygon lies on the AOI clip perimeter."""
    if not aoi_bbox or len(aoi_bbox) != 4:
        return False
    min_lon, min_lat, max_lon, max_lat = aoi_bbox
    gtype = geometry.get("type")
    coords = geometry.get("coordinates", [])
    rings: list[list[list[float]]] = []
    if gtype == "Polygon":
        rings = coords
    elif gtype == "MultiPolygon":
        for poly in coords:
            rings.extend(poly)
    for ring in rings:
        for pt in ring:
            if (
                abs(pt[0] - min_lon) <= tol
                or abs(pt[0] - max_lon) <= tol
                or abs(pt[1] - min_lat) <= tol
                or abs(pt[1] - max_lat) <= tol
            ):
                return True
    return False


def _parse_dist(raw: dict[str, Any] | None) -> TwAgroDistributionStats | None:
    if not raw or not isinstance(raw, dict):
        return None
    return TwAgroDistributionStats(
        mean=float(raw["mean"]),
        median=float(raw["median"]),
        std=float(raw["std"]),
        min=float(raw["min"]),
        max=float(raw["max"]),
        p10=float(raw["p10"]),
        p25=float(raw["p25"]),
        p50=float(raw["p50"]),
        p75=float(raw["p75"]),
        p90=float(raw["p90"]),
    )


def _read_json_safe(path: pathlib.Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


class TaiwanAgroService:
    """Service serving verified TW-01 & TW-03 Yunlin agricultural investigation packages."""

    def __init__(
        self,
        tw01_dir: pathlib.Path | None = None,
        tw03_dir: pathlib.Path | None = None,
        data_dir: pathlib.Path | None = None,
        tw08_dir: pathlib.Path | None = None,
    ) -> None:
        self.tw01_dir = pathlib.Path(tw01_dir) if tw01_dir is not None else DEFAULT_TW01_DIR
        self.tw03_dir = pathlib.Path(tw03_dir) if tw03_dir is not None else DEFAULT_TW03_DIR
        self.data_dir = pathlib.Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
        if tw08_dir is not None:
            self.tw08_dir = pathlib.Path(tw08_dir)
        elif tw01_dir is not None or tw03_dir is not None:
            self.tw08_dir = self.tw01_dir / "__tw08_unconfigured__"
        else:
            self.tw08_dir = DEFAULT_TW08_DIR

    def _build_unavailable_nisar(
        self,
        *,
        status: str,
        missing_assets: list[str],
        failure_reason: str,
        evidence_id: str | None = None,
    ) -> TwAgroSensorPackage:
        return TwAgroSensorPackage(
            package_id="nisar_tw03",
            schema_version="nisar-tw03-demo/1.0",
            status=status,
            available=False,
            missing_assets=missing_assets,
            failure_reason=failure_reason,
            evidence_id=evidence_id,
            sensor_name="NASA-ISRO NISAR L-band",
            band_name="L-band (~24 cm, HH / HV)",
            product_type="NISAR_L2_GCOV",
            observation_role_badge="颱風前觀測 (Pre-Typhoon Observation)",
            observation_window_note=(
                "兩期觀測皆位於 2026-10-23/24 颱風影響時窗之前（2026-10-04 → 2026-10-16），"
                "嚴禁描述為颱風災損。"
            ),
            not_supported_claims=[
                "不得描述為颱風災損（兩期皆在颱風前）",
                "不得與 Sentinel-1D C-band 資料直接相減",
                "不得以未驗證之資料替代實測數據",
            ],
        )

    def _load_nisar_tw03(self) -> tuple[TwAgroSensorPackage, list[float] | None]:
        manifest_path = self.tw03_dir / "manifest.json"
        manifest = _read_json_safe(manifest_path)
        if manifest is None:
            return (
                self._build_unavailable_nisar(
                    status="missing_manifest",
                    missing_assets=["tw03/nisar-demo-v1/manifest.json"],
                    failure_reason="無法讀取 TW-03 NISAR manifest.json，顯示為無法使用（未使用合成資料）。",
                ),
                None,
            )

        status = str(manifest.get("status", "unknown"))
        evidence_id = manifest.get("evidence_id")
        missing_assets: list[str] = list(manifest.get("missing_assets", []))

        stats_href = manifest.get("statistics_href", "statistics.json")
        evidence_href = manifest.get("evidence_href", "evidence.json")
        aoi_href = manifest.get("aoi_href", "aoi.geojson")

        for rel in (stats_href, evidence_href, aoi_href):
            if not (self.tw03_dir / rel).is_file():
                missing_assets.append(rel)

        raw_layers = manifest.get("layers", [])
        for lyr in raw_layers:
            href = lyr.get("overlay", {}).get("href")
            if not href or not (self.tw03_dir / href).is_file():
                missing_assets.append(href or f"{lyr.get('layer_id', 'unknown')}.png")

        if status != "verified_observation" or missing_assets:
            reason = (
                f"TW-03 NISAR 資料狀態為 `{status}`"
                if status != "verified_observation"
                else f"TW-03 NISAR 缺少必要資產：{', '.join(missing_assets)}"
            )
            return (
                self._build_unavailable_nisar(
                    status=status,
                    missing_assets=missing_assets,
                    failure_reason=reason,
                    evidence_id=evidence_id,
                ),
                None,
            )

        stats_data = _read_json_safe(self.tw03_dir / stats_href)
        evidence_data = _read_json_safe(self.tw03_dir / evidence_href)
        if stats_data is None or evidence_data is None:
            return (
                self._build_unavailable_nisar(
                    status="corrupt_metadata",
                    missing_assets=[stats_href, evidence_href],
                    failure_reason="TW-03 statistics.json 或 evidence.json 解析失敗。",
                    evidence_id=evidence_id,
                ),
                None,
            )

        grid = manifest.get("grid", {})
        spacing = [float(x) for x in grid.get("spacing_m", [20.0, 20.0])]
        window_shape = [int(x) for x in grid.get("window_shape", [])]
        crs_epsg = int(grid.get("epsg", 32651))

        scenes_out: list[TwAgroSceneProvenance] = []
        raw_scenes = manifest.get("scenes", [])
        for idx, sc in enumerate(raw_scenes):
            epoch: Literal["T0", "T1"] = "T0" if idx == 0 else "T1"
            track_num = sc.get("track_number")
            frame_num = sc.get("frame_number")
            pass_dir = sc.get("orbit_pass_direction", "")
            look_dir = sc.get("look_direction", "")
            maturity = sc.get("data_maturity", "")
            crid = sc.get("crid", "")
            scenes_out.append(
                TwAgroSceneProvenance(
                    epoch=epoch,
                    scene_id=sc["scene_id"],
                    granule_id=sc.get("granule_id", ""),
                    acquisition_utc=sc.get("acquisition_start_utc", ""),
                    source_url=sc.get("url", ""),
                    metadata_url=sc.get("metadata_url"),
                    sha256=sc.get("sha256"),
                    track_frame_note=f"Track {track_num} / Frame {frame_num} ({pass_dir}, {look_dir}-looking, CRID {crid} {maturity})",
                    processor_version=sc.get("product_version"),
                )
            )

        t0_utc = scenes_out[0].acquisition_utc if len(scenes_out) >= 1 else None
        t1_utc = scenes_out[1].acquisition_utc if len(scenes_out) >= 2 else None

        pol_stats_out: dict[str, TwAgroPolarizationStats] = {}
        stats_pols = stats_data.get("polarizations", {})
        ev_t0 = evidence_data.get("t0_db", {})
        ev_t1 = evidence_data.get("t1_db", {})
        ev_delta = evidence_data.get("delta_db", {})
        ev_mag = evidence_data.get("magnitude_db", {})

        for pol in ("HH", "HV"):
            st_pol = stats_pols.get(pol)
            if not st_pol:
                pol_stats_out[pol] = TwAgroPolarizationStats(polarization=pol, available=False)
                continue
            pol_stats_out[pol] = TwAgroPolarizationStats(
                polarization=pol,
                available=True,
                t0_db=_parse_dist(st_pol.get("t0_distribution_db") or ev_t0.get(pol)),
                t1_db=_parse_dist(st_pol.get("t1_distribution_db") or ev_t1.get(pol)),
                delta_db=_parse_dist(st_pol.get("delta_distribution_db") or ev_delta.get(pol)),
                magnitude_db=_parse_dist(st_pol.get("magnitude_distribution_db") or ev_mag.get(pol)),
                positive_change_fraction=st_pol.get("positive_change_fraction"),
                negative_change_fraction=st_pol.get("negative_change_fraction"),
            )

        layers_out: dict[str, TwAgroLayerOverlay] = {}
        asset_sha = manifest.get("asset_sha256", {})
        union_bbox: list[float] | None = None

        for lyr in raw_layers:
            lid = lyr["layer_id"]
            pol = lyr["polarization"]
            ov = lyr["overlay"]
            href = ov["href"]
            corners = ov["coordinates_lon_lat"]
            bbox = _bbox_from_corners(corners)
            union_bbox = bbox if union_bbox is None else [
                min(union_bbox[0], bbox[0]),
                min(union_bbox[1], bbox[1]),
                max(union_bbox[2], bbox[2]),
                max(union_bbox[3], bbox[3]),
            ]
            legend = lyr.get("legend", {})
            stops = [
                TwAgroLegendStop(
                    value=float(s["value"]),
                    color=str(s["color"]),
                    label=str(s["label"]),
                )
                for s in legend.get("stops", [])
            ]
            layers_out[lid] = TwAgroLayerOverlay(
                layer_id=lid,
                polarization=pol,
                title=legend.get("title", f"Signed Δ{pol} (dB)"),
                units=lyr.get("units", "dB"),
                overlay_url=f"/api/tw-agro/assets/tw03/{href}",
                geotiff_filename=lyr.get("geotiff_href"),
                render_range_db=[
                    float(legend.get("min_value", -4.0)),
                    float(legend.get("max_value", 4.0)),
                ],
                coordinates_lon_lat=corners,
                bbox_wgs84=bbox,
                legend_stops=stops,
                positive_change_meaning=legend.get("positive_change_meaning"),
                negative_change_meaning=legend.get("negative_change_meaning"),
                prohibited_labels_notice=legend.get(
                    "prohibited_labels_notice",
                    "Radar backscatter or change in dB only — never labeled as crop damage or yield loss.",
                ),
                overlay_sha256=asset_sha.get(href),
            )

        hh_stats = stats_pols.get("HH", {})
        aoi_cov = hh_stats.get("coverage_ratio")
        valid_area_km2 = hh_stats.get("valid_area_km2")
        valid_area_ha = hh_stats.get("valid_area_ha")

        mask_rule = (
            stats_data.get("processing_metadata", {}).get("mask_rule")
            or evidence_data.get("processing_metadata", {}).get("mask_rule")
        )

        pkg = TwAgroSensorPackage(
            package_id="nisar_tw03",
            schema_version=str(manifest.get("schema_version", "nisar-tw03-demo/1.0")),
            status=status,
            available=True,
            missing_assets=[],
            failure_reason=None,
            evidence_id=evidence_id,
            sensor_name=str(manifest.get("sensor", "NASA-ISRO NISAR L-band")),
            band_name="L-band (~24 cm, HH / HV)",
            product_type=f"{manifest.get('collection', 'NISAR_L2_GCOV_PROVISIONAL_V1')} (20 m)",
            algorithm_version=manifest.get("algorithm_version"),
            observation_role_badge="颱風前觀測 (Pre-Typhoon Observation)",
            observation_window_note=(
                "T0 = 2026-10-04 UTC、T1 = 2026-10-16 UTC，兩期皆在 2026-10-23/24 颱風影響前；"
                "此為颱風前地表基線 L-band 背向散射變化，不得寫成颱風災損。"
            ),
            crs_epsg=crs_epsg,
            pixel_spacing_m=spacing,
            grid_shape=window_shape,
            t0_acquisition_utc=t0_utc,
            t1_acquisition_utc=t1_utc,
            polarizations=["HH", "HV"],
            valid_pixel_count=int(stats_data["valid_pixel_count"]),
            total_reference_pixel_count=int(stats_data["requested_pixel_count"]),
            coverage_ratio=float(stats_data["coverage_ratio"]),
            aoi_coverage_ratio=float(aoi_cov) if aoi_cov is not None else None,
            valid_area_km2=float(valid_area_km2) if valid_area_km2 is not None else None,
            valid_area_ha=float(valid_area_ha) if valid_area_ha is not None else None,
            scenes=scenes_out,
            polarization_stats=pol_stats_out,
            layers=layers_out,
            limitations=list(manifest.get("limitations", [])),
            not_supported_claims=[
                "不得描述為颱風災損（兩期觀測皆早於 2026-10-23/24 颱風影響時窗）",
                "單憑 L-band 背向散射變化不能判定農損原因、減產程度或救助資格",
                "NISAR L-band HH/HV 與 Sentinel-1D C-band VV/VH 不可直接跨感測器相減",
                "RFI likelihood 不作為跨景定量品質分數",
            ],
            processing_notes=[
                "使用既有 sar2action-change-engine-v1.0.0（未修改任何科學運算）",
                "EvidenceRecord 外接 255×254 格網視窗覆蓋率為 97.39%（63,080 / 64,770）；AOI 多邊形內部有效覆蓋率為 100.00%（無遮罩剔除或負功率像元）",
                "產品成熟度：PROVISIONAL P05023（Ascending/Descending 一致性：Track 61 / Frame 76 Descending Left-looking）",
            ],
            mask_rule=mask_rule,
            asset_sha256={k: str(v) for k, v in asset_sha.items()},
        )
        return pkg, union_bbox

    def _build_unavailable_s1(
        self,
        *,
        status: str,
        missing_assets: list[str],
        failure_reason: str,
        evidence_id: str | None = None,
    ) -> tuple[TwAgroSensorPackage, TwAgroParcelScreeningSummary]:
        pkg = TwAgroSensorPackage(
            package_id="s1_tw01",
            schema_version="taiwan-agricultural-demo/1.0",
            status=status,
            available=False,
            missing_assets=missing_assets,
            failure_reason=failure_reason,
            evidence_id=evidence_id,
            sensor_name="Sentinel-1D C-band (OPERA RTC)",
            band_name="C-band (~5.6 cm, VV / VH)",
            product_type="OPERA_L2_RTC-S1_V1",
            observation_role_badge="跨事件觀測 (Cross-Event Observation)",
            observation_window_note=(
                "T0 = 2026-10-14 → T1 = 2026-10-26 跨事件觀測，雷達變化不代表一定由颱風造成。"
            ),
            not_supported_claims=[
                "不代表變化一定由颱風造成（可能反映收割、整地、灌溉或降雨土壤濕度差異）",
                "待查農田候選僅為 3 dB 勘查優先排序門檻，並非已確認農損",
                "不得與 NISAR L-band 直接跨感測器相減",
            ],
        )
        screening = TwAgroParcelScreeningSummary(
            available=False,
            missing_assets=missing_assets,
            failure_reason=failure_reason,
            mandatory_non_damage_notice=(
                "待查農田候選資料目前無法使用（未以合成資料替代）。"
            ),
            candidates=[],
        )
        return pkg, screening

    def _load_s1_tw01(
        self,
    ) -> tuple[
        TwAgroSensorPackage,
        TwAgroParcelScreeningSummary,
        TwAgroReliefCardInfo,
        int | None,
        str | None,
        list[float] | None,
    ]:
        default_relief = TwAgroReliefCardInfo(
            title="農業部農糧署官方農業救助公告資訊卡",
            official_source_name="農業部農糧署（Agriculture and Food Agency, MOA）",
            official_report_url="https://www.afa.gov.tw/cht/index.php?article_id=34384&code=list&flag=detail&ids=717",
            moa_open_data_url="https://data.moa.gov.tw/GetOpenDataFile.aspx?id=I75&FileType=DataMore&RID=44143",
            moa_relief_portal_url="https://www.afa.gov.tw/cht/index.php?code=list&ids=717",
            reporting_scope="County-level reporting only",
            yunlin_reported_loss_twd=None,
            applicable_items_summary=(
                "農業部 115年10月26日農糧字第1151112527F號公告雲林縣全縣現金救助及低利貸款品項："
                "雜糧（一）～（三）、蔬菜（一）～（七）（非屬森林副產物之竹筍除外）、原料甘蔗、青割玉米、"
                "塑膠布溫網室及水平棚架網室；另於 115年10月30日以農糧字第1151112552B號公告增列「洋蔥苗圃」"
                "（損害率須達 20% 以上，未達 20% 不予救助）。"
            ),
            application_deadline_guidance=(
                "【受理期限已截止】一般作物及設施受理期限為 115年10月27日起至11月9日止；"
                "洋蔥苗圃為 115年10月31日起至11月13日止（雲林縣落花生若於前次8月下旬豪雨已向公所申報者得免重複申請，由公所合併審理）。"
                "截至 2026-11-14，上述法定受理期限均已屆滿，請農民勿誤認目前仍可就本次公告提出一般申請；"
                "實際個案仍應以農業部、農糧署及雲林縣各鄉鎮市公所最新公告與個案核定為準。"
            ),
            competent_authority="農業部（MOA）／農業部農糧署（AFA）／雲林縣政府農業處及各鄉鎮市區公所",
            mandatory_disclaimer=(
                "本系統僅提供衛星雷達回波變化科學指標與農業部歷史公告連結，系統不自動判定救助資格或補助金額，"
                "亦不代表任何區塊已符合政府災害救助標準；且本次公告法定受理期限（115/11/09 及 115/11/13）已截止，"
                "請勿誤認為現行開放申報介面。"
            ),
        )

        manifest_path = self.tw01_dir / "manifest.json"
        manifest = _read_json_safe(manifest_path)
        if manifest is None:
            pkg, screening = self._build_unavailable_s1(
                status="missing_manifest",
                missing_assets=["tw01/taiwan-agricultural-demo-v1/manifest.json"],
                failure_reason="無法讀取 TW-01 Sentinel-1D manifest.json，顯示為無法使用（未使用合成資料）。",
            )
            return pkg, screening, default_relief, None, None, None

        status = str(manifest.get("status", "unknown"))
        evidence_id = manifest.get("evidence_id")
        missing_assets: list[str] = list(manifest.get("missing_assets", []))

        aoi_href = manifest.get("aoi_href", "aoi.geojson")
        farmland_info = manifest.get("farmland", {})
        farmland_href = farmland_info.get("href", "farmland.geojson")
        farmland_preview = farmland_info.get("preview_png")

        analysis = manifest.get("analysis", {})
        raw_layers = analysis.get("layers", [])
        parcel_screening = analysis.get("parcel_screening", {})
        candidates_href = parcel_screening.get("geometry_href", "candidate-parcels.geojson")

        for rel in (aoi_href, farmland_href, candidates_href):
            if not (self.tw01_dir / rel).is_file():
                missing_assets.append(rel)
        for lyr in raw_layers:
            ov_href = lyr.get("overlay", {}).get("href")
            if not ov_href or not (self.tw01_dir / ov_href).is_file():
                missing_assets.append(ov_href or f"{lyr.get('polarization', 'unknown')}_overlay.png")

        if status != "verified_observation" or missing_assets:
            reason = (
                f"TW-01 Sentinel-1D 資料狀態為 `{status}`"
                if status != "verified_observation"
                else f"TW-01 Sentinel-1D 缺少必要資產：{', '.join(missing_assets)}"
            )
            pkg, screening = self._build_unavailable_s1(
                status=status,
                missing_assets=missing_assets,
                failure_reason=reason,
                evidence_id=evidence_id,
            )
            return pkg, screening, default_relief, None, None, None

        # Read official background loss directly from manifest (never hardcoded)
        off_bg = manifest.get("official_background", {})
        yunlin_loss = off_bg.get("yunlin_reported_loss_twd")
        relief_info = TwAgroReliefCardInfo(
            title="農業部農糧署官方農業救助公告與縣級農損背景資訊卡",
            official_source_name=f"農業部農糧署（{off_bg.get('source', 'Agriculture and Food Agency final report')}）",
            official_report_url=str(off_bg.get("url", default_relief.official_report_url)),
            moa_open_data_url=str(farmland_info.get("source_url", default_relief.moa_open_data_url)),
            moa_relief_portal_url=default_relief.moa_relief_portal_url,
            reporting_scope=str(off_bg.get("scope", "County-level reporting only")),
            yunlin_reported_loss_twd=int(yunlin_loss) if yunlin_loss is not None else None,
            applicable_items_summary=default_relief.applicable_items_summary,
            application_deadline_guidance=default_relief.application_deadline_guidance,
            competent_authority="農業部（MOA）／農業部農糧署（AFA）／雲林縣政府農業處及各鄉鎮市區公所",
            mandatory_disclaimer=default_relief.mandatory_disclaimer,
        )

        # Grid & spacing
        grid = analysis.get("grid", {})
        crs_str = str(grid.get("crs", "EPSG:32651"))
        crs_epsg = int(crs_str.split(":")[-1]) if ":" in crs_str else 32651
        spacing = [float(x) for x in grid.get("spacing_m", [30.0, 30.0])]
        grid_shape = [int(x) for x in grid.get("shape", [])]

        # Scenes
        scenes_out: list[TwAgroSceneProvenance] = []
        raw_scenes = manifest.get("scenes", [])
        rtc_tags_by_epoch = analysis.get("rtc_tags_by_epoch", [])
        for idx, sc in enumerate(raw_scenes):
            epoch: Literal["T0", "T1"] = "T0" if idx == 0 else "T1"
            assets = sc.get("assets", {})
            vv_asset = assets.get("VV", {})
            vh_asset = assets.get("VH", {})
            tags = (
                rtc_tags_by_epoch[idx].get("VV", {})
                if idx < len(rtc_tags_by_epoch)
                else {}
            )
            orbit_num = tags.get("ABSOLUTE_ORBIT_NUMBER", "")
            burst_id = tags.get("BURST_ID", "")
            pass_dir = tags.get("ORBIT_PASS_DIRECTION", "ascending")
            s1_proc = tags.get("SOURCE_DATA_SOFTWARE_VERSION")
            scenes_out.append(
                TwAgroSceneProvenance(
                    epoch=epoch,
                    scene_id=sc["scene_id"],
                    granule_id=sc.get("cmr_granule_id", ""),
                    acquisition_utc=sc.get("acquisition_utc", ""),
                    source_url=vv_asset.get("url", ""),
                    metadata_url=(
                        f"https://cmr.earthdata.nasa.gov/search/concepts/{sc['cmr_granule_id']}.umm_json"
                        if sc.get("cmr_granule_id")
                        else None
                    ),
                    sha256=f"VV:{vv_asset.get('sha256', '')[:16]}... VH:{vh_asset.get('sha256', '')[:16]}...",
                    track_frame_note=f"Burst {burst_id} ({pass_dir}, AbsOrbit {orbit_num}, S1 IPF v{s1_proc})",
                    processor_version=s1_proc,
                )
            )

        t0_utc = scenes_out[0].acquisition_utc if len(scenes_out) >= 1 else None
        t1_utc = scenes_out[1].acquisition_utc if len(scenes_out) >= 2 else None

        # Polarization stats
        pol_stats_out: dict[str, TwAgroPolarizationStats] = {}
        raw_pols = analysis.get("polarizations", {})
        for pol in ("VV", "VH"):
            rp = raw_pols.get(pol)
            if not rp:
                pol_stats_out[pol] = TwAgroPolarizationStats(polarization=pol, available=False)
                continue
            pol_stats_out[pol] = TwAgroPolarizationStats(
                polarization=pol,
                available=True,
                t0_db=_parse_dist(rp.get("t0_db")),
                t1_db=_parse_dist(rp.get("t1_db")),
                delta_db=_parse_dist(rp.get("delta_db")),
                magnitude_db=None,
                positive_change_fraction=None,
                negative_change_fraction=None,
            )

        # Layers
        layers_out: dict[str, TwAgroLayerOverlay] = {}
        asset_sha = manifest.get("asset_sha256", {})
        union_bbox: list[float] | None = None

        for lyr in raw_layers:
            pol = lyr["polarization"]
            lid = f"delta_{pol.lower()}"
            ov = lyr["overlay"]
            href = ov["href"]
            corners = ov["coordinates_lon_lat"]
            bbox = _bbox_from_corners(corners)
            union_bbox = bbox if union_bbox is None else [
                min(union_bbox[0], bbox[0]),
                min(union_bbox[1], bbox[1]),
                max(union_bbox[2], bbox[2]),
                max(union_bbox[3], bbox[3]),
            ]
            rmin, rmax = [float(x) for x in ov.get("render_range_db", [-6.0, 6.0])]
            stops = [
                TwAgroLegendStop(value=rmin, color="#082f87", label=f"{rmin:+.0f} dB (Negative radar change)"),
                TwAgroLegendStop(value=rmin / 2, color="#388ee6", label=f"{rmin / 2:+.0f} dB (Decrease)"),
                TwAgroLegendStop(value=0.0, color="#f1f5f9", label="0 dB (Neutral)"),
                TwAgroLegendStop(value=rmax / 2, color="#f59e0b", label=f"+{rmax / 2:.0f} dB (Increase)"),
                TwAgroLegendStop(value=rmax, color="#b43403", label=f"+{rmax:.0f} dB (Positive radar change)"),
            ]
            layers_out[lid] = TwAgroLayerOverlay(
                layer_id=lid,
                polarization=pol,
                title=f"Signed Δ{pol} (T1 − T0, OPERA RTC dB)",
                units=lyr.get("unit", "dB"),
                overlay_url=f"/api/tw-agro/assets/tw01/{href}",
                geotiff_filename=lyr.get("href"),
                render_range_db=[rmin, rmax],
                coordinates_lon_lat=corners,
                bbox_wgs84=bbox,
                legend_stops=stops,
                positive_change_meaning=f"Positive radar change (Δ{pol} > 0 dB): Backscatter increased between 10/14 and 10/26.",
                negative_change_meaning=f"Negative radar change (Δ{pol} < 0 dB): Backscatter decreased between 10/14 and 10/26.",
                prohibited_labels_notice=(
                    "Cross-event C-band radar change only — never labeled as verified typhoon crop damage."
                ),
                overlay_sha256=asset_sha.get(href),
            )

        common_valid_px = int(analysis.get("common_valid_pixel_count", 0))
        aoi_px = int(analysis.get("aoi_pixel_count", common_valid_px))
        cov_frac = float(analysis.get("common_coverage_fraction", 1.0))
        valid_area_m2 = common_valid_px * spacing[0] * spacing[1]
        valid_area_km2 = round(valid_area_m2 / 1_000_000.0, 4)
        valid_area_ha = round(valid_area_m2 / 10_000.0, 2)

        radiometry = analysis.get("radiometry", {})

        pkg = TwAgroSensorPackage(
            package_id="s1_tw01",
            schema_version=str(manifest.get("schema_version", "taiwan-agricultural-demo/1.0")),
            status=status,
            available=True,
            missing_assets=[],
            failure_reason=None,
            evidence_id=evidence_id,
            sensor_name=f"{manifest.get('sensor', 'Sentinel-1D')} C-band",
            band_name="C-band (~5.6 cm, VV / VH)",
            product_type=f"{manifest.get('product', 'OPERA_L2_RTC-S1_V1')} (30 m)",
            algorithm_version=manifest.get("algorithm_version"),
            observation_role_badge="跨事件觀測 (Cross-Event Observation)",
            observation_window_note=(
                "T0 = 2026-10-14 UTC → T1 = 2026-10-26 UTC 跨越颱風時窗；"
                "雷達變化不代表一定由颱風造成，亦可能源自農作收穫、整地、灌溉、作物生長或土壤含水差異。"
            ),
            crs_epsg=crs_epsg,
            pixel_spacing_m=spacing,
            grid_shape=grid_shape,
            t0_acquisition_utc=t0_utc,
            t1_acquisition_utc=t1_utc,
            polarizations=list(manifest.get("polarizations", ["VV", "VH"])),
            valid_pixel_count=common_valid_px,
            total_reference_pixel_count=aoi_px,
            coverage_ratio=cov_frac,
            aoi_coverage_ratio=cov_frac,
            valid_area_km2=valid_area_km2,
            valid_area_ha=valid_area_ha,
            scenes=scenes_out,
            polarization_stats=pol_stats_out,
            layers=layers_out,
            limitations=list(manifest.get("limitations", [])),
            not_supported_claims=[
                "跨事件變化不代表一定由颱風造成（cause_not_determined）",
                "181 筆待查農田候選僅供實地優先勘查排序，並非已確認農損或災損模型",
                "未建立獨立穩定參考區（stable_reference_test: Not independently established）",
                "不得與 NISAR L-band 直接相減",
            ],
            processing_notes=[
                "OPERA L2 RTC-S1（同一 burst T069-146197-IW1，EPSG:32651，30 m 格網完全對齊）",
                f"遮罩規則：兩期 mask 均為 class 0 且線性 gamma0 > 0（共同有效像元 {common_valid_px:,} / AOI {aoi_px:,}，覆蓋率 {cov_frac * 100:.1f}%）",
                f"輻射比較說明：{radiometry.get('comparison', '')} Offset correction applied: {radiometry.get('offset_correction_applied')}",
            ],
            mask_rule="T0 mask == 0 and T1 mask == 0 and linear backscatter > 0 (both VV & VH)",
            asset_sha256={k: str(v) for k, v in asset_sha.items()},
        )

        # Build joined 181 candidate parcels list from manifest + candidate-parcels.geojson
        aoi_geojson = _read_json_safe(self.tw01_dir / aoi_href)
        aoi_clip_bbox: list[float] | None = None
        if aoi_geojson and isinstance(aoi_geojson.get("geometry"), dict):
            _, aoi_clip_bbox = _compute_geom_centroid_and_bbox(aoi_geojson["geometry"])

        candidates_geojson = _read_json_safe(self.tw01_dir / candidates_href)
        geom_lookup: dict[int, dict[str, Any]] = {}
        if candidates_geojson and isinstance(candidates_geojson.get("features"), list):
            for feat in candidates_geojson["features"]:
                props = feat.get("properties", {})
                fid = props.get("parcel_feature_id")
                if fid is not None:
                    geom_lookup[int(fid)] = feat

        joined_candidates: list[TwAgroCandidateParcel] = []
        for item in parcel_screening.get("candidates", []):
            fid = int(item["parcel_feature_id"])
            feat = geom_lookup.get(fid, {})
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            centroid, pbbox = _compute_geom_centroid_and_bbox(geom)
            touches_edge = _geometry_touches_bbox(geom, aoi_clip_bbox)
            deltas = item.get("median_delta_db", {})
            vv_val = float(deltas["VV"])
            vh_val = float(deltas["VH"])
            dominant: Literal["VV", "VH"] = "VV" if abs(vv_val) >= abs(vh_val) else "VH"
            area_m2 = float(props.get("clipped_area_m2", 0.0))
            joined_candidates.append(
                TwAgroCandidateParcel(
                    parcel_feature_id=fid,
                    parcel_no=str(props.get("PARCEL_NO", f"FEATURE-{fid}")),
                    clipped_area_m2=area_m2,
                    clipped_area_ha=round(area_m2 / 10_000.0, 8),
                    touches_aoi_boundary=touches_edge,
                    valid_pixel_count=int(item["valid_pixel_count"]),
                    coverage_fraction=float(item["coverage_fraction"]),
                    median_delta_vv_db=vv_val,
                    median_delta_vh_db=vh_val,
                    max_abs_median_delta_db=round(max(abs(vv_val), abs(vh_val)), 4),
                    dominant_channel=dominant,
                    centroid_lon_lat=centroid,
                    bbox_wgs84=pbbox,
                )
            )

        # Sort descending by strongest absolute radar shift so top inspection priorities appear first
        joined_candidates.sort(key=lambda c: c.max_abs_median_delta_db, reverse=True)

        total_farmland = (
            int(farmland_info["parcel_count"])
            if farmland_info.get("parcel_count") is not None
            else None
        )
        candidate_areas = analysis.get("candidate_areas", {})

        screening_summary = TwAgroParcelScreeningSummary(
            available=True,
            missing_assets=[],
            failure_reason=None,
            total_farmland_parcels=total_farmland,
            eligible_parcels=int(parcel_screening.get("eligible_parcels", 0)),
            candidate_count=int(parcel_screening.get("candidate_count", len(joined_candidates))),
            criteria=parcel_screening.get("criteria"),
            candidate_pixel_count=(
                int(candidate_areas["candidate_pixel_count"])
                if candidate_areas.get("candidate_pixel_count") is not None
                else None
            ),
            candidate_pixel_criteria=candidate_areas.get("criteria"),
            mandatory_non_damage_notice=(
                f"以下 {len(joined_candidates)} 筆（自 {parcel_screening.get('eligible_parcels')} 筆合格坵塊 / "
                f"{total_farmland:,} 筆雲林農田坵塊篩選）僅為 |median Δ| ≥ 3 dB 之「待查農田候選」，"
                "並非已確認農損、災損模型或救助核定依據。"
            ),
            candidates=joined_candidates,
        )

        farmland_preview_url = (
            f"/api/tw-agro/assets/tw01/{farmland_preview}"
            if farmland_preview and (self.tw01_dir / farmland_preview).is_file()
            else None
        )

        return pkg, screening_summary, relief_info, total_farmland, farmland_preview_url, union_bbox

    def _compute_geojson_total_area_ha(self, path: pathlib.Path) -> float | None:
        data = _read_json_safe(path)
        if not data or not isinstance(data.get("features"), list):
            return None
        total_m2 = sum(
            float(feat.get("properties", {}).get("clipped_area_m2", 0.0) or 0.0)
            for feat in data["features"]
        )
        return round(total_m2 / 10_000.0, 4)

    def _build_unavailable_s2(
        self,
        status: str,
        missing_assets: list[str],
        failure_reason: str,
    ) -> TwAgroSentinel2Package:
        return TwAgroSentinel2Package(
            package_id="s2_tw08",
            available=False,
            status=status,
            schema_version=None,
            failure_reason=failure_reason,
            missing_assets=missing_assets,
            title="TW-08A Sentinel-2 L2A 多光譜輔助檢視（未載入）",
            role_notice="輔助多光譜檢視（非主要偵測，亦不參與 TW-07 救助核定）",
            boa_offset_verified=False,
            grid_alignment_note="10 m (NDVI) 與 20 m (NDRE/LSWI/SCL) 維持原生網格",
            scl_semantics_note="SCL={4,5,6} 為晴空可觀測地物（含植被、裸土與水體），非單指健康植被。",
            ground_truth_labels_available=False,
            classifier_trained=False,
        )

    def _row_to_parcel_optical(
        self,
        row: dict[str, str],
        scenes_by_date: dict[str, dict[str, Any]],
    ) -> TwAgroParcelOpticalMetrics:
        fid = int(row["parcel_feature_id"])
        dates_order = ["2026-10-11", "2026-10-16", "2026-10-26", "2026-11-05"]
        epochs: list[TwAgroParcelOpticalEpoch] = []
        valid_10m_map: dict[str, bool] = {}

        for d in dates_order:
            ymd = d.replace("-", "")
            smeta = scenes_by_date.get(d, {})
            is_v10 = row.get(f"is_valid_10m_{ymd}") == "True"
            valid_10m_map[d] = is_v10
            epochs.append(
                TwAgroParcelOpticalEpoch(
                    date_utc=d,
                    stac_id=smeta.get("stac_id"),
                    usability_status=str(smeta.get("usability_status", "CLOUD_OBSCURED_UNUSABLE")),
                    valid_px_10m=int(row.get(f"valid_px_10m_{ymd}") or 0),
                    total_px_10m=int(row.get("total_pixels_10m") or 0),
                    cov_10m=float(row.get(f"cov_10m_{ymd}") or 0.0),
                    is_valid_10m=is_v10,
                    ndvi_med=_float_or_none(row.get(f"ndvi_med_{ymd}")),
                    ndvi_iqr=_float_or_none(row.get(f"ndvi_iqr_{ymd}")),
                    valid_px_20m=int(row.get(f"valid_px_20m_{ymd}") or 0),
                    total_px_20m=int(row.get("total_pixels_20m") or 0),
                    cov_20m=float(row.get(f"cov_20m_{ymd}") or 0.0),
                    is_valid_20m=row.get(f"is_valid_20m_{ymd}") == "True",
                    ndre_med=_float_or_none(row.get(f"ndre_med_{ymd}")),
                    lswi_med=_float_or_none(row.get(f"lswi_med_{ymd}")),
                )
            )

        v_1011 = valid_10m_map.get("2026-10-11", False)
        v_1105 = valid_10m_map.get("2026-11-05", False)
        usable_clear_dates = [d for d in ("2026-10-11", "2026-11-05") if valid_10m_map.get(d, False)]

        if v_1011 and v_1105:
            gate_status: Literal["SUFFICIENT_CLEAR_BOTH", "INSUFFICIENT_OPTICAL_EVIDENCE"] = "SUFFICIENT_CLEAR_BOTH"
            gate_label = "雙期有效晴空觀測（2026-10-11 與 2026-11-05 均達 10 m ≥ 80% 覆蓋率且 ≥ 5 像元）"
            reason = None
        else:
            gate_status = "INSUFFICIENT_OPTICAL_EVIDENCE"
            gate_label = "INSUFFICIENT OPTICAL EVIDENCE"
            if not v_1011 and not v_1105:
                reason = (
                    "2026-10-11 與 2026-11-05 皆未達 10 m 有效晴空門檻（需 ≥ 80% 覆蓋率且 ≥ 5 像元）；"
                    "依規範禁止合成補植，標註為 INSUFFICIENT OPTICAL EVIDENCE。"
                )
            elif not v_1105:
                reason = (
                    "2026-11-05 受雲／雲影影響，未達 10 m 有效晴空門檻（需 ≥ 80% 覆蓋率且 ≥ 5 像元）；"
                    "依規範禁止合成補植，標註為 INSUFFICIENT OPTICAL EVIDENCE。"
                )
            else:
                reason = (
                    "2026-10-11 未達 10 m 有效晴空門檻（需 ≥ 80% 覆蓋率且 ≥ 5 像元）；"
                    "依規範禁止合成補植，標註為 INSUFFICIENT OPTICAL EVIDENCE。"
                )

        return TwAgroParcelOpticalMetrics(
            parcel_feature_id=fid,
            parcel_no=str(row.get("parcel_no") or f"FEATURE-{fid}"),
            clipped_area_m2=float(row.get("clipped_area_m2") or 0.0),
            clipped_area_ha=float(row.get("clipped_area_ha") or 0.0),
            is_tw01_sar_candidate_181=row.get("is_tw01_sar_candidate_181") == "True",
            quality_gate_status=gate_status,
            quality_gate_label=gate_label,
            insufficient_reason=reason,
            usable_clear_dates=usable_clear_dates,
            all_touched_fallback_10m=row.get("all_touched_fallback_10m") == "True",
            all_touched_fallback_20m=row.get("all_touched_fallback_20m") == "True",
            epochs=epochs,
            delta_ndvi_20261011_20261105=_float_or_none(row.get("delta_ndvi_20261011_20261105")),
            delta_ndre_20261011_20261105=_float_or_none(row.get("delta_ndre_20261011_20261105")),
            delta_lswi_20261011_20261105=_float_or_none(row.get("delta_lswi_20261011_20261105")),
            crop_type_label="UNKNOWN",
            actual_damage_rate="UNKNOWN",
            scientific_note=(
                "僅供多光譜輔助檢視；MOA 地籍資料無 2026 年逐坵塊作物別與現地災損標註，"
                "crop_type_label 與 actual_damage_rate 維持 UNKNOWN，且不輸入 TW-07 現金救助計算。"
            ),
        )

    def _load_s2_tw08(self) -> tuple[TwAgroSentinel2Package, dict[int, TwAgroParcelOpticalMetrics]]:
        manifest_path = self.tw08_dir / "manifest.json"
        manifest = _read_json_safe(manifest_path)
        if manifest is None:
            return (
                self._build_unavailable_s2(
                    status="unavailable",
                    missing_assets=["tw08/sentinel2-demo-v1/manifest.json"],
                    failure_reason="未載入 TW-08A Sentinel-2 manifest.json，輔助多光譜模組顯示為無法使用。",
                ),
                {},
            )

        csv_rel = manifest.get("csv_outputs", {}).get("farmland_4863", "farmland_4863_multitemporal_metrics.csv")
        csv_path = self.tw08_dir / csv_rel
        if not csv_path.is_file():
            return (
                self._build_unavailable_s2(
                    status="unavailable",
                    missing_assets=[csv_rel],
                    failure_reason=f"缺少 TW-08A 逐坵塊光譜 CSV：{csv_rel}",
                ),
                {},
            )

        raw_scenes = manifest.get("scenes", [])
        scenes_by_date: dict[str, dict[str, Any]] = {str(sc.get("date_utc")): sc for sc in raw_scenes}

        scenes_out: list[TwAgroSentinel2SceneSummary] = []
        for sc in raw_scenes:
            outputs = sc.get("outputs", {})
            ndvi_ov = outputs.get("ndvi_overlay", {})
            ov_href = ndvi_ov.get("href")
            ov_coords = ndvi_ov.get("coordinates_lon_lat")
            ov_url = f"/api/tw-agro/assets/tw08/{ov_href}" if ov_href and (self.tw08_dir / ov_href).is_file() else None
            scl_fracs = sc.get("scl_fractions_20m", {})
            scenes_out.append(
                TwAgroSentinel2SceneSummary(
                    date_utc=str(sc["date_utc"]),
                    acquisition_utc=str(sc.get("acquisition_utc", "")),
                    stac_id=str(sc["stac_id"]),
                    platform=str(sc.get("platform", "")),
                    tile_cloud_cover_percent=float(sc.get("tile_cloud_cover_percent", 0.0)),
                    aoi_valid_fraction_10m=float(sc.get("aoi_valid_fraction_10m", 0.0)),
                    aoi_valid_fraction_20m=float(sc.get("aoi_valid_fraction_20m", 0.0)),
                    aoi_cloud_shadow_fraction_20m=float(sc.get("aoi_cloud_shadow_fraction_20m", 0.0)),
                    usability_status=str(sc.get("usability_status", "CLOUD_OBSCURED_UNUSABLE")),
                    scl4_vegetation_fraction_20m=float(scl_fracs.get("4_vegetation", 0.0)),
                    scl5_not_vegetated_fraction_20m=float(scl_fracs.get("5_not_vegetated", 0.0)),
                    scl6_water_fraction_20m=float(scl_fracs.get("6_water", 0.0)),
                    aoi_ndvi_median_10m=sc.get("aoi_ndvi_stats_10m", {}).get("median"),
                    aoi_ndre_median_20m=sc.get("aoi_ndre_stats_20m", {}).get("median"),
                    aoi_lswi_median_20m=sc.get("aoi_lswi_stats_20m", {}).get("median"),
                    overlay_url=ov_url,
                    overlay_coordinates_lon_lat=ov_coords if ov_url else None,
                )
            )

        clear_delta_out: TwAgroSentinel2ClearDelta | None = None
        deltas = manifest.get("temporal_index_deltas", [])
        if deltas:
            d0 = deltas[0]
            dov = d0.get("outputs", {}).get("delta_ndvi_overlay", {})
            dhref = dov.get("href")
            if dhref and (self.tw08_dir / dhref).is_file():
                clear_delta_out = TwAgroSentinel2ClearDelta(
                    t0_date=str(d0["t0_date"]),
                    t1_date=str(d0["t1_date"]),
                    common_valid_fraction_10m=float(d0.get("common_valid_fraction_10m", 0.0)),
                    common_valid_fraction_20m=float(d0.get("common_valid_fraction_20m", 0.0)),
                    delta_ndvi_median=d0.get("delta_ndvi_stats", {}).get("median"),
                    delta_ndre_median=d0.get("delta_ndre_stats", {}).get("median"),
                    delta_lswi_median=d0.get("delta_lswi_stats", {}).get("median"),
                    overlay_url=f"/api/tw-agro/assets/tw08/{dhref}",
                    overlay_coordinates_lon_lat=dov["coordinates_lon_lat"],
                )

        optical_by_id: dict[int, TwAgroParcelOpticalMetrics] = {}
        farmland_suff = 0
        cand_total = 0
        cand_suff = 0
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                metrics = self._row_to_parcel_optical(row, scenes_by_date)
                optical_by_id[metrics.parcel_feature_id] = metrics
                if metrics.quality_gate_status == "SUFFICIENT_CLEAR_BOTH":
                    farmland_suff += 1
                if metrics.is_tw01_sar_candidate_181:
                    cand_total += 1
                    if metrics.quality_gate_status == "SUFFICIENT_CLEAR_BOTH":
                        cand_suff += 1

        pa = manifest.get("parcel_analysis", {})
        pa_counts = pa.get("counts", {})
        corr_ndvi = pa.get("sar_optical_correlations_within_181", {}).get("delta_ndvi_20261011_20261105", {})
        vh_corr = corr_ndvi.get("spearman_vh_vs_opt", {})
        fig_urls: dict[str, str] = {}
        for fn in manifest.get("diagnostic_figures", []):
            if fn in ALLOWED_TW08_ASSETS and (self.tw08_dir / fn).is_file():
                fig_urls[fn] = f"/api/tw-agro/assets/tw08/{fn}"

        rad = manifest.get("radiometry_and_cloud_masking", {})
        gt_audit = manifest.get("ground_truth_and_classification_audit", {})

        pkg = TwAgroSentinel2Package(
            package_id="s2_tw08",
            available=True,
            status=str(manifest.get("status", "real_multispectral_observation_qa")),
            schema_version=manifest.get("schema_version"),
            failure_reason=None,
            missing_assets=[],
            title="Sentinel-2 L2A 多光譜時序輔助檢視（TW-08A NDVI 10 m / NDRE & LSWI 20 m）",
            role_notice=(
                "輔助多光譜檢視（與 NISAR／Sentinel-1D 核心 SAR 分開呈現）；僅記錄實際晴空觀測，不得推論作物別或颱風農損，亦不進入 TW-07 現金救助計算。"
            ),
            boa_offset_verified=bool(rad.get("earthsearch_boa_offset_applied_verified", False)),
            grid_alignment_note="10 m (NDVI: B04/B08) 與 20 m (NDRE/LSWI/SCL: B05/B8A/B11) 嚴格保留各自原生空間解析度（EPSG:32651 原點誤差 0.0 m）。",
            scl_semantics_note=(
                "SCL={4,5,6} 代表未受雲遮蔽之晴空地表（4=植被、5=裸土／非植被、6=水體），絕非「全部皆為健康植被」；"
                "品質未達雙期 ≥ 80% 且 ≥ 5 像元者一律顯示 INSUFFICIENT OPTICAL EVIDENCE。"
            ),
            ground_truth_labels_available=bool(gt_audit.get("ground_truth_labels_available", False)),
            classifier_trained=bool(gt_audit.get("classifier_trained", False)),
            usable_clear_dates=list(pa_counts.get("usable_clear_dates", ["2026-10-11", "2026-11-05"])),
            total_farmland_parcels=len(optical_by_id),
            farmland_sufficient_count=farmland_suff,
            farmland_insufficient_count=len(optical_by_id) - farmland_suff,
            candidate_181_count=cand_total,
            candidate_sufficient_count=cand_suff,
            candidate_insufficient_count=cand_total - cand_suff,
            sar_vh_delta_ndvi_spearman_rho=vh_corr.get("rho"),
            sar_vh_delta_ndvi_spearman_p=vh_corr.get("pvalue"),
            scenes=scenes_out,
            clear_delta=clear_delta_out,
            diagnostic_figure_urls=fig_urls,
            scientific_limitations=list(manifest.get("scientific_limitations", [])),
        )
        return pkg, optical_by_id

    def get_parcel_optical_metrics(self, parcel_feature_id: int) -> TwAgroParcelOpticalMetrics:
        """Return verified Sentinel-2 L2A multi-temporal metrics for any of the 4,863 farmland parcels."""
        s2_pkg, optical_by_id = self._load_s2_tw08()
        if not s2_pkg.available:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "OPTICAL_EVIDENCE_UNAVAILABLE",
                    "message": s2_pkg.failure_reason or "TW-08A Sentinel-2 package is unavailable.",
                    "science_status": "INSUFFICIENT_OPTICAL_EVIDENCE",
                },
            )
        metrics = optical_by_id.get(parcel_feature_id)
        if metrics is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "PARCEL_OPTICAL_NOT_FOUND",
                    "message": f"Parcel feature ID `{parcel_feature_id}` was not found in TW-08A farmland optical metrics.",
                    "science_status": "INSUFFICIENT_OPTICAL_EVIDENCE",
                },
            )
        return metrics

    def get_relief_catalog(self) -> TwAgroReliefCatalog:
        """Load versioned statutory cash relief schedule and Yunlin disaster announcements."""
        sched_path = self.data_dir / "tw_relief_schedules_1150629.json"
        ann_path = self.data_dir / "tw_yunlin_announcements_11510.json"
        sched = _read_json_safe(sched_path)
        ann = _read_json_safe(ann_path)
        if sched is None or ann is None:
            raise HTTPException(
                status_code=500,
                detail={
                    "error_code": "RELIEF_CATALOG_MISSING",
                    "message": "Versioned statutory relief schedule or announcement JSON is missing.",
                },
            )

        farmland_ha = self._compute_geojson_total_area_ha(self.tw01_dir / "farmland.geojson")
        candidate_ha = self._compute_geojson_total_area_ha(self.tw01_dir / "candidate-parcels.geojson")

        return TwAgroReliefCatalog(
            schedule_version_id=str(sched["schedule_version_id"]),
            regulation_title=str(sched["regulation_title"]),
            regulation_amendment_date_roc=str(sched["regulation_amendment_date_roc"]),
            regulation_amendment_date_iso=str(sched["regulation_amendment_date_iso"]),
            statutory_basis_articles=list(sched["statutory_basis_articles"]),
            min_application_area_ha=float(sched.get("min_application_area_ha", 0.01)),
            min_application_area_rule=str(sched["min_application_area_rule"]),
            statutory_loss_threshold_fraction=float(sched["statutory_loss_threshold_fraction"]),
            statutory_loss_threshold_rule=str(sched["statutory_loss_threshold_rule"]),
            official_law_url=str(sched["official_law_url"]),
            official_afa_schedule_url=str(sched["official_afa_schedule_url"]),
            as_of_date_iso=str(ann["as_of_date_iso"]),
            primary_deadline_expired_warning=str(ann["primary_deadline_expired_warning"]),
            statutory_exception_notice=str(ann["statutory_exception_notice"]),
            farmland_total_area_ha=farmland_ha,
            candidate_total_area_ha=candidate_ha,
            announcements=[TwAgroDisasterAnnouncement(**a) for a in ann["announcements"]],
            items=[TwAgroReliefScheduleItem(**i) for i in sched["items"]],
            framework_separation=[TwAgroFrameworkSeparationItem(**f) for f in ann["framework_separation"]],
        )

    def _lookup_parcel_for_estimator(
        self,
        parcel_feature_id: int | None,
    ) -> tuple[dict[str, Any] | None, TwAgroCandidateParcel | None]:
        """Resolve optional cadastral parcel info (m2 / ha) and candidate SAR delta if available."""
        if parcel_feature_id is None:
            return None, None

        _, screening, _, _, _, _ = self._load_s1_tw01()
        candidate_match = next(
            (c for c in screening.candidates if c.parcel_feature_id == parcel_feature_id),
            None,
        )
        if candidate_match is not None:
            return (
                {
                    "parcel_feature_id": candidate_match.parcel_feature_id,
                    "parcel_no": candidate_match.parcel_no,
                    "clipped_area_m2": candidate_match.clipped_area_m2,
                    "clipped_area_ha": candidate_match.clipped_area_ha,
                    "touches_aoi_boundary": candidate_match.touches_aoi_boundary,
                    "source": "tw01/candidate-parcels.geojson (AOI 內裁切，MOA I75 RID=44143)",
                },
                candidate_match,
            )

        aoi_geojson = _read_json_safe(self.tw01_dir / "aoi.geojson")
        aoi_clip_bbox: list[float] | None = None
        if aoi_geojson and isinstance(aoi_geojson.get("geometry"), dict):
            _, aoi_clip_bbox = _compute_geom_centroid_and_bbox(aoi_geojson["geometry"])

        farmland_data = _read_json_safe(self.tw01_dir / "farmland.geojson")
        if farmland_data and isinstance(farmland_data.get("features"), list):
            for feat in farmland_data["features"]:
                props = feat.get("properties", {})
                if props.get("parcel_feature_id") == parcel_feature_id:
                    area_m2 = float(props.get("clipped_area_m2", 0.0) or 0.0)
                    geom = feat.get("geometry", {})
                    return (
                        {
                            "parcel_feature_id": parcel_feature_id,
                            "parcel_no": str(props.get("PARCEL_NO", f"FEATURE-{parcel_feature_id}")),
                            "clipped_area_m2": area_m2,
                            "clipped_area_ha": round(area_m2 / 10_000.0, 8),
                            "touches_aoi_boundary": _geometry_touches_bbox(geom, aoi_clip_bbox),
                            "source": "tw01/farmland.geojson (AOI 內裁切，MOA I75 RID=44143)",
                        },
                        None,
                    )

        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "PARCEL_NOT_FOUND",
                "message": f"Parcel feature ID `{parcel_feature_id}` was not found in Yunlin farmland GeoJSON.",
            },
        )

    def compute_relief_estimate(
        self,
        req: TwAgroReliefEstimateRequest,
    ) -> TwAgroReliefEstimateResponse:
        """Compute Phase 1 conditional statutory relief reference amount with strict epistemic separation."""
        catalog = self.get_relief_catalog()
        parcel_record, candidate_match = self._lookup_parcel_for_estimator(req.parcel_feature_id)

        item = next((i for i in catalog.items if i.item_id == req.crop_item_id), None)
        if item is None:
            item = next((i for i in catalog.items if i.item_id == "unknown_crop"), catalog.items[0])

        ann_doc = next(
            (a for a in catalog.announcements if a.doc_id == item.announcement_doc_id),
            catalog.announcements[0],
        )

        confirmed_facts: dict[str, Any] = {
            "regulation_version": f"{catalog.regulation_title}（{catalog.regulation_amendment_date_roc}版本 • 第5/6/12/12-1條）",
            "schedule_version_id": catalog.schedule_version_id,
            "statutory_item_name": item.display_name,
            "statutory_category": item.statutory_category,
            "statutory_rate_twd_per_ha": item.rate_twd_per_ha,
            "statutory_conditions": item.statutory_conditions,
            "announced_in_yunlin_11510": item.announced_in_yunlin_11510,
            "announcement_doc_number": ann_doc.doc_number if item.announcement_doc_id else "非本次 1151112527F／1151112552B 公告品項",
            "announcement_window_roc": (
                f"{ann_doc.application_start_roc} ～ {ann_doc.application_end_roc}（已截止）"
                if item.announcement_doc_id
                else None
            ),
            "parcel_feature_id": parcel_record["parcel_feature_id"] if parcel_record else None,
            "parcel_no": parcel_record["parcel_no"] if parcel_record else None,
            "parcel_clipped_area_m2": parcel_record["clipped_area_m2"] if parcel_record else None,
            "parcel_clipped_area_ha": parcel_record["clipped_area_ha"] if parcel_record else None,
            "parcel_area_nature": (
                "AOI 內裁切面積（非完整地籍面積、非實際種植面積、非公所核認救助面積）"
                if parcel_record
                else None
            ),
            "parcel_full_cadastral_area_ha": "UNKNOWN",
            "parcel_application_land_area_ha": "UNKNOWN",
            "parcel_min_001ha_eligibility_from_aoi_clip": (
                "UNKNOWN（0.01公頃門檻必須以申請土地面積判斷，不能直接使用 AOI clipped_area_ha 作為資格認定）"
            ),
            "parcel_touches_aoi_boundary": parcel_record["touches_aoi_boundary"] if parcel_record else None,
            "parcel_area_source": parcel_record["source"] if parcel_record else None,
            "min_application_area_ha": catalog.min_application_area_ha,
            "article_12_official_announcement_applicability": (
                "UNCONFIRMED_IN_LOCAL_PACKAGE（農業部 1151112527F／1151112552B 公告僅明載雲林晚種落花生免重複申請合併審理；"
                "是否另依第12條第1項第3款公告災損天氣參數或災損嚴重簡化程序，須以農業部正式公告為準）"
            ),
            "article_12_competent_authority_determination": (
                "UNCONFIRMED（須由鄉鎮市區公所與主管機關審查客觀種植證明文件或辦理 20% 以上抽樣勘查認定，"
                "不能單靠勾選或選單設定就判定符合資格）"
            ),
            "eligibility_determination_status": "NOT_DETERMINED（不能單靠勾選或選擇即判定符合救助資格）",
        }

        threshold_labels = {
            "unverified": "尚未設定／未確認現勘或第12條簡化程序資格",
            "below_20_percent": "假設為一般勘查案件且損失率未達 20%（依第12-1條第1項第3款本文，不予救助）",
            "meets_20_percent": "假設一般勘查確認損失率達 20% 以上法定門檻（第12條第1項第2款、第12-1條第1項第3款）",
            "article_12_simplified_exception": "使用者情境假設第12條第1項第3款簡化程序（僅模擬試算假設；官方公告適用與主管機關認定均未確認，不能單靠勾選判定符合資格）",
        }
        user_assumptions: dict[str, Any] = {
            "assumed_crop_item_id": req.crop_item_id,
            "assumed_crop_label": item.display_name,
            "assumed_approved_area_ha": req.assumed_approved_area_ha,
            "assumed_loss_threshold": req.assumed_loss_threshold,
            "assumed_loss_threshold_label": threshold_labels[req.assumed_loss_threshold],
            "article_12_user_scenario_assumption": (
                "使用者情境假設（僅模擬假設適用第12條第1項第3款簡化程序，非官方公告適用確認或主管機關資格認定）"
                if req.assumed_loss_threshold == "article_12_simplified_exception"
                else "未啟用第12條簡化程序情境假設"
            ),
            "allow_cross_aoi_boundary_area": req.allow_cross_aoi_boundary_area,
            "adjacent_land_merged_meets_001ha": req.adjacent_land_merged_meets_001ha,
        }

        if candidate_match is not None:
            satellite_observations: dict[str, Any] = {
                "sensor": "Sentinel-1D C-band OPERA L2 RTC-S1 (2026-10-14 -> 2026-10-26 cross-event)",
                "parcel_screening_status": "待查農田候選（|median Δ| ≥ 3 dB 勘查排序，非已確認農損）",
                "median_delta_vv_db": candidate_match.median_delta_vv_db,
                "median_delta_vh_db": candidate_match.median_delta_vh_db,
                "max_abs_median_delta_db": candidate_match.max_abs_median_delta_db,
                "valid_pixel_count": candidate_match.valid_pixel_count,
                "coverage_fraction": candidate_match.coverage_fraction,
                "sar_db_prohibition": "SAR 背向散射變化（dB）僅供勘查優先排序，嚴禁換算為作物受損率（%）或判定作物別。",
            }
        elif parcel_record is not None:
            satellite_observations = {
                "sensor": "Sentinel-1D C-band OPERA L2 RTC-S1 (2026-10-14 -> 2026-10-26 cross-event)",
                "parcel_screening_status": "未列入 |median Δ| ≥ 3 dB 待查農田候選清單（或像元不足）",
                "median_delta_vv_db": None,
                "median_delta_vh_db": None,
                "sar_db_prohibition": "SAR 背向散射變化（dB）不可換算為農損百分比（%）。",
            }
        else:
            satellite_observations = {
                "sensor": "Sentinel-1D C-band OPERA L2 RTC-S1 (2026-10-14 -> 2026-10-26 cross-event)",
                "parcel_screening_status": "未指定單一農田坵塊（僅做法定額度與條件試算）",
                "median_delta_vv_db": None,
                "median_delta_vh_db": None,
                "sar_db_prohibition": "SAR 背向散射變化（dB）不可換算為農損百分比（%）。",
            }

        unconfirmed_eligibility = [
            "田區實際種植作物種類或合法農業設施登記（依第12-1條不符者不予救助且有後續限制）",
            "第5條第1項及第2項資格：實際從事農業生產自然人、土地／水源／設施合法使用、農產業單筆或毗鄰合併面積≥0.01公頃、同產季／同曆年以救助一次為限",
            "雷達回波變化之真實成因（颱風／豪雨 vs 收割、翻耕、灌溉或季節物候轉換）",
            "是否符合第12-1條一般勘查損失率≥20%，或經中央主管機關公告適用第12條第1項第3款簡化程序（免勘查／抽樣勘查）例外",
            "法定受理期限已於 115/11/09 及 115/11/13 截止（雲林晚種落花生免重複申請合併審理例外仍須公所核實）",
        ]

        deadline_and_exception_notice = (
            f"{catalog.primary_deadline_expired_warning} {catalog.statutory_exception_notice}"
        )
        non_approval_disclaimer = (
            "本試算輸出僅代表「在特定作物類別、假設面積與法定條件皆假設成立下之額度參考試算」，"
            "絕非政府核定可領金額或實際撥款保證。"
        )
        framework_separation_notice = (
            "政府現金救助（本試算，依每公頃法定定額、第5條0.01公頃門檻及第12/12-1條規定）與「農業保險理賠」（依保單條款與投保方案）"
            "及「實際經濟產值損失估算」（依產量與市價）屬三種獨立制度，不得混為一談。"
        )

        def _blocked(
            status: Literal[
                "BLOCKED_UNKNOWN_CROP",
                "BLOCKED_UNANNOUNCED_OR_EXCLUDED_ITEM",
                "BLOCKED_UNVERIFIED_OR_BELOW_20_THRESHOLD",
                "BLOCKED_BELOW_MIN_AREA_001_HA",
                "BLOCKED_INVALID_AREA",
            ],
            label: str,
            reason: str,
        ) -> TwAgroReliefEstimateResponse:
            return TwAgroReliefEstimateResponse(
                calculation_allowed=False,
                result_status=status,
                result_label=label,
                blocked_reason=reason,
                conditional_reference_amount_twd=None,
                formula_display=None,
                confirmed_facts=confirmed_facts,
                user_assumptions=user_assumptions,
                satellite_observations=satellite_observations,
                unconfirmed_eligibility=unconfirmed_eligibility,
                deadline_and_exception_notice=deadline_and_exception_notice,
                non_approval_disclaimer=non_approval_disclaimer,
                framework_separation_notice=framework_separation_notice,
            )

        if item.item_id == "unknown_crop" or item.item_group == "unconfirmed":
            return _blocked(
                "BLOCKED_UNKNOWN_CROP",
                "不顯示試算金額（作物類別未知）",
                item.exclusion_reason or "尚未確認作物或設施類別，不得顯示救助試算金額。",
            )

        if not item.announced_in_yunlin_11510 or item.rate_twd_per_ha is None:
            return _blocked(
                "BLOCKED_UNANNOUNCED_OR_EXCLUDED_ITEM",
                "不顯示試算金額（未公告或明文排除品項）",
                item.exclusion_reason or "此品項未列入農業部 1151112527F 或 1151112552B 號雲林縣救助公告，不提供試算。",
            )

        area_ha = req.assumed_approved_area_ha
        if area_ha is None or area_ha <= 0:
            return _blocked(
                "BLOCKED_INVALID_AREA",
                "不顯示試算金額（面積未設定）",
                "請明確輸入或選取大於 0 公頃（ha）之假設核認面積，方可進行條件式參考試算。",
            )

        min_ha = catalog.min_application_area_ha
        if area_ha < min_ha and not req.adjacent_land_merged_meets_001ha:
            return _blocked(
                "BLOCKED_BELOW_MIN_AREA_001_HA",
                "依法不予救助（假設申請土地面積低於 0.01 公頃門檻）",
                (
                    f"依《農業天然災害救助辦法》第5條第2項第5款，0.01 公頃門檻必須以「申請土地面積」判斷"
                    f"（不能直接使用 AOI clipped_area_ha 作為資格認定；完整地籍與申請面積目前為 UNKNOWN）。"
                    f"目前使用者輸入之假設申請土地面積為 {_format_area_ha(area_ha)} ha（不足 {min_ha:.2f} 公頃），"
                    f"若非依第5條第4項與相毗鄰土地合併計算達 {min_ha:.2f} 公頃以上，此假設情境依法不予現金救助。"
                ),
            )

        if parcel_record is not None:
            parcel_ha = float(parcel_record["clipped_area_ha"])
            if parcel_ha > 0 and area_ha > parcel_ha + 1e-4:
                if not req.allow_cross_aoi_boundary_area:
                    return _blocked(
                        "BLOCKED_INVALID_AREA",
                        "不顯示試算金額（輸入面積超過 AOI 內裁切面積）",
                        (
                            f"假設面積（{_format_area_ha(area_ha)} ha）超過該地號之 AOI 內裁切面積"
                            f"（{_format_area_ha(parcel_ha)} ha；完整地籍面積為 UNKNOWN）。"
                            "若該筆跨出 5×5 km AOI 邊界或擬以實際地籍／申請面積試算，請勾選「允許跨 AOI 邊界／完整地籍假設面積」。"
                        ),
                    )
                if area_ha > 20.0:
                    return _blocked(
                        "BLOCKED_INVALID_AREA",
                        "不顯示試算金額（假設面積異常過大）",
                        "跨邊界假設單筆面積上限為 20.0000 公頃，請確認輸入單位為公頃（ha）。",
                    )

        if req.assumed_loss_threshold == "below_20_percent":
            return _blocked(
                "BLOCKED_UNVERIFIED_OR_BELOW_20_THRESHOLD",
                "依法不予救助（一般案件損失率未達 20%）",
                "依《農業天然災害救助辦法》第12條之1第1項第3款本文，一般勘查案件申報項目損失率未達 20% 者不予現金救助（NT$0）；惟經中央主管機關依第12條第1項第3款公告簡化程序（免勘查／抽樣勘查）者不在此限。",
            )

        if req.assumed_loss_threshold not in ("meets_20_percent", "article_12_simplified_exception"):
            return _blocked(
                "BLOCKED_UNVERIFIED_OR_BELOW_20_THRESHOLD",
                "不顯示試算金額（尚未設定適用條件）",
                "尚未設定適用條件（一般案件損失率 ≥ 20%，或第12條第1項第3款簡化程序情境假設），系統預設不輸出金額。",
            )

        # Statutory rate * unrounded assumed approved area (only round the final NTD integer)
        ref_amount_twd = int(round(item.rate_twd_per_ha * float(area_ha)))
        condition_tag = (
            "使用者情境假設第12條第1項第3款簡化程序；官方公告適用與主管機關認定均未確認，不能單靠勾選判定符合資格"
            if req.assumed_loss_threshold == "article_12_simplified_exception"
            else "一般勘查假設達 20% 門檻，20% 為資格門檻、未乘以損失百分比"
        )
        formula = (
            f"{item.rate_twd_per_ha:,} 元／公頃 × {_format_area_ha(area_ha)} 公頃 = NT${ref_amount_twd:,}"
            f"（{condition_tag}）"
        )

        return TwAgroReliefEstimateResponse(
            calculation_allowed=True,
            result_status="CONDITIONAL_REFERENCE_ESTIMATE",
            result_label="條件式試算參考金額（非核定可領金額）",
            blocked_reason=None,
            conditional_reference_amount_twd=ref_amount_twd,
            formula_display=formula,
            confirmed_facts=confirmed_facts,
            user_assumptions=user_assumptions,
            satellite_observations=satellite_observations,
            unconfirmed_eligibility=unconfirmed_eligibility,
            deadline_and_exception_notice=deadline_and_exception_notice,
            non_approval_disclaimer=non_approval_disclaimer,
            framework_separation_notice=framework_separation_notice,
        )

    def get_overview(self) -> TwAgroOverviewResponse:
        """Assemble the unified TW-05 Yunlin Agricultural Investigation response."""
        nisar_pkg, nisar_bbox = self._load_nisar_tw03()
        s1_pkg, screening, relief_info, total_farmland, preview_url, s1_bbox = self._load_s1_tw01()
        relief_catalog = self.get_relief_catalog()
        s2_pkg, optical_by_id = self._load_s2_tw08()

        if s2_pkg.available and screening.candidates:
            updated_candidates = [
                cand.model_copy(update={"optical_s2": optical_by_id.get(cand.parcel_feature_id)})
                for cand in screening.candidates
            ]
            screening = screening.model_copy(update={"candidates": updated_candidates})

        aoi_bbox = s1_bbox or nisar_bbox or [120.2745, 23.6865, 120.3256, 23.7335]

        return TwAgroOverviewResponse(
            workspace_id="TW-05-YUNLIN-AGRO",
            title="臺灣雲林農業地表變化調查介面（NISAR L-band × Sentinel-1D C-band）",
            region_name="雲林縣虎尾／土庫／元長農田調查示範區 (Yunlin 5 × 5 km AOI)",
            aoi_bbox_wgs84=aoi_bbox,
            geojson_urls={
                "aoi": "/api/tw-agro/geojson/aoi",
                "farmland": "/api/tw-agro/geojson/farmland",
                "candidate_parcels": "/api/tw-agro/geojson/candidate-parcels",
                "nisar_aoi": "/api/tw-agro/geojson/nisar-aoi",
            },
            farmland_preview_url=preview_url,
            farmland_total_parcel_count=total_farmland,
            nisar_tw03=nisar_pkg,
            s1_tw01=s1_pkg,
            parcel_screening_summary=screening,
            s2_tw08=s2_pkg if s2_pkg.available else None,
            relief_info=relief_info,
            relief_catalog=relief_catalog,
            scientific_guardrails=[
                "NISAR（2026-10-04 → 2026-10-16）屬於颱風前觀測，僅反映颱風前基線變化，不得寫成颱風災損。",
                "Sentinel-1D（2026-10-14 → 2026-10-26）屬於跨事件觀測，雷達背向散射變化不代表一定由颱風造成。",
                "NISAR L-band（HH/HV, 20 m）與 Sentinel-1D C-band（VV/VH, 30 m）屬不同波段與極化系統，兩種 SAR 資料不可直接相減。",
                "Sentinel-1D 所列 181 筆待查農田候選僅供勘查優先排序，並非已確認農損或產量損失證明。",
                "Sentinel-2 L2A 多光譜僅為輔助檢視，10/16 與 10/26 重度雲蔽不得內插補植，品質不足坵塊標示 INSUFFICIENT OPTICAL EVIDENCE，作物與損失率均維持 UNKNOWN。",
                "TW-07 現金救助試算僅為依《農業天然災害救助辦法》115/06/29 版本之條件式額度參考，嚴禁將 SAR dB 或光學指標換算為損失率或取代公所現勘核定。",
            ],
        )

    def get_geojson_bytes(self, layer_name: str) -> bytes:
        """Serve verified GeoJSON FeatureCollection / Feature files from disk."""
        mapping: dict[str, pathlib.Path] = {
            "aoi": self.tw01_dir / "aoi.geojson",
            "farmland": self.tw01_dir / "farmland.geojson",
            "candidate-parcels": self.tw01_dir / "candidate-parcels.geojson",
            "nisar-aoi": self.tw03_dir / "aoi.geojson",
        }
        target = mapping.get(layer_name)
        if target is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "GEOJSON_LAYER_NOT_FOUND",
                    "message": f"Unknown Taiwan Agro GeoJSON layer `{layer_name}`.",
                    "science_status": "INSUFFICIENT_EVIDENCE",
                },
            )
        if not target.is_file():
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "GEOJSON_ASSET_MISSING",
                    "message": f"GeoJSON asset `{target.name}` is missing on disk; no synthetic fallback is permitted.",
                    "science_status": "INSUFFICIENT_EVIDENCE",
                },
            )
        return target.read_bytes()

    def get_asset_png_bytes(self, package_id: str, filename: str) -> bytes:
        """Serve verified transparent PNG overlays with strict allowlist against path traversal."""
        if package_id == "tw01":
            if filename not in ALLOWED_TW01_ASSETS:
                raise HTTPException(status_code=404, detail=f"Asset `{filename}` is not allowlisted for tw01.")
            target = (self.tw01_dir / filename).resolve()
            if not str(target).startswith(str(self.tw01_dir.resolve())) or not target.is_file():
                raise HTTPException(status_code=404, detail=f"TW-01 PNG asset `{filename}` is missing on disk.")
            return target.read_bytes()

        if package_id == "tw03":
            if filename not in ALLOWED_TW03_ASSETS:
                raise HTTPException(status_code=404, detail=f"Asset `{filename}` is not allowlisted for tw03.")
            target = (self.tw03_dir / filename).resolve()
            if not str(target).startswith(str(self.tw03_dir.resolve())) or not target.is_file():
                raise HTTPException(status_code=404, detail=f"TW-03 PNG asset `{filename}` is missing on disk.")
            return target.read_bytes()

        if package_id == "tw08":
            if filename not in ALLOWED_TW08_ASSETS:
                raise HTTPException(status_code=404, detail=f"Asset `{filename}` is not allowlisted for tw08.")
            target = (self.tw08_dir / filename).resolve()
            if not str(target).startswith(str(self.tw08_dir.resolve())) or not target.is_file():
                raise HTTPException(status_code=404, detail=f"TW-08 PNG asset `{filename}` is missing on disk.")
            return target.read_bytes()

        raise HTTPException(status_code=404, detail=f"Unknown asset package `{package_id}`.")
