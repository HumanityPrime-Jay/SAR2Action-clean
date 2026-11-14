import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { buildEvidenceGraph, investigateLive, loadStudioAssets, makeDossier, referencedIds, runEvidenceChallenge } from './adapter';
import type { ChallengeKind } from './adapter';
import type { FieldComparison, GraphNode, StudioAssets, StudioInvestigation, StudioMode, TraceEvent, VhObservation } from './contracts';
import { FieldFindings } from './FieldFindings';
import { PolygonEditor } from './PolygonEditor';
import { NASA_GIBS_ATTRIBUTION, NASA_GIBS_BLUE_MARBLE, NASA_GIBS_LANDSAT_WELD, NASA_GIBS_WELD_ATTRIBUTION, parseNisarMapManifest } from './mapScience';
import type { NisarMapManifest } from './mapScience';
import './studio.css';

const questionForField = (fieldId: string, comparison?: FieldComparison) => {
  const field = comparison?.fields.find(item => item.field_id === fieldId);
  const change = field?.['2026_pre_to_warning_window']?.median_difference_db;
  return `Why did VH ${change != null && change >= 0 ? 'increase' : 'change'}${change != null && change >= 0 ? ` by ${change.toFixed(3)} dB` : ''} in field ${fieldId} during the typhoon warning period? Check real dates, 2025 observations, other fields, post-warning observations, NISAR limits, and alternative explanations.`;
};
const asText = (value: unknown) => value === null || value === undefined || value === '' ? 'unavailable' : String(value);
const asList = (value: unknown): string[] => Array.isArray(value) ? value.filter((x): x is string => typeof x === 'string') : [];
const asLines = (value: unknown): string[] => typeof value === 'string' ? [value] : asList(value);
const dateText = (value: unknown) => typeof value === 'string' && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString('en-GB', { timeZone: 'UTC', year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' }) + ' UTC' : 'unavailable';
const coordText = (value: number) => value.toFixed(5);

function geometryBounds(feature: StudioAssets['fields']['features'][number]): [number, number, number, number] {
  const points: number[][] = [];
  function walk(value: unknown) {
    if (!Array.isArray(value)) return;
    if (value.length >= 2 && typeof value[0] === 'number' && typeof value[1] === 'number') points.push(value as number[]);
    else value.forEach(walk);
  }
  walk(feature.geometry.coordinates);
  return [Math.min(...points.map(p => p[0])), Math.min(...points.map(p => p[1])),
          Math.max(...points.map(p => p[0])), Math.max(...points.map(p => p[1]))];
}

function FieldMap({ assets, selectedField, onSelect }: { assets: StudioAssets; selectedField: string; onSelect: (id: string) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const tourToken = useRef(0);
  const touring = useRef(false);
  const [mapReady, setMapReady] = useState(false);
  const drawing = useRef(false);
  const [manifest, setManifest] = useState<NisarMapManifest | null>(null);
  const [mapError, setMapError] = useState('');
  const [period, setPeriod] = useState<'PRE' | 'POST'>('PRE');
  const [polarization, setPolarization] = useState<'HH' | 'HV'>('HH');
  const [layerVisible, setLayerVisible] = useState(false);
  const [opacity, setOpacity] = useState(68);
  const [tourStage, setTourStage] = useState('Selected field');
  useEffect(() => {
    let active = true;
    fetch(`${import.meta.env.BASE_URL || '/'}studio/nisar_map_manifest.json`, { cache: 'no-store' })
      .then(response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
      .then(value => { if (active) setManifest(parseNisarMapManifest(value)); })
      .catch(error => { if (active) setMapError(`NISAR map layer unavailable: ${String(error)}`); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!container.current) return;
    try {
      const instance = new maplibregl.Map({
        container: container.current,
        attributionControl: false,
        style: { version: 8,
          sources: { 'nasa-blue-marble': { type: 'raster', tiles: [NASA_GIBS_BLUE_MARBLE], tileSize: 256, maxzoom: 8,
            attribution: NASA_GIBS_ATTRIBUTION },
            'nasa-landsat-weld': { type: 'raster', tiles: [NASA_GIBS_LANDSAT_WELD], tileSize: 256, maxzoom: 12,
              attribution: NASA_GIBS_WELD_ATTRIBUTION } },
          layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#0d1c27' } },
            { id: 'nasa-blue-marble', type: 'raster', source: 'nasa-blue-marble' },
            { id: 'nasa-landsat-weld', type: 'raster', source: 'nasa-landsat-weld', minzoom: 9 }] },
        center: [120.19, 23.70], zoom: 11,
      });
      map.current = instance;
      instance.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
      instance.on('load', () => {
        setMapReady(true);
        instance.addSource('fields', { type: 'geojson', data: assets.fields as any });
        instance.addLayer({ id: 'field-fill', type: 'fill', source: 'fields', paint: { 'fill-color': '#34d399', 'fill-opacity': 0.23 } });
        instance.addLayer({ id: 'field-outline', type: 'line', source: 'fields', paint: { 'line-color': '#72e1bd', 'line-width': 2 } });
        instance.addLayer({ id: 'field-selected', type: 'fill', source: 'fields', filter: ['==', ['get', 'field_id'], selectedField],
                            paint: { 'fill-color': '#ffb45b', 'fill-opacity': 0.48 } });
        instance.on('click', 'field-fill', event => {
          if (drawing.current) return;
          const id = event.features?.[0]?.properties?.field_id;
          if (typeof id === 'string') onSelect(id);
        });
        instance.on('mouseenter', 'field-fill', () => { instance.getCanvas().style.cursor = 'pointer'; });
        instance.on('mouseleave', 'field-fill', () => { instance.getCanvas().style.cursor = ''; });
      });
      return () => { tourToken.current += 1; drawing.current = false; setMapReady(false); map.current = null; instance.remove(); };
    } catch { return; } // Field list remains usable when WebGL is unavailable.
  }, [assets, onSelect]);
  useEffect(() => {
    const instance = map.current;
    if (!instance || !mapReady || !manifest) return;
    const scene = manifest.scenes.find(item => item.period === period);
    if (!scene) return;
    const layer = scene.layers[polarization];
    const source = instance.getSource('nisar-observation') as maplibregl.ImageSource | undefined;
    const image = { url: `${import.meta.env.BASE_URL || '/'}studio/${layer.image}`,
                    coordinates: scene.coordinates as [[number, number], [number, number], [number, number], [number, number]] };
    if (source) source.updateImage(image);
    else {
      instance.addSource('nisar-observation', { type: 'image', ...image });
      instance.addLayer({ id: 'nisar-observation', type: 'raster', source: 'nisar-observation',
        paint: { 'raster-opacity': opacity / 100 }, layout: { visibility: layerVisible ? 'visible' : 'none' } }, 'field-fill');
    }
    instance.setLayoutProperty('nisar-observation', 'visibility', layerVisible ? 'visible' : 'none');
    instance.setPaintProperty('nisar-observation', 'raster-opacity', opacity / 100);
  }, [mapReady, manifest, period, polarization, layerVisible, opacity]);
  useEffect(() => {
    const instance = map.current;
    const feature = assets.fields.features.find(f => f.properties.field_id === selectedField);
    if (!instance || !feature || touring.current) return;
    const fit = () => {
      if (instance.getLayer('field-selected')) instance.setFilter('field-selected', ['==', ['get', 'field_id'], selectedField]);
      const [west, south, east, north] = geometryBounds(feature);
      instance.fitBounds([[west, south], [east, north]], { padding: 70, maxZoom: 14, duration: 450 });
    };
    if (instance.isStyleLoaded()) fit(); else instance.once('load', fit);
  }, [assets, selectedField]);
  const feature = assets.fields.features.find(f => f.properties.field_id === selectedField);
  const bounds = feature ? geometryBounds(feature) : null;
  const scene = manifest?.scenes.find(item => item.period === period);
  const flyFromEarth = async () => {
    const instance = map.current;
    if (!instance || !bounds) return;
    const token = ++tourToken.current;
    touring.current = true;
    instance.stop();
    instance.jumpTo({ center: [0, 18], zoom: 1.3, pitch: 0, bearing: 0 });
    const center: [number, number] = [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2];
    setTourStage('Earth overview');
    await new Promise(resolve => setTimeout(resolve, 350));
    const steps: Array<{ label: string; center: [number, number]; zoom: number; pitch: number; duration: number }> = [
      { label: 'Taiwan', center: [121, 23.7], zoom: 5.4, pitch: 12, duration: 1150 },
      { label: 'Yunlin', center: [120.35, 23.72], zoom: 9.2, pitch: 25, duration: 1150 },
      { label: 'Taixi', center: [120.19, 23.70], zoom: 11.4, pitch: 38, duration: 1150 },
      { label: selectedField, center, zoom: 14, pitch: 48, duration: 1300 },
    ];
    for (const step of steps) {
      if (token !== tourToken.current) return;
      setTourStage(step.label);
      await new Promise<void>(resolve => { instance.once('moveend', () => resolve());
        instance.flyTo({ ...step, bearing: step.label === 'Earth overview' ? 0 : -16, essential: true }); });
    }
    touring.current = false;
  };
  return <div className="studio-map-panel">
    <div className="studio-map-toolbar"><button type="button" onClick={() => void flyFromEarth()} disabled={!mapReady}>Fly from Earth → selected field</button><span aria-live="polite">Camera: {tourStage}</span></div>
    <div className="studio-map-shell">
      <div ref={container} className="studio-map" data-map-ready={mapReady} role="img" aria-label="MapLibre NASA satellite map with five agricultural candidate polygons" />
      <div className="studio-map-meta">NASA Blue Marble 2004 · Landsat WELD 2000 annual context<br />
        Candidate field · EPSG:4326 · {bounds ? bounds.map(coordText).join(', ') : 'coordinates unavailable'}<br />
        Basemap is visual context, not 2026 event evidence.</div>
    </div>
    {mapReady && map.current && import.meta.env.VITE_GIS_EDITOR !== 'false' && (
      <PolygonEditor map={map.current} onActive={active => { drawing.current = active; }} />
    )}
    <p className="studio-map-credit"><a href="https://earthobservatory.nasa.gov/features/BlueMarble" target="_blank" rel="noreferrer">NASA Blue Marble</a> · <a href="https://worldview.earthdata.nasa.gov/?l=Landsat_WELD_CorrectedReflectance_TrueColor_Global_Annual" target="_blank" rel="noreferrer">Landsat WELD annual true color</a> · tiles served by <a href="https://www.earthdata.nasa.gov/data/tools/gibs" target="_blank" rel="noreferrer">NASA EOSDIS GIBS</a>. Candidate field boundaries: <a href="https://data.gov.tw/en/datasets/166618" target="_blank" rel="noreferrer">Taiwan Ministry of Agriculture, National Agricultural Field Block Map</a> (Open Government Data License v1); Taixi township boundary: <a href="https://maps.nlsc.gov.tw/pro/download.jsp" target="_blank" rel="noreferrer">NLSC, Ministry of the Interior</a>. Historic basemap imagery is visual context, not 2026 event evidence.</p>
    <div className="studio-radar-controls"><strong>NISAR independent observation · Taixi Township</strong>
      <div className="studio-radar-actions"><button type="button" aria-pressed={layerVisible} onClick={() => setLayerVisible(value => !value)} disabled={!manifest}>{layerVisible ? 'Hide' : 'Show'} radar layer</button>
        <label>Observation timeline<select aria-label="NISAR observation" value={period} onChange={event => setPeriod(event.target.value as 'PRE' | 'POST')} disabled={!manifest}><option value="PRE">2026-10-16 · provisional P05023</option><option value="POST">2026-10-28 · validated P05036</option></select></label>
        <label>Polarization<select aria-label="NISAR polarization" value={polarization} onChange={event => setPolarization(event.target.value as 'HH' | 'HV')} disabled={!manifest}><option value="HH">HH</option><option value="HV">HV</option></select></label>
        <label>Radar opacity <output>{opacity}%</output><input aria-label="Radar opacity" type="range" min="10" max="100" value={opacity} onChange={event => setOpacity(Number(event.target.value))} disabled={!manifest} /></label></div>
      {mapError && <p className="studio-warning" role="status">{mapError}</p>}
      {scene && <p className="studio-muted">{scene.acquisition_start_utc} · {scene.product_maturity} {scene.crid} · {polarization} · {scene.layers[polarization].valid_pixels.toLocaleString()} QA-valid pixels · {scene.scene_id}</p>}
      <p className="studio-warning">Each HH/HV image has its own display stretch. Taixi is a township AOI, not any selected candidate field. Cross-CRID radiometric equivalence and parcel damage are unverified; this toggle never computes a date difference.</p>
    </div>
  </div>;
}

function VhChart({ rows, fieldId, comparison }: { rows: VhObservation[]; fieldId: string; comparison: FieldComparison }) {
  const valid = rows.filter(r => r.field_id === fieldId && r.vh_median_db !== null && !r.qa_flags.includes('INSUFFICIENT_SPATIAL_SUPPORT'));
  const values = valid.map(r => r.vh_median_db as number);
  if (!valid.length) return <p className="studio-empty">No QA-passing VH pixels for this candidate.</p>;
  const min = Math.floor(Math.min(...values) - 1), max = Math.ceil(Math.max(...values) + 1);
  const width = 760, height = 290, left = 65, right = 20, top = 22, bottom = 46;
  const x = (time: string) => {
    const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Taipei', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
      .formatToParts(new Date(time));
    const number = (name: string) => Number(parts.find(part => part.type === name)?.value);
    const aligned = Date.UTC(2025, number('month') - 1, number('day'), number('hour'), number('minute'));
    return left + (aligned - Date.UTC(2025, 9, 1)) / (Date.UTC(2025, 10, 7) - Date.UTC(2025, 9, 1)) * (width - left - right);
  };
  const y = (db: number) => top + (max - db) / (max - min) * (height - top - bottom);
  const eventX = x(comparison.event_reference.start_taiwan), eventEndX = x(comparison.event_reference.end_taiwan);
  const byYear = [2025, 2026].map(year => valid.filter(r => r.year === year).sort((a, b) => a.acquisition_datetime.localeCompare(b.acquisition_datetime)));
  return <div className="studio-chart-wrap"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Observed 2025 and 2026 VH backscatter curves for ${fieldId}`}>
    <rect x={eventX} y={top} width={eventEndX - eventX} height={height - top - bottom} fill="#d2675b" opacity=".18" />
    {[min, (min + max) / 2, max].map(tick => <g key={tick}><line x1={left} x2={width-right} y1={y(tick)} y2={y(tick)} stroke="#405567" strokeDasharray="3 5" /><text x={left-8} y={y(tick)+4} textAnchor="end" fill="#a8bac8" fontSize="11">{tick.toFixed(1)}</text></g>)}
    {['10-01', '10-08', '10-15', '10-22', '10-29', '11-05'].map(day => <text key={day} x={x(`2025-${day}T00:00:00+08:00`)} y={height-17} fill="#a8bac8" fontSize="11">{day.replace('-', '/')}</text>)}
    {byYear.map((group, index) => {
      const color = index === 0 ? '#58b8e7' : '#ffae66';
      return <g key={index}>
        {group.slice(1).map((r, i) => {
          const prior = group[i];
          const gap = (Date.parse(r.acquisition_datetime) - Date.parse(prior.acquisition_datetime)) / 86400000;
          return gap <= 24 ? <line key={r.evidence_id} x1={x(prior.acquisition_datetime)} y1={y(prior.vh_median_db as number)} x2={x(r.acquisition_datetime)} y2={y(r.vh_median_db as number)} stroke={color} strokeWidth="2" /> : null;
        })}
        {group.map(r => <circle key={r.evidence_id} cx={x(r.acquisition_datetime)} cy={y(r.vh_median_db as number)} r="5" fill={color}><title>{`${new Date(r.acquisition_datetime).toLocaleString('en-GB', { timeZone: 'Asia/Taipei' })} Taiwan | ${dateText(r.acquisition_datetime)} | ${r.vh_median_db} dB | ${r.valid_pixel_count} px | ${r.evidence_id}`}</title></circle>)}
      </g>;
    })}
    <text x="10" y="16" fill="#d9e5ed" fontSize="11">VH backscatter (dB)</text>
    <text x={eventX-28} y="15" fill="#ff9c91" fontSize="10">CWA land-warning window</text>
  </svg><div className="studio-chart-legend"><span><b className="year25" />2025</span><span><b className="year26" />2026</span><span>Taiwan calendar dates · actual OPERA acquisitions · gaps &gt;24 days stay disconnected</span></div></div>;
}

function EvidenceGraph({ result, assets, onSelect }: { result: StudioInvestigation; assets: StudioAssets; onSelect: (node: GraphNode) => void }) {
  const graph = useMemo(() => buildEvidenceGraph(result, assets.evidence), [result, assets]);
  const order: GraphNode['type'][] = ['DATASET', 'OBSERVATION', 'EVIDENCE', 'HYPOTHESIS', 'SCIENTIFIC_TEST', 'CONCLUSION', 'ACTION'];
  const positioned = graph.nodes.map(node => {
    const col = order.indexOf(node.type);
    const peers = graph.nodes.filter(n => n.type === node.type);
    const row = peers.findIndex(n => n.id === node.id);
    return { node, x: 75 + col * 215, y: 48 + row * 49 };
  });
  const loc = new Map(positioned.map(x => [x.node.id, x]));
  const contentHeight = Math.max(430, ...positioned.map(p => p.y + 35));
  return <div className="studio-graph-scroll"><svg viewBox={`0 0 1450 ${contentHeight}`} role="img" aria-label="Evidence provenance graph from registered API references">
    {graph.edges.map((edge, index) => {
      const a = loc.get(edge.from), b = loc.get(edge.to);
      return a && b ? <line key={index} x1={a.x+80} y1={a.y} x2={b.x-80} y2={b.y} stroke="#456579" strokeWidth="1" opacity=".6"><title>{edge.relation}</title></line> : null;
    })}
    {positioned.map(({ node, x, y }) => <g key={node.id} role="button" tabIndex={0} onClick={() => onSelect(node)} onKeyDown={event => { if (event.key === 'Enter') onSelect(node); }} className="studio-graph-node">
      <rect x={x-82} y={y-17} width="164" height="34" rx="8" fill={node.label.startsWith('UNRESOLVED') ? '#743d44' : '#19394b'} stroke="#67bdd2" />
      <text x={x} y={y+4} textAnchor="middle" fill="#eaf7fa" fontSize="10">{node.label.slice(0, 24)}</text><title>{`${node.type}: ${node.label}`}</title>
    </g>)}
  </svg></div>;
}

function downloadJson(value: unknown, name: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = name; anchor.click();
  URL.revokeObjectURL(url);
}

export const InvestigationStudio: React.FC = () => {
  const [assets, setAssets] = useState<StudioAssets | null>(null);
  const [error, setError] = useState('');
  const [mode, setMode] = useState<StudioMode>('RECORDED_DETERMINISTIC');
  const [selectedField, setSelectedField] = useState('YL-CAND-01');
  const [question, setQuestion] = useState(questionForField('YL-CAND-01'));
  const [live, setLive] = useState<{ field: string; mode: StudioMode; result: StudioInvestigation } | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<Record<string, unknown> | null>(null);
  const [evidenceError, setEvidenceError] = useState('');
  const [storyStep, setStoryStep] = useState(0);
  const [challengeId, setChallengeId] = useState<string | null>(null);
  const [challenge, setChallenge] = useState<{ field: string; kind: ChallengeKind; output?: Record<string, unknown>; error?: string } | null>(null);
  const [challengeRunning, setChallengeRunning] = useState(false);
  useEffect(() => { let active = true; loadStudioAssets().then(value => { if (active) { const first = String(value.fields.features[0]?.properties.field_id || 'YL-CAND-01'); setAssets(value); setSelectedField(first); setQuestion(questionForField(first, value.comparison)); } }).catch(err => { if (active) setError(String(err)); }); return () => { active = false; }; }, []);
  const recordedField = assets?.recorded.vh_timeseries?.field_id;
  const deterministicField = assets?.recordedDeterministic.vh_timeseries?.field_id;
  const isLive = mode === 'LIVE_DETERMINISTIC' || mode === 'LIVE_GEMINI';
  const result = mode === 'RECORDED_GEMINI' ? (selectedField === recordedField ? assets?.recorded : null) :
    mode === 'RECORDED_DETERMINISTIC' ? (selectedField === deterministicField ? assets?.recordedDeterministic : null) :
      (live?.field === selectedField && live.mode === mode ? live.result : null);
  const trace = mode === 'RECORDED_GEMINI' ? (result ? assets?.recordedTrace.trace || [] : []) : (result?.tool_trace || []);
  const unresolved = result && assets ? referencedIds(result).filter(id => !assets.evidence.has(id)) : [];
  const fieldRows = assets?.vh.observations.filter(r => r.field_id === selectedField) || [];
  const fieldFeature = assets?.fields.features.find(f => f.properties.field_id === selectedField);
  const chooseField = useCallback((id: string) => {
    setSelectedField(id);
    setQuestion(questionForField(id, assets?.comparison));
    setSelectedEvidence(null);
    setChallengeId(null);
  }, [assets?.comparison]);
  const run = async () => {
    setLoading(true); setError(''); setLive(null); setSelectedNode(null);
    try { const response = await investigateLive(selectedField, question, mode === 'LIVE_GEMINI' ? 'gemini' : 'deterministic'); setLive({ field: selectedField, mode, result: response }); }
    catch (err) { setError(String(err)); }
    finally { setLoading(false); }
  };
  const openEvidence = async (id: string) => {
    setEvidenceError(''); setSelectedEvidence(null);
    const local = assets?.evidence.get(id);
    if (local) { setSelectedEvidence(local); return; }
    try {
      const response = await fetch(`/api/agent/champi/evidence/${encodeURIComponent(id)}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const record = await response.json() as Record<string, unknown>;
      if (record.evidence_id !== id) throw new Error('Evidence ID mismatch');
      setSelectedEvidence(record);
    } catch { setEvidenceError(`UNRESOLVED_REFERENCE: ${id}`); }
  };
  const runChallenge = async (kind: ChallengeKind) => {
    if (!assets) return;
    setChallengeRunning(true);
    setChallenge({ field: selectedField, kind });
    try { setChallenge({ field: selectedField, kind, output: await runEvidenceChallenge(kind, selectedField, assets.evidence) }); }
    catch (err) { setChallenge({ field: selectedField, kind, error: String(err) }); }
    finally { setChallengeRunning(false); }
  };
  const stories = [
    ['01 DISASTER', 'studio-disaster'], ['02 SATELLITE OBSERVATION', 'studio-observations'],
    ['03 AGRICULTURAL RADAR CHANGE', 'studio-field-change'], ['04 AI INVESTIGATION', 'studio-question'],
    ['05 EVIDENCE VERIFICATION', 'studio-evidence'], ['06 HUMAN ACTION', 'studio-action'],
  ];
  if (!assets && !error) return <main className="studio-root"><p role="status">Loading verified investigation assets…</p></main>;
  return <main className="studio-root">
    <header className="studio-header"><div><a href="/" className="studio-back">← SAR2Action</a><p className="studio-eyebrow">SAR2ACTION / SCIENTIFIC INVESTIGATION</p><h1>Investigation Studio</h1><p>Observe → Investigate → Test → Verify → Act</p></div><div className="studio-mode"><label htmlFor="studio-mode">Execution mode</label><select id="studio-mode" value={mode} onChange={e => { setMode(e.target.value as StudioMode); setError(''); setSelectedNode(null); }}><option value="RECORDED_DETERMINISTIC">Recorded deterministic investigation</option><option value="RECORDED_GEMINI">Recorded Gemini execution</option><option value="LIVE_DETERMINISTIC">Live deterministic API</option><option value="LIVE_GEMINI">Live Gemini API</option></select><small>{isLive ? 'Runs POST /api/agent/investigate-v3 when you investigate' : 'Historical completed execution · never presented as live'}</small></div></header>
    {error && <div className="studio-alert" role="alert">{error}</div>}
    {assets?.integrityWarnings.map(w => <div className="studio-alert" role="alert" key={w}>{w}</div>)}
    <nav className="studio-story" aria-label="NASA story mode">{stories.map(([label, id], index) => <button key={id} type="button" aria-current={storyStep === index ? 'step' : undefined} onClick={() => { setStoryStep(index); document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' }); }}>{label}</button>)}</nav>
    {assets && <>
      <section id="studio-disaster" className="studio-card studio-disaster"><div><p className="studio-kicker">01 / OFFICIAL CONTEXT</p><h2>Typhoon CHAMPI · October 2026</h2><p>Official loss context is county level. It does not identify losses for these candidate fields.</p></div><div><strong>Yunlin county reported loss</strong><p>{assets.officialLoss.yunlin_county_ntd === null || assets.officialLoss.yunlin_county_ntd === undefined ? 'unavailable' : `NT$ ${Number(assets.officialLoss.yunlin_county_ntd).toLocaleString()}`}</p>{typeof assets.officialLoss.source_url === 'string' && <a href={assets.officialLoss.source_url} target="_blank" rel="noreferrer">Official source ↗</a>}</div></section>
      <section className="studio-workspace"><div className="studio-main-col">
        <section id="studio-observations" className="studio-card"><div className="studio-section-head"><div><p className="studio-kicker">02 / OBSERVE</p><h2>Agricultural candidate map</h2></div><label>Field candidate<select aria-label="Field candidate" value={selectedField} onChange={e => chooseField(e.target.value)} >{assets.fields.features.map(f => <option key={String(f.properties.field_id)} value={String(f.properties.field_id)}>{String(f.properties.field_id)}</option>)}</select></label></div>
          <FieldMap assets={assets} selectedField={selectedField} onSelect={chooseField} />
          <p className="studio-muted">{asText(fieldFeature?.properties.status)} · Rice crop unverified · {fieldFeature?.properties.area_m2 ? Number(fieldFeature.properties.area_m2).toLocaleString() : 'unavailable'} m² boundary · visual mixed land use review {asText(fieldFeature?.properties.visual_mixed_land_use_review)}</p>
        </section>
        <section className="studio-card"><p className="studio-kicker">MULTI-SENSOR TIME EXPLORER</p><h2>Sentinel-1 VH · same field, two seasons</h2><p className="studio-muted">C-band OPERA RTC-S1 gamma0 · Taiwan month/day alignment · all statistics from acquired scenes</p><VhChart rows={assets.vh.observations} fieldId={selectedField} comparison={assets.comparison} />
          <div className="studio-measures"><span>2025: {fieldRows.filter(r => r.year === 2025).length} observations</span><span>2026: {fieldRows.filter(r => r.year === 2026).length} observations</span><span>Orbit: {asText(fieldRows[0]?.relative_orbit)} {asText(fieldRows[0]?.orbit_direction)}</span></div>
          <details><summary>Inspect actual VH acquisition dates and pixel counts</summary><div className="studio-table-scroll"><table><thead><tr><th>Acquired UTC</th><th>VH median dB</th><th>Valid pixels</th><th>Coverage</th><th>Platform</th><th>Evidence</th></tr></thead><tbody>{fieldRows.map(r => <tr key={r.evidence_id}><td>{dateText(r.acquisition_datetime)}</td><td>{r.vh_median_db === null ? 'unavailable' : r.vh_median_db.toFixed(3)}</td><td>{r.valid_pixel_count}</td><td>{(r.valid_coverage_ratio*100).toFixed(1)}%</td><td>{r.platform}</td><td><button type="button" className="studio-link" onClick={() => void openEvidence(r.evidence_id)}>{r.evidence_id}</button></td></tr>)}</tbody></table></div></details>
          <h3>NISAR L-band observations · Taixi AOI</h3><p className="studio-warning">Scientific compatibility warning: October 16 P05023 is provisional; October 28 P05036 is validated. Cross-CRID radiometric equivalence is unverified. Do not compute a verified pre/post typhoon NISAR difference or subtract NISAR HV from Sentinel-1 VH.</p>
          <div className="studio-nisar">{assets.recorded.observation_timeline.filter(x => x.mission === 'NISAR').map(x => <article key={String(x.evidence_id)}><strong>{dateText(x.acquisition_start_utc)}</strong><span>{asText(x.product_maturity)} · {asText(x.crid)} · {asText(x.valid_pixels)} valid pixels</span><button className="studio-link" onClick={() => void openEvidence(String(x.evidence_id))}>{asText(x.evidence_id)}</button></article>)}</div>
        </section>
        <FieldFindings comparison={assets.comparison} fieldId={selectedField} onEvidence={id => void openEvidence(id)} />
      </div><div className="studio-side-col">
        <section id="studio-question" className="studio-card"><p className="studio-kicker">03 / SCIENTIFIC QUESTION</p><h2>Investigate this AOI</h2><label htmlFor="studio-question-input">Ask the Scientific Agent</label><textarea id="studio-question-input" value={question} onChange={e => setQuestion(e.target.value)} rows={4} />
          <button className="studio-primary" type="button" disabled={loading || !isLive} onClick={() => void run()}>{loading ? 'Investigating…' : mode === 'LIVE_GEMINI' ? 'Investigate with live Gemini API' : 'Investigate with live deterministic API'}</button>
          {!isLive && <p className="studio-muted">Recorded mode displays a completed historical run. Switch to a live mode to call the API for the selected field.</p>}
          {mode === 'RECORDED_GEMINI' && selectedField !== recordedField && <p className="studio-warning">Recorded Gemini report is scoped to {recordedField}; the field’s observations remain available. Run a live investigation for {selectedField}.</p>}
          {mode === 'RECORDED_DETERMINISTIC' && selectedField !== deterministicField && <p className="studio-warning">Recorded deterministic report is scoped to {deterministicField}; the field’s observations remain available. Run a live investigation for {selectedField}.</p>}
          {result && <dl className="studio-facts"><dt>Investigation ID</dt><dd>{result.investigation_id}</dd><dt>AOI</dt><dd>{result.aoi_id} · {selectedField}</dd><dt>Data mode</dt><dd>{result.data_mode}</dd><dt>Provenance</dt><dd>{result.provenance_status}</dd></dl>}
        </section>
        <section id="studio-investigation" className="studio-card"><p className="studio-kicker">04 / SCIENTIFIC EXECUTION</p><h2>Agent execution inspector</h2>{result ? <><p className="studio-muted">{trace.length} recorded trace events · {isLive ? 'fresh API response after completion' : mode === 'RECORDED_GEMINI' ? 'historical Gemini run' : 'historical deterministic run'} · no simulated streaming</p><div className="studio-trace">{trace.map((event, index) => <details key={`${event.step || index}-${index}`}><summary><span>{String(event.kind || 'tool_result').toUpperCase().replace('_', ' ')}</span><strong>{asText(event.tool)}</strong><em>{asText(event.status)}</em></summary><div className="studio-trace-detail"><p>Recorded: {dateText(event.timestamp_utc)}</p><pre>{JSON.stringify(event, null, 2)}</pre></div></details>)}</div></> : <p className="studio-empty">No investigation for the selected field and mode.</p>}
          {mode === 'RECORDED_GEMINI' && selectedField === recordedField && <details className="studio-extra-trace"><summary>Additional recorded Gemini five-field run · separate investigation ID</summary><p className="studio-muted">This tool trace has no paired full report. It is shown separately and is not combined with the report above. Gemini selected: {assets.recentGeminiTrace.selected_tools.flat().join(', ')}.</p><p className="studio-muted">Investigation ID: {assets.recentGeminiTrace.investigation_id}</p><div className="studio-trace">{assets.recentGeminiTrace.tool_trace.map((event, index) => <details key={`${event.step || index}-${index}`}><summary>{asText(event.kind)} · {asText(event.tool)} · {asText(event.status)}</summary><pre>{JSON.stringify(event, null, 2)}</pre></details>)}</div></details>}
        </section>
        <section className="studio-card"><p className="studio-kicker">SCIENTIFIC VALIDATION</p><h2>Executed tests & QA</h2>{result ? <><p className="studio-warning">{asText(result.qa.qa_decision)} · {asText(result.qa.reason)}</p><ul className="studio-test-list">{result.hypothesis_tests.map((test, index) => <li key={index}><strong>{asText(test.test_id)}</strong> <span className="studio-status">{asText(test.status)}</span><p>{asText(test.result)}</p><small>{asList(test.evidence_ids).join(', ') || 'No Evidence IDs recorded'}</small></li>)}</ul></> : <p className="studio-empty">Run or select a matching investigation to inspect tests.</p>}</section>
      </div></section>
      <section id="studio-evidence" className="studio-card"><p className="studio-kicker">05 / VERIFY</p><h2>Evidence provenance graph</h2>{result ? <><p className="studio-muted">Nodes and relationships come only from registered Evidence IDs, timeline references and executed tests. Select a node for provenance.</p><EvidenceGraph result={result} assets={assets} onSelect={node => { setSelectedNode(node); if (node.type === 'EVIDENCE' && typeof node.payload.evidence_id === 'string') void openEvidence(node.payload.evidence_id); }} />
        {unresolved.length > 0 && <p className="studio-warning">UNRESOLVED_REFERENCE: {unresolved.join(', ')}</p>}
        {selectedNode && <aside className="studio-node-detail"><h3>{selectedNode.type} · {selectedNode.label}</h3><pre>{JSON.stringify(selectedNode.payload, null, 2)}</pre></aside>}</> : <p className="studio-empty">Select the recorded field or complete a live investigation to inspect graph links.</p>}
        {evidenceError && <p className="studio-warning" role="alert">{evidenceError}</p>}
        {selectedEvidence && <aside className="studio-node-detail"><h3>Resolved Evidence · {asText(selectedEvidence.evidence_id)}</h3><pre>{JSON.stringify(selectedEvidence, null, 2)}</pre></aside>}
      </section>
      <section className="studio-card"><p className="studio-kicker">READ-ONLY EVIDENCE CHALLENGE</p><h2>Rerun scientific checks</h2>
        <p className="studio-muted">Each check calls an existing deterministic API and returns source Evidence IDs. It does not change hypothesis status or establish crop damage.</p>
        <div className="studio-actions">{([
          ['timing', 'Observation timing'], ['seasonal', 'Seasonal comparison'],
          ['cross_field', 'Cross-field comparison'], ['cross_crid', 'Cross-CRID compatibility'],
          ['ground_truth', 'Missing ground truth'],
        ] as [ChallengeKind, string][]).map(([kind, label]) => <button key={kind} type="button" disabled={challengeRunning} onClick={() => void runChallenge(kind)}>{label}</button>)}</div>
        {challenge?.field === selectedField && <div role="status" className="studio-node-detail">
          <h3>{challenge.kind} · {challenge.output ? asText(challenge.output.status) : challenge.error ? 'NOT AVAILABLE' : 'Running…'}</h3>
          {challenge.error && <p className="studio-warning">{challenge.error}</p>}
          {challenge.output && <><p>Execution: {asText(challenge.output.execution)} · Evidence IDs: {asList(challenge.output.evidence_ids).join(', ') || 'none registered'}</p><details><summary>Inspect actual test result</summary><pre>{JSON.stringify(challenge.output, null, 2)}</pre></details></>}
        </div>}
      </section>
      <section className="studio-card"><p className="studio-kicker">TEST / HYPOTHESIS CHALLENGE</p><h2>Competing explanations</h2>{result ? <div className="studio-hypotheses">{result.hypotheses.map((h, index) => {
        const id = String(h.hypothesis_id || index);
        const linkedTests = result.hypothesis_tests.filter(test => id === 'storm_disturbance'
          ? String(test.test_id).startsWith('vh_') : id === 'observation_processing'
            ? test.test_id === 'cross_crid_radiometric_compatibility' : false);
        return <article key={id}><div><h3>{id}</h3><span className="studio-status">{asText(h.status)}</span></div>
          <p>{asText(h.statement)}</p><p>Validation: {asText(h.test_status)}</p>
          <button type="button" onClick={() => setChallengeId(challengeId === id ? null : id)} aria-expanded={challengeId === id}>Inspect challenge evidence</button>
          {challengeId === id && <div className="studio-challenge-detail"><p>{asText(h.falsification_check)}</p>
            <strong>Recorded relevant tests</strong>{linkedTests.length ? <ul>{linkedTests.map(test => <li key={String(test.test_id)}>{asText(test.test_id)} · {asText(test.status)} — {asText(test.result)}</li>)}</ul> : <p>No hypothesis-specific test was executed. Field records or independent measurements are needed.</p>}
            <strong>Support references</strong><p>{asList(h.supporting_evidence_ids).length ? asList(h.supporting_evidence_ids).map(ref => <button key={ref} type="button" className="studio-link" onClick={() => void openEvidence(ref)}>{ref} </button>) : 'No cause-confirming evidence registered.'}</p>
            <strong>Counter-evidence references</strong><p>{asList(h.contradicting_evidence_ids).length ? asList(h.contradicting_evidence_ids).map(ref => <button key={ref} type="button" className="studio-link" onClick={() => void openEvidence(ref)}>{ref} </button>) : 'None registered.'}</p>
            <small>Inspecting these records does not run a new scientific test or confirm damage.</small>
          </div>}
        </article>;
      })}</div> : <p className="studio-empty">No current investigation hypotheses.</p>}</section>
      <section id="studio-action" className="studio-card studio-dossier"><p className="studio-kicker">06 / ACT</p><h2>Investigation dossier</h2>{result ? <><div className="studio-report-grid"><article><h3>Observed fact</h3>{asLines(result.expert_report.observed).map((line, index) => <p key={index}>{line}</p>)}</article><article><h3>Possible interpretation</h3>{asLines(result.expert_report.possible_interpretation).map((line, index) => <p key={index}>{line}</p>)}</article><article><h3>Unresolved hypothesis</h3>{asLines(result.expert_report.unknown).map((line, index) => <p key={index}>{line}</p>)}</article><article><h3>Recommended action</h3><p>{result.recommended_next_action}</p></article></div><h3>Missing evidence</h3><ul>{result.missing_evidence.map((item, index) => <li key={index}>{item}</li>)}</ul><h3>Scientific limitations</h3><ul>{result.scientific_limitations.map((item, index) => <li key={index}>{item}</li>)}</ul><div className="studio-actions"><button type="button" onClick={() => downloadJson(makeDossier(result, mode, selectedField, trace), `SAR2Action-${result.investigation_id}.json`)}>Export dossier JSON</button><button type="button" onClick={() => window.print()}>Print dossier HTML</button></div></> : <p className="studio-empty">No dossier is available for this field and mode.</p>}</section>
    </>}
  </main>;
};
