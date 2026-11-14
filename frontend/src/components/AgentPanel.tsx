import React, { useEffect, useRef, useState } from 'react';
import type { CaseSummary, LayerMetadataResponse, RevealMode } from '../types/api';

type Bbox = [number, number, number, number];
type Action = { type: string; payload: Record<string, unknown> };
type Claim = { statement: string; evidence_id: string; unit: string };
type Region = { region_id: string; rank: number; bbox_wgs84: Bbox; crs: string;
  median_abs_change_db: number; median_signed_change_db: number; pixel_count: number;
  valid_pixel_percentage: number; area_km2_approx: number; evidence_ids: string[];
  observation_times: string[]; polarization: string; limitations: string[];
  quality_status?: string; scene_versions?: string[]; method?: string };
type Result = {
  status: string; mode: string; narrative: string; claims: Claim[]; evidence_ids: string[];
  unknowns: string[]; trace: { tool: string; status: string }[];
  map_actions: Action[]; data_notice: string; ranked_regions?: Region[];
  agent_mode?: 'real' | 'deterministic'; model_name?: string; model_provider?: string;
  comparison?: { median_abs_difference_db: number };
  fingerprint_details?: { evidence_id: string; roi_id: string; aoi_bbox_wgs84: Bbox;
    hh_delta_median_db: number | null; hv_delta_median_db: number | null;
    t0_acquisition_utc: string; t1_acquisition_utc: string; valid_pixel_count: number;
    quality_status: string; scene_ids: string[]; method: string;
    measurement_definition: string; significance_status: string; stable_control_status: string;
    mask_rule: string; distribution: Record<'HH' | 'HV', { p10_delta_db: number | null;
      p90_delta_db: number | null; median_abs_change_db: number | null;
      positive_change_fraction: number | null; negative_change_fraction: number | null }> };
  story?: Story;
  investigation_plan?: { tool: string; status: string }[];
  scientific_assessment?: { observed: { statement: string; evidence_ids: string[] }[];
    inferred: { statement: string; evidence_ids: string[] }[]; unknown: string[];
    next_steps: string[]; limitations: string[]; analysis_version: string; data_kind: string };
};
type Story = {
  story_id: string; status: 'current' | 'stale'; mode: string;
  data_notice?: string;
  evidence_ids: string[];
  frames: { title: string; narrative: string; evidence_ids: string[];
    map_state: { bbox: Bbox; layer_id: string }; visualization: string; source: string[] }[];
};

interface Props {
  initialDataMode?: 'live' | 'cache' | 'fixture';
  initialAgentMode?: 'real' | 'deterministic';
  activeCase: CaseSummary | null;
  bbox: Bbox;
  aoiId?: string;
  polarizationMode: 'DUAL' | 'HH_ONLY';
  currentEvidenceId?: string;
  availableLayers: Record<string, LayerMetadataResponse>;
  activeLayer?: RevealMode;
  onFocusBbox: (bbox: Bbox) => void;
  onSetLayer: (layer: RevealMode) => void;
  onOpenEvidence: (id: string) => void;
  onDataModeChange?: (mode: 'live' | 'cache' | 'fixture') => void;
  onRankedRegions?: (regions: { bbox_wgs84: Bbox; rank: number }[]) => void;
}

const sessionId = `web-${Math.random().toString(36).slice(2, 12)}`;
const layerIds = new Set<RevealMode>([
  't0_hh', 't1_hh', 't0_hv', 't1_hv', 'delta_hh', 'delta_hv',
  'magnitude_hh', 'magnitude_hv', 'combined_change', 'validity_mask',
  'swipe_hh', 'swipe_hv',
]);

export const AgentPanel: React.FC<Props> = (props) => {
  const [query, setQuery] = useState(props.initialDataMode === 'cache'
    ? '分析 AOI-OKI-04 的 HH/HV 雷達變化，顯示證據，並說明能否確認泥炭火災。'
    : props.initialDataMode === 'fixture'
      ? '找出目前選取範圍中變化最大的三個區域，比較它們，帶我查看證據。'
      : 'What changed in this selected area?');
  const [dataMode, setDataMode] = useState<'live' | 'cache' | 'fixture'>(props.initialDataMode || 'live');
  const [agentMode, setAgentMode] = useState<'real' | 'deterministic'>(props.initialAgentMode || 'deterministic');
  const [storyLocale, setStoryLocale] = useState<'en' | 'zh-TW'>('en');
  const [storyAudience, setStoryAudience] = useState<'public' | 'scientific'>('public');
  const [agentStatus, setAgentStatus] = useState('Agent Offline');
  const [providerStatus, setProviderStatus] = useState('');
  const [liveStatus, setLiveStatus] = useState('checking data handoff');
  const [cacheStatus, setCacheStatus] = useState('checking cached evidence');
  const [activeRegion, setActiveRegion] = useState<Region | null>(null);
  const [evidenceCard, setEvidenceCard] = useState<Record<string, unknown> | null>(null);
  const [comparison, setComparison] = useState('');
  const [result, setResult] = useState<Result | null>(null);
  const [story, setStory] = useState<Story | null>(null);
  const [frameIndex, setFrameIndex] = useState(0);
  const [phase, setPhase] = useState('Ready');
  const [running, setRunning] = useState(false);
  const [liveTrace, setLiveTrace] = useState<{ tool: string; status: string; steps?: { tool: string; status: string }[] }[]>([]);
  const [error, setError] = useState('');
  const runId = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const activityTimer = useRef<number | null>(null);
  const context = `${props.activeCase?.case_id || ''}|${props.aoiId || ''}|${props.bbox.join(',')}|${props.polarizationMode}|${dataMode}|${agentMode}`;

  useEffect(() => {
    fetch('/api/agent/status').then((response) => response.json())
      .then((status) => {
        setAgentStatus(status.agent?.status === 'online' ? 'Agent Online' : 'Agent Offline');
        setProviderStatus(status.agent?.status === 'online' ? `${status.agent.provider || 'model'} · ${status.agent.model || ''}` : '');
        setLiveStatus(status.spatial_manifest_configured ? 'manifest configured; validation runs on analysis' : 'BLOCKED: B-team change raster/manifest missing');
        setCacheStatus(status.cached_evidence?.status === 'blocked' ? 'BLOCKED: B-team evidence cache missing' : 'PROVENANCE NOT VERIFIED');
      })
      .catch(() => { setAgentStatus('Agent Offline'); setLiveStatus('status unavailable'); });
  }, []);

  useEffect(() => {
    runId.current += 1;
    if (controller.current && !controller.current.signal.aborted) {
      void fetch(`/api/agent/cancel/${sessionId}`, { method: 'POST' }).catch(() => {});
    }
    controller.current?.abort();
    controller.current = null;
    if (activityTimer.current !== null) window.clearInterval(activityTimer.current);
    setResult(null);
    setActiveRegion(null);
    setEvidenceCard(null);
    setComparison('');
    props.onRankedRegions?.([]);
    setStory((current) => current ? { ...current, status: 'stale' } : null);
    setPhase('Ready');
    setRunning(false);
    setLiveTrace([]);
  }, [context]);

  useEffect(() => {
    if (!controller.current || controller.current.signal.aborted) return;
    void fetch(`/api/agent/cancel/${sessionId}`, { method: 'POST' }).catch(() => {});
    controller.current.abort();
    controller.current = null;
    runId.current += 1;
    if (activityTimer.current !== null) window.clearInterval(activityTimer.current);
    setRunning(false);
    setPhase('Cancelled: map layer changed');
  }, [props.activeLayer]);

  const focus = (bbox: unknown) => {
    if (!Array.isArray(bbox) || bbox.length !== 4 || !bbox.every((v) => typeof v === 'number' && Number.isFinite(v))) return;
    const [w, s, e, n] = bbox;
    if (w < e && s < n && w >= -180 && e <= 180 && s >= -90 && n <= 90) props.onFocusBbox(bbox as Bbox);
  };

  const dispatch = (action: Action, evidenceId: string) => {
    switch (action.type) {
      case 'map.focus_bbox':
      case 'map.highlight_aoi': focus(action.payload.bbox); break;
      case 'map.set_layer': {
        const id = action.payload.layer_id;
        if (typeof id === 'string' && layerIds.has(id as RevealMode) && id in props.availableLayers) props.onSetLayer(id as RevealMode);
        break;
      }
      case 'evidence.open':
        if (action.payload.evidence_id === evidenceId) void openEvidence(evidenceId);
        break;
      case 'fingerprint.open':
        if (action.payload.evidence_id === evidenceId) document.getElementById('fingerprint-panel')?.scrollIntoView?.();
        break;
    }
  };

  const openEvidence = async (evidenceId: string) => {
    if (!result?.evidence_ids.includes(evidenceId)) return;
    const matchingRegion = result.ranked_regions?.find((region) => region.evidence_ids.includes(evidenceId));
    if (matchingRegion) { setActiveRegion(matchingRegion); focus(matchingRegion.bbox_wgs84); }
    const contextRun = runId.current;
    if (result.mode === 'fixture' || result.ranked_regions?.length) {
      try {
        const response = await fetch(`/api/agent/spatial/evidence/${encodeURIComponent(evidenceId)}`);
        if (!response.ok) throw new Error('Evidence not found');
        const card = await response.json() as Record<string, unknown>;
        if (contextRun === runId.current) setEvidenceCard(card);
      } catch (cause) { setError(String(cause)); }
    } else if (result.mode === 'cache') {
      try {
        const response = await fetch(`/api/evidence/${encodeURIComponent(evidenceId)}`);
        if (!response.ok) throw new Error('Cached evidence not found');
        const card = await response.json() as Record<string, unknown>;
        if (contextRun === runId.current) {
          setEvidenceCard(card);
          focus(result.fingerprint_details?.aoi_bbox_wgs84);
          props.onOpenEvidence(evidenceId);
        }
      } catch (cause) { if (contextRun === runId.current) setError(String(cause)); }
    } else props.onOpenEvidence(evidenceId);
  };

  const selectRegion = (region: Region) => {
    if (!result?.evidence_ids.includes(region.evidence_ids[0]) || region.crs !== 'EPSG:4326') return;
    setActiveRegion(region);
    focus(region.bbox_wgs84);
    void openEvidence(region.evidence_ids[0]);
  };

  const compareRegions = async () => {
    if (!result?.ranked_regions || result.ranked_regions.length < 2) return;
    const [a, b] = result.ranked_regions;
    const contextRun = runId.current;
    try {
      const response = await fetch('/api/agent/spatial/compare', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ first_evidence_id: a.evidence_ids[0], second_evidence_id: b.evidence_ids[0] }) });
      const body = await response.json();
      if (!response.ok) throw new Error(String(body.detail || 'Comparison failed'));
      if (contextRun === runId.current) setComparison(`Rank 1 minus rank 2 median absolute change: ${body.median_abs_difference_db.toFixed(3)} dB. Cause remains unknown.`);
    } catch (cause) { if (contextRun === runId.current) setError(String(cause)); }
  };

  const investigate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!props.activeCase) return;
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    const id = ++runId.current;
    setError(''); setPhase('Analysis request running…'); setRunning(true); setLiveTrace([]);
    const timer = window.setInterval(() => {
      fetch(`/api/agent/operations/${sessionId}`, { signal: abort.signal })
        .then((response) => response.json())
        .then((body) => {
          if (id !== runId.current || abort.signal.aborted) return;
          const events = body.events as { tool: string; status: string; steps?: { tool: string; status: string }[] }[];
          if (Array.isArray(events) && events.length) {
            setLiveTrace(events);
            const latest = events[events.length - 1];
            setPhase(`${latest.tool}: ${latest.status}`);
          }
        }).catch(() => {});
    }, 600);
    activityTimer.current = timer;
    try {
      const response = await fetch('/api/agent/investigate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: abort.signal,
        body: JSON.stringify({ case_id: props.activeCase.case_id, aoi_bbox_wgs84: props.bbox,
          aoi_id: props.aoiId, requested_polarizations: props.polarizationMode === 'HH_ONLY' ? ['HH'] : undefined,
          query, session_id: sessionId, intent: 'auto', data_mode: dataMode, agent_mode: agentMode }),
      });
      const body = await response.json();
      if (id !== runId.current) return;
      if (!response.ok) throw new Error(body.detail?.message || body.detail || `Analysis failed (${response.status})`);
      if (body.status !== 'completed') throw new Error(body.reason || 'Insufficient comparable observations');
      if (!body.claims.every((claim: Claim) => body.evidence_ids.includes(claim.evidence_id))) throw new Error('Evidence validation failed');
      const completed = body as Result;
      setResult(completed);
      props.onRankedRegions?.(completed.ranked_regions || []);
      const firstRegion = completed.ranked_regions?.[0];
      setActiveRegion(firstRegion || null);
      setEvidenceCard(null);
      if (firstRegion) {
        focus(firstRegion.bbox_wgs84);
        const evidenceResponse = await fetch(`/api/agent/spatial/evidence/${encodeURIComponent(firstRegion.evidence_ids[0])}`, { signal: abort.signal });
        if (!evidenceResponse.ok) throw new Error('Ranked region evidence is unavailable');
        const card = await evidenceResponse.json() as Record<string, unknown>;
        if (id !== runId.current) return;
        setEvidenceCard(card);
        window.requestAnimationFrame(() => document.getElementById('agent-region-fingerprint')?.scrollIntoView?.({ block: 'nearest' }));
      } else {
        completed.map_actions.forEach((action) => {
          if (action.type === 'map.focus_bbox' || action.type === 'map.highlight_aoi') focus(action.payload.bbox);
        });
      }
      setComparison(completed.comparison ? `Rank 1 minus rank 2 median absolute change: ${completed.comparison.median_abs_difference_db.toFixed(3)} dB. Cause remains unknown.` : '');
      setStory(completed.story || null);
      if (completed.story) setFrameIndex(0);
      setPhase('Evidence validated; map focused');
    } catch (cause) {
      if (id !== runId.current || abort.signal.aborted) return;
      setError(String(cause)); setPhase('Failed');
    } finally {
      window.clearInterval(timer);
      if (activityTimer.current === timer) activityTimer.current = null;
      if (id === runId.current) { setRunning(false); controller.current = null; }
    }
  };

  const buildStory = async () => {
    const evidenceId = activeRegion?.evidence_ids[0] || result?.evidence_ids[0];
    if (!evidenceId || (result?.mode !== 'fixture' && result?.mode !== 'cache' && !result?.ranked_regions?.length && evidenceId !== props.currentEvidenceId)) { setError('The AOI evidence is stale. Run analysis again.'); return; }
    setPhase('Building evidence story…');
    const contextRun = runId.current;
    try {
      const response = await fetch('/api/agent/story', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, evidence_id: evidenceId, locale: storyLocale, audience: storyAudience }) });
      const body = await response.json();
      if (contextRun !== runId.current) return;
      if (!response.ok) throw new Error(body.detail || `Story failed (${response.status})`);
      setStory(body as Story); setFrameIndex(0); setPhase('Five-scene story ready');
    } catch (cause) { if (contextRun === runId.current) { setError(String(cause)); setPhase('Failed'); } }
  };

  const selectFrame = (index: number) => {
    if (!story || story.status === 'stale') return;
    setFrameIndex(index);
    const frame = story.frames[index];
    focus(frame.map_state.bbox);
    const layer = frame.map_state.layer_id;
    if (layerIds.has(layer as RevealMode) && layer in props.availableLayers) props.onSetLayer(layer as RevealMode);
  };

  return <section className="agent-panel panel-card" aria-label="AI Earth Investigator">
    <h2>AI Earth Investigator</h2>
    <nav aria-label="Release demo entrances"><a href="/?demo=A">Demo A · NISAR Cached Evidence</a> · <a href="/?demo=B">Demo B · Synthetic Spatial Ranking</a></nav>
    <div className="agent-status"><strong>{agentStatus}</strong>{providerStatus && <strong>{providerStatus}</strong>}<strong>{agentMode === 'real' ? 'Real AI Tool Calling' : 'Deterministic Demo'}</strong><strong>{dataMode === 'fixture' ? 'SIMULATED DATA — NOT NASA OBSERVATIONS' : dataMode === 'cache' ? `NISAR CACHED EVIDENCE · ${cacheStatus}` : `LIVE NISAR DATA · ${liveStatus}`}</strong></div>
    <p>Selected AOI: {props.activeCase?.region_name || 'Choose a case'} · {props.bbox.map((v) => v.toFixed(3)).join(', ')} · {props.polarizationMode}</p>
    <p>Scene pair: {props.activeCase?.default_t0_scene_id || '—'} → {props.activeCase?.default_t1_scene_id || '—'} · Active layer: {props.activeLayer || 'none'}</p>
    <form onSubmit={(event) => void investigate(event)}>
      <label htmlFor="agent-query">Ask about this area</label>
      <textarea id="agent-query" value={query} onChange={(event) => setQuery(event.target.value)} maxLength={1200} rows={2} />
      <label htmlFor="agent-data-mode">Data mode</label>
      <select id="agent-data-mode" value={dataMode} onChange={(event) => { const mode = event.target.value as 'live' | 'cache' | 'fixture'; setDataMode(mode); props.onDataModeChange?.(mode); }}><option value="live">Live NISAR only</option><option value="cache">NISAR Cached Evidence</option><option value="fixture">Synthetic Demo</option></select>
      <label htmlFor="agent-execution-mode">Agent execution</label>
      <select id="agent-execution-mode" value={agentMode} onChange={(event) => setAgentMode(event.target.value as 'real' | 'deterministic')}><option value="deterministic">Deterministic Demo</option><option value="real">Real AI Analysis</option></select>
      <button type="submit" disabled={!props.activeCase || running}>Investigate</button>
      {running && <button type="button" onClick={() => { controller.current?.abort(); void fetch(`/api/agent/cancel/${sessionId}`, { method: 'POST' }).catch(() => {}); if (activityTimer.current !== null) window.clearInterval(activityTimer.current); runId.current++; setRunning(false); setPhase('Cancelled'); }}>Cancel</button>}
    </form>
    <p role="status">{phase}</p>
    {running && liveTrace.some((item) => item.tool === 'investigation_plan') &&
      <div className="agent-plan"><h3>Investigation Plan</h3><ol>{liveTrace.filter((item) => item.tool === 'investigation_plan').at(-1)?.steps?.map((step) =>
        <li key={step.tool}>{step.tool}: {step.status}</li>)}</ol></div>}
    {running && liveTrace.length > 0 && <ol aria-label="Live tool activity">{liveTrace.map((item, index) => <li key={index}>{item.tool}: {item.status}</li>)}</ol>}
    {error && <p role="alert">{error}</p>}
    {result && <div>
      <p><strong>{result.agent_mode === 'real' ? `Real AI Analysis · ${result.model_provider || 'local'} · ${(result.model_name || 'model').split(/[\\/]/).pop()}` : 'Deterministic Demo'}</strong></p>
      <strong>{result.data_notice}</strong>
      {running && <p>Showing the previous completed result while the new request runs.</p>}
      {result.investigation_plan && <div className="agent-plan"><h3>Investigation Plan</h3><ol>{result.investigation_plan.map((step) =>
        <li key={step.tool}>{step.tool}: {step.status}</li>)}</ol></div>}
      <p>{result.narrative}</p>
      {result.mode === 'cache' && result.fingerprint_details && <div id="agent-region-fingerprint" className="rank-fingerprint" data-testid="cached-radar-fingerprint">
        <h3>Radar Fingerprint · {result.fingerprint_details.roi_id}</h3>
        <p>HH median signed change: {result.fingerprint_details.hh_delta_median_db?.toFixed(4) ?? 'Unavailable'} dB · HV median signed change: {result.fingerprint_details.hv_delta_median_db?.toFixed(4) ?? 'Unavailable'} dB.</p>
        <p>{result.fingerprint_details.t0_acquisition_utc} → {result.fingerprint_details.t1_acquisition_utc} · {result.fingerprint_details.valid_pixel_count.toLocaleString()} valid pixels.</p>
        <p>Evidence {result.fingerprint_details.evidence_id} · {result.fingerprint_details.quality_status} · {result.fingerprint_details.method}. Two observation dates only.</p>
        <p>Definition: {result.fingerprint_details.measurement_definition}. This is an observed backscatter difference, not a confirmed significant disturbance.</p>
        <div className="agent-distribution" aria-label="Cached change distribution">
          {(['HH', 'HV'] as const).map((pol) => <p key={pol}>{pol} pixelwise Δ p10–p90: {result.fingerprint_details!.distribution[pol].p10_delta_db?.toFixed(4) ?? '—'} to {result.fingerprint_details!.distribution[pol].p90_delta_db?.toFixed(4) ?? '—'} dB · median |Δ|: {result.fingerprint_details!.distribution[pol].median_abs_change_db?.toFixed(4) ?? '—'} dB · positive: {result.fingerprint_details!.distribution[pol].positive_change_fraction !== null ? (result.fingerprint_details!.distribution[pol].positive_change_fraction! * 100).toFixed(1) : '—'}%.</p>)}
        </div>
        <p>Significance: {result.fingerprint_details.significance_status} · Stable control: {result.fingerprint_details.stable_control_status}. Source raster review is still needed for spatial interpretation.</p>
        <button type="button" onClick={() => void openEvidence(result.fingerprint_details!.evidence_id)}>Inspect Evidence</button>
      </div>}
      {result.ranked_regions && <div className="ranked-regions"><h3>Ranked Change Regions</h3>
        {result.ranked_regions.map((region) => <article key={region.region_id} className={activeRegion?.region_id === region.region_id ? 'rank-card active' : 'rank-card'}>
          <strong>#{region.rank} · {region.region_id}</strong>
          <p>Median |Δ{region.polarization}| {region.median_abs_change_db.toFixed(3)} dB · {region.pixel_count} connected pixels · {region.valid_pixel_percentage.toFixed(1)}% valid · ≈{region.area_km2_approx.toFixed(3)} km²</p>
          <small>{region.observation_times.join(' → ')} · {region.crs} · {region.quality_status || 'Quality unknown'}</small><br />
          <button type="button" onClick={() => selectRegion(region)}>Focus on Map</button>
          <button type="button" onClick={() => { selectRegion(region); window.requestAnimationFrame(() => document.getElementById('agent-region-fingerprint')?.scrollIntoView?.({ block: 'nearest' })); }}>View Radar Fingerprint</button>
          <button type="button" onClick={() => void openEvidence(region.evidence_ids[0])}>Inspect Evidence</button>
        </article>)}
        {result.ranked_regions.length > 1 && <button type="button" onClick={() => void compareRegions()}>Compare Regions</button>}
        {comparison && <p>{comparison}</p>}
      </div>}
      {activeRegion && <div id="agent-region-fingerprint" className="rank-fingerprint"><h3>Radar Fingerprint · Region #{activeRegion.rank}</h3>
        <p>Pairwise {activeRegion.polarization} median signed change: {activeRegion.median_signed_change_db.toFixed(3)} dB; median magnitude: {activeRegion.median_abs_change_db.toFixed(3)} dB.</p>
        <p>Only two comparison dates are available. No additional time points are inferred.</p>
      </div>}
      {evidenceCard && result.mode === 'cache' && <div className="agent-evidence-card" data-testid="cached-evidence-card"><h3>Evidence {String(evidenceCard.evidence_id)}</h3>
        <p>Source status: Internally Consistent Cache · Provenance Pending · Verified Source: No</p>
        <p>AOI: {String(evidenceCard.roi_id)} · Quality: {String(evidenceCard.quality_status)} · Valid pixels: {String(evidenceCard.valid_pixel_count)}</p>
        <p>Scene pair: {(evidenceCard.scene_ids as string[] || []).join(' → ')}</p>
        <p>Observation dates: {String((evidenceCard.processing_metadata as Record<string, unknown> | undefined)?.t0_acquisition_utc || 'unknown')} → {String((evidenceCard.processing_metadata as Record<string, unknown> | undefined)?.t1_acquisition_utc || 'unknown')} · Polarization: {(evidenceCard.polarizations as string[] || []).join(', ')}</p>
        <p>Observed: HH {result.fingerprint_details?.hh_delta_median_db?.toFixed(4) ?? '—'} dB · HV {result.fingerprint_details?.hv_delta_median_db?.toFixed(4) ?? '—'} dB. Recorded mask: {result.fingerprint_details?.mask_rule || 'unavailable'}.</p>
        <p>Method: {String(evidenceCard.algorithm_version)} · Limitations: {(evidenceCard.limitations as string[] || []).join(', ')}</p>
      </div>}
      {evidenceCard && result.mode !== 'cache' && <div className="agent-evidence-card"><h3>Evidence {String(evidenceCard.evidence_id)}</h3>
        <p>Source: {(evidenceCard.scene_ids as string[] || []).join(' · ')} · {(evidenceCard.observation_times as string[] || []).join(' → ')}</p>
        <p>Method: {String(evidenceCard.method)} · Polarization: {String(evidenceCard.polarization)} · CRS: {String(evidenceCard.crs)}</p>
        <p>Quality: {String(evidenceCard.quality_status || 'unknown')}{Array.isArray(evidenceCard.scene_versions) && evidenceCard.scene_versions.length > 0 ? ` · Product versions: ${evidenceCard.scene_versions.join(' → ')}` : ''}</p>
        {Boolean(evidenceCard.parent_evidence_id) && <p>Parent Evidence: {String(evidenceCard.parent_evidence_id)} · Change SHA-256: {String(evidenceCard.change_sha256 || 'unavailable')}</p>}
        <p>Data: {String(evidenceCard.data_kind)} · {(evidenceCard.limitations as string[] || []).join(' ')}</p>
      </div>}
      <h3>Observed</h3>
      {(result.scientific_assessment?.observed || result.claims.map((claim) => ({ statement: claim.statement, evidence_ids: [claim.evidence_id] }))).map((claim, index) =>
        <button key={index} type="button" className="agent-claim" onClick={() => {
          void openEvidence(claim.evidence_ids[0]);
          window.requestAnimationFrame(() => document.getElementById('agent-region-fingerprint')?.scrollIntoView?.({ block: 'nearest' }));
        }}>{claim.statement} [{claim.evidence_ids[0]}]</button>)}
      {result.scientific_assessment && <><h3>Inferred</h3><ul>{result.scientific_assessment.inferred.map((item, index) => <li key={index}>{item.statement}</li>)}</ul></>}
      <h3>Unknown</h3><ul>{(result.scientific_assessment?.unknown || result.unknowns).map((item, index) => <li key={index}>{item}</li>)}</ul>
      {result.scientific_assessment && <><h3>Scientific Limitations</h3><ul>{result.scientific_assessment.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul>
        <p>Analysis version: {result.scientific_assessment.analysis_version} · {result.scientific_assessment.data_kind}</p>
        <h3>Next steps</h3><ul>{result.scientific_assessment.next_steps.map((item, index) => <li key={index}>{item}</li>)}</ul></>}
      <div className="agent-actions">
        {result.map_actions.map((action, index) => <button key={index} type="button" onClick={() => dispatch(action, result.evidence_ids[0])}>{action.type}</button>)}
        <label htmlFor="story-locale">Story language</label><select id="story-locale" value={storyLocale} onChange={(event) => setStoryLocale(event.target.value as 'en' | 'zh-TW')}><option value="en">English</option><option value="zh-TW">繁體中文</option></select>
        <label htmlFor="story-audience">Story mode</label><select id="story-audience" value={storyAudience} onChange={(event) => setStoryAudience(event.target.value as 'public' | 'scientific')}><option value="public">Public</option><option value="scientific">Scientific</option></select>
        <button type="button" onClick={() => void buildStory()}>Generate story</button>
      </div>
      <details><summary>Tool execution trace</summary><ol>{result.trace.map((item, index) => <li key={index}>{item.tool}: {item.status}</li>)}</ol></details>
    </div>}
    {story && <div className="agent-story">
      <h3>Earth Change Story {story.status === 'stale' ? '(Stale)' : ''}</h3>
      {story.data_notice && <strong>{story.data_notice}</strong>}
      <nav aria-label="Story scenes">{story.frames.map((frame, index) => <button key={index} type="button" disabled={story.status === 'stale'} aria-current={index === frameIndex ? 'step' : undefined} onClick={() => selectFrame(index)}>{index + 1}. {frame.title}</button>)}</nav>
      <p>{story.frames[frameIndex].narrative}</p>
      <p>Evidence: {story.frames[frameIndex].evidence_ids.join(', ')} · Source scenes: {story.frames[frameIndex].source.join(' → ')}</p>
      <button type="button" onClick={() => void openEvidence(story.evidence_ids[0])}>View evidence</button>
      <button type="button" onClick={() => { const blob = new Blob([JSON.stringify(story, null, 2)], { type: 'application/json' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `${story.story_id}.json`; link.click(); URL.revokeObjectURL(url); }}>Export JSON</button>
    </div>}
  </section>;
};
