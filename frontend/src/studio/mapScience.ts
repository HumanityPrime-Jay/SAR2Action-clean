export const NASA_GIBS_BLUE_MARBLE = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_NextGeneration/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg';
export const NASA_GIBS_ATTRIBUTION = 'NASA Earth Observatory Blue Marble Next Generation · NASA EOSDIS GIBS';
export const NASA_GIBS_LANDSAT_WELD = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/Landsat_WELD_CorrectedReflectance_TrueColor_Global_Annual/default/2000-12-01/GoogleMapsCompatible_Level12/{z}/{y}/{x}.jpeg';
export const NASA_GIBS_WELD_ATTRIBUTION = 'NASA EOSDIS GIBS · USGS/NASA Landsat WELD annual true color, 2000 composite';

export interface NisarMapScene {
  period: 'PRE' | 'POST';
  scene_id: string;
  acquisition_start_utc: string;
  crid: string;
  product_maturity: 'PROVISIONAL' | 'VALIDATED';
  source_sha256: string;
  coordinates: [number, number][];
  layers: Record<'HH' | 'HV', { image: string; valid_pixels: number; display_stretch_db: [number, number] }>;
}

export interface NisarMapManifest {
  case_id: string;
  aoi_kind: string;
  status: 'SEPARATE_OBSERVATIONS_ONLY';
  cross_crid_radiometric_equivalence_verified: false;
  verified_typhoon_delta_allowed: false;
  display_method: string;
  scenes: NisarMapScene[];
}

export function parseNisarMapManifest(value: unknown): NisarMapManifest {
  if (!value || typeof value !== 'object') throw new Error('NISAR map manifest missing');
  const root = value as NisarMapManifest;
  if (root.status !== 'SEPARATE_OBSERVATIONS_ONLY' ||
      root.cross_crid_radiometric_equivalence_verified !== false ||
      root.verified_typhoon_delta_allowed !== false ||
      root.aoi_kind !== 'ADMINISTRATIVE_TOWNSHIP_NOT_FIELD' ||
      !Array.isArray(root.scenes) || root.scenes.length !== 2)
    throw new Error('NISAR map science gate failed');
  for (const [index, scene] of root.scenes.entries()) {
    if (scene.period !== (index === 0 ? 'PRE' : 'POST') ||
        scene.crid !== (index === 0 ? 'P05023' : 'P05036') ||
        scene.product_maturity !== (index === 0 ? 'PROVISIONAL' : 'VALIDATED') ||
        !/^NISAR_L2_PR_GCOV_/.test(scene.scene_id) ||
        !Number.isFinite(Date.parse(scene.acquisition_start_utc)) ||
        !/^[a-f0-9]{64}$/.test(scene.source_sha256) ||
        !Array.isArray(scene.coordinates) || scene.coordinates.length !== 4 ||
        !scene.coordinates.every(point => point.length === 2 && point[0] > 119 && point[0] < 122 && point[1] > 22 && point[1] < 25))
      throw new Error('NISAR map scene provenance invalid');
    for (const pol of ['HH', 'HV'] as const) {
      const layer = scene.layers?.[pol];
      if (!layer || layer.image !== `nisar_${scene.period.toLowerCase()}_${pol.toLowerCase()}_map.png` ||
          !Number.isInteger(layer.valid_pixels) || layer.valid_pixels <= 0 ||
          layer.display_stretch_db.length !== 2 || layer.display_stretch_db[0] >= layer.display_stretch_db[1])
        throw new Error('NISAR map layer QA invalid');
    }
  }
  if (root.scenes[0].source_sha256 === root.scenes[1].source_sha256)
    throw new Error('NISAR scenes cannot share the same source digest');
  return root;
}
