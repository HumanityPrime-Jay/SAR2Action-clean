import React, { useEffect, useRef, useState } from 'react';
import {
  fetchCases,
  fetchEvidenceRecord,
  requestRadarFingerprint,
  ScienceApiError,
} from './api/client';
import { RadarMapCanvas } from './components/RadarMapCanvas';
import { AgentPanel } from './components/AgentPanel';
import {
  ApiScienceError,
  CaseSummary,
  DeterministicClaim,
  EvidenceRecord,
  PolarizationChannel,
  PolarizationFingerprintDetail,
  RadarFingerprintResponse,
  RevealMode,
} from './types/api';

const REVEAL_BUTTONS: { mode: RevealMode; label: string }[] = [
  { mode: 't0_hh', label: 'T0 HH' },
  { mode: 't1_hh', label: 'T1 HH' },
  { mode: 'swipe_hh', label: 'Swipe T0/T1 (HH)' },
  { mode: 't0_hv', label: 'T0 HV' },
  { mode: 't1_hv', label: 'T1 HV' },
  { mode: 'swipe_hv', label: 'Swipe T0/T1 (HV)' },
  { mode: 'delta_hh', label: 'Delta HH' },
  { mode: 'delta_hv', label: 'Delta HV' },
  { mode: 'magnitude_hh', label: 'Abs |ΔHH|' },
  { mode: 'magnitude_hv', label: 'Abs |ΔHV|' },
  { mode: 'combined_change', label: 'Combined Radar Change' },
  { mode: 'validity_mask', label: 'Validity Mask' },
];

const releaseDemo = new URLSearchParams(window.location.search).get('demo')?.toUpperCase();
const initialDataMode = releaseDemo === 'A' ? 'cache' : releaseDemo === 'B' ? 'fixture' : 'live';

function formatSignedDb(val: number | null | undefined): string {
  if (val === null || val === undefined || Number.isNaN(val)) return '—';
  const prefix = val > 0 ? '+' : '';
  return `${prefix}${val.toFixed(4)} dB`;
}

function formatDb(val: number | null | undefined): string {
  if (val === null || val === undefined || Number.isNaN(val)) return '—';
  return `${val.toFixed(4)} dB`;
}

function formatDbComposite(val: number | null | undefined): string {
  if (val === null || val === undefined || Number.isNaN(val)) return '—';
  return `${val.toFixed(4)} dB composite`;
}

export const App: React.FC = () => {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [activeCaseId, setActiveCaseId] = useState<string>('');
  const [selectedAoiId, setSelectedAoiId] = useState<string | undefined>(undefined);
  const [selectedBbox, setSelectedBbox] = useState<[number, number, number, number]>([
    105.28, -3.28, 105.48, -3.08,
  ]);
  const [polFilter, setPolFilter] = useState<'DUAL' | 'HH_ONLY'>('DUAL');
  const [revealMode, setRevealMode] = useState<RevealMode>('delta_hv');

  const [fingerprintData, setFingerprintData] = useState<RadarFingerprintResponse | null>(null);
  const [inspectedEvidence, setInspectedEvidence] = useState<EvidenceRecord | null>(null);
  const [selectedClaim, setSelectedClaim] = useState<DeterministicClaim | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [apiError, setApiError] = useState<ApiScienceError | null>(null);
  const [agentFocusBbox, setAgentFocusBbox] = useState<[number, number, number, number] | null>(null);
  const [agentDataMode, setAgentDataMode] = useState<'live' | 'cache' | 'fixture'>(initialDataMode);
  const [agentRankedRegions, setAgentRankedRegions] = useState<{ bbox_wgs84: [number, number, number, number]; rank: number }[]>([]);
  const fingerprintRequestId = useRef(0);

  const activeCase = cases.find((c) => c.case_id === activeCaseId) || null;

  useEffect(() => { setAgentFocusBbox(null); }, [selectedBbox, activeCaseId]);

  useEffect(() => {
    let mounted = true;
    fetchCases()
      .then((loadedCases) => {
        if (!mounted || loadedCases.length === 0) return;
        setCases(loadedCases);
        // Prefer the first case whose local HDF5 files are ready on disk
        const defaultCase =
          (releaseDemo === 'A' ? loadedCases.find((c) => c.case_id === 'case-flagship-oki-f2') : undefined) ||
          loadedCases.find((c) => c.local_hdf5_ready) || loadedCases[0];
        setActiveCaseId(defaultCase.case_id);
        const firstPreset = (releaseDemo === 'A'
          ? defaultCase.preset_aois.find((aoi) => aoi.aoi_id === 'AOI-OKI-04') : undefined) || defaultCase.preset_aois[0];
        const initBbox = firstPreset
          ? firstPreset.bbox_wgs84
          : defaultCase.default_aoi_bbox_wgs84;
        setSelectedAoiId(firstPreset?.aoi_id);
        setSelectedBbox(initBbox);
        void runFingerprint(
          defaultCase.case_id,
          initBbox,
          firstPreset?.aoi_id,
          'DUAL'
        );
      })
      .catch((err) => {
        if (!mounted) return;
        if (err instanceof ScienceApiError) {
          setApiError(err.scienceError);
        } else {
          setApiError({
            error_code: 'NETWORK_ERROR',
            message: String(err),
            science_status: 'INSUFFICIENT_EVIDENCE',
          });
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  const runFingerprint = async (
    caseId: string,
    bbox: [number, number, number, number],
    aoiId?: string,
    polarizationMode: 'DUAL' | 'HH_ONLY' = polFilter
  ) => {
    const requestId = ++fingerprintRequestId.current;
    setLoading(true);
    setApiError(null);
    setFingerprintData(null);
    setInspectedEvidence(null);
    setSelectedClaim(null);
    try {
      const requestedPols: PolarizationChannel[] | undefined =
        polarizationMode === 'HH_ONLY' ? ['HH'] : undefined;
      const result = await requestRadarFingerprint({
        case_id: caseId,
        aoi_id: aoiId,
        aoi_bbox_wgs84: bbox,
        requested_polarizations: requestedPols,
      });
      if (requestId !== fingerprintRequestId.current) return;
      setFingerprintData(result);
      setInspectedEvidence(result.evidence_record);
      if (result.claims.length > 0) {
        setSelectedClaim(result.claims[0]);
      } else {
        setSelectedClaim(null);
      }
      if (polarizationMode === 'HH_ONLY' && revealMode.includes('hv')) {
        setRevealMode('delta_hh');
      }
    } catch (err) {
      if (requestId !== fingerprintRequestId.current) return;
      // Never leave a previous AOI's statistics on screen after a refusal/failure:
      // stale numbers could be misread as belonging to the refused AOI.
      setFingerprintData(null);
      setInspectedEvidence(null);
      setSelectedClaim(null);
      if (err instanceof ScienceApiError) {
        setApiError(err.scienceError);
      } else {
        setApiError({
          error_code: 'ANALYSIS_ERROR',
          message: String(err),
          science_status: 'INSUFFICIENT_EVIDENCE',
        });
      }
    } finally {
      if (requestId === fingerprintRequestId.current) setLoading(false);
    }
  };

  const handleCaseChange = (newCaseId: string) => {
    setActiveCaseId(newCaseId);
    const targetCase = cases.find((c) => c.case_id === newCaseId);
    if (!targetCase) return;
    const preset = targetCase.preset_aois[0];
    const bbox = preset ? preset.bbox_wgs84 : targetCase.default_aoi_bbox_wgs84;
    setSelectedAoiId(preset?.aoi_id);
    setSelectedBbox(bbox);
    void runFingerprint(newCaseId, bbox, preset?.aoi_id, polFilter);
  };

  const handleSelectPresetAoi = (presetId: string) => {
    if (!activeCase) return;
    const preset = activeCase.preset_aois.find((p) => p.aoi_id === presetId);
    if (!preset) return;
    setSelectedAoiId(preset.aoi_id);
    setSelectedBbox(preset.bbox_wgs84);
    void runFingerprint(activeCase.case_id, preset.bbox_wgs84, preset.aoi_id, polFilter);
  };

  const handleClaimClick = async (claim: DeterministicClaim) => {
    setSelectedClaim(claim);
    if (claim.target_layer_type) {
      setRevealMode(claim.target_layer_type as RevealMode);
    }
    try {
      const record = await fetchEvidenceRecord(claim.evidence_id);
      setInspectedEvidence(record);
    } catch {
      // Keep existing record if already loaded
    }
  };

  const renderPolarizationCard = (detail: PolarizationFingerprintDetail) => {
    const pol = detail.polarization;
    if (!detail.available || detail.status_label === 'Unavailable') {
      return (
        <div
          className="pol-card pol-unavailable"
          data-testid={`pol-card-${pol.toLowerCase()}`}
        >
          <div className="pol-card-header">
            <span className="pol-badge">{pol} Polarization</span>
            <span
              className="status-pill status-unavailable"
              data-testid={`pol-status-${pol.toLowerCase()}`}
            >
              Unavailable
            </span>
          </div>
          <p className="pol-unavailable-note">
            {pol} polarization is unavailable for this request. Per Science Contract Section 6,
            missing polarizations are explicitly marked <strong>Unavailable</strong> and never
            replaced with synthetic zero.
          </p>
        </div>
      );
    }

    const dist = detail.delta_distribution_db;
    return (
      <div className="pol-card" data-testid={`pol-card-${pol.toLowerCase()}`}>
        <div className="pol-card-header">
          <span className="pol-badge">{pol} Polarization ({pol === 'HH' ? 'HHHH' : 'HVHV'})</span>
          <span
            className="status-pill status-available"
            data-testid={`pol-status-${pol.toLowerCase()}`}
          >
            Available
          </span>
        </div>
        <div className="pol-metrics-grid">
          <div className="metric-cell">
            <span className="metric-label">Median T0 ({pol})</span>
            <strong data-testid={`median-t0-${pol.toLowerCase()}`}>
              {formatDb(detail.t0_median_db)}
            </strong>
          </div>
          <div className="metric-cell">
            <span className="metric-label">Median T1 ({pol})</span>
            <strong data-testid={`median-t1-${pol.toLowerCase()}`}>
              {formatDb(detail.t1_median_db)}
            </strong>
          </div>
          <div className="metric-cell highlight-delta">
            <span className="metric-label">Median Signed Δ{pol}</span>
            <strong data-testid={`median-delta-${pol.toLowerCase()}`}>
              {formatSignedDb(detail.delta_median_db)}
            </strong>
          </div>
          <div className="metric-cell">
            <span className="metric-label">Median |Δ{pol}|</span>
            <strong data-testid={`median-mag-${pol.toLowerCase()}`}>
              {formatDb(detail.magnitude_median_db)}
            </strong>
          </div>
        </div>
        {dist && (
          <div
            className="pol-distribution-bar"
            data-testid={`delta-dist-${pol.toLowerCase()}`}
          >
            <div className="dist-title">
              Signed Δ{pol} Distribution (p10 / p25 / p50 / p75 / p90):
            </div>
            <div className="dist-values">
              <span>p10: {formatSignedDb(dist.p10)}</span>
              <span>p25: {formatSignedDb(dist.p25)}</span>
              <span>p50: {formatSignedDb(dist.p50)}</span>
              <span>p75: {formatSignedDb(dist.p75)}</span>
              <span>p90: {formatSignedDb(dist.p90)}</span>
            </div>
            <div className="dist-fractions">
              <span>
                Positive (Δ &gt; 0):{' '}
                {((detail.positive_change_fraction || 0) * 100).toFixed(1)}%
              </span>
              <span>
                Negative (Δ &lt; 0):{' '}
                {((detail.negative_change_fraction || 0) * 100).toFixed(1)}%
              </span>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="sar2action-app">
      {/* Top Navigation & Case Header */}
      <header className="app-header">
        <div className="brand-block">
          <span className="mission-pill">NISAR L2 GCOV • DETERMINISTIC SCIENCE SLICE</span>
          <h1>SAR2Action — Earth Change Intelligence</h1>
          <p className="brand-subtitle">
            Every quantitative claim leads back to verifiable radar evidence.
          </p>
          <a href="/studio" className="brand-subtitle">Open Investigation Studio →</a>
        </div>

        <div className="case-selector-block">
          <label htmlFor="case-select">Active Scientific Case:</label>
          <select
            id="case-select"
            data-testid="case-select"
            value={activeCaseId}
            onChange={(e) => handleCaseChange(e.target.value)}
          >
            {cases.map((c) => (
              <option key={c.case_id} value={c.case_id}>
                [{c.case_role}] {c.title}
              </option>
            ))}
          </select>
        </div>
      </header>

      {/* Scene Pair Provenance Banner */}
      {activeCase && (
        <section className="scene-pair-banner" data-testid="scene-pair-banner">
          <div className="scene-item">
            <span className="scene-epoch-tag">T0 Observation</span>
            <code>{activeCase.default_t0_scene_id}</code>
            <span className="scene-time">{activeCase.t0_acquisition_utc}</span>
          </div>
          <div className="scene-arrow">→</div>
          <div className="scene-item">
            <span className="scene-epoch-tag">T1 Observation</span>
            <code>{activeCase.default_t1_scene_id}</code>
            <span className="scene-time">{activeCase.t1_acquisition_utc}</span>
          </div>
          <div className="scene-meta-tags">
            <span>Orbit: {activeCase.orbit_pass_direction} ({activeCase.look_direction})</span>
            <span>CRID: {activeCase.crid} ({activeCase.product_maturity})</span>
            <span>Full Frame: {activeCase.is_full_frame ? 'YES' : 'PARTIAL'}</span>
            {activeCase.t0_orbit_pointing_fidelity && activeCase.t1_orbit_pointing_fidelity && (
              <span title="Official NISAR GCOV filename token after CRID (internal HDF5 orbitType=MOE)">
                Pointing Fidelity: T0={activeCase.t0_orbit_pointing_fidelity} / T1={activeCase.t1_orbit_pointing_fidelity}
              </span>
            )}
            <span>RFI QA: {activeCase.rfi_comparison_status || 'UNRELIABLE_METADATA'}</span>
          </div>
        </section>
      )}

      {/* Mandatory Science Status & Non-Attribution Banner (Phase 3C Hardening) */}
      <section className="science-status-guardrail-bar" data-testid="science-status-guardrail-bar">
        <div className="guardrail-badges">
          <span className="status-pill status-provisional" data-testid="badge-provisional">
            PROVISIONAL
          </span>
          <span className="status-pill status-cause-undetermined" data-testid="badge-cause-not-determined">
            CAUSE NOT DETERMINED
          </span>
          <span className="status-pill status-demo-mode" data-testid="badge-demo-mode">
            {agentDataMode === 'fixture' ? 'SIMULATED DATA — NOT NASA OBSERVATIONS' : agentDataMode === 'cache' ? 'NISAR CACHED EVIDENCE · PROVENANCE NOT VERIFIED' : `DEMO_MODE: ${fingerprintData?.demo_mode || 'LIVE'}${fingerprintData?.cache_hit ? ' (CACHED REAL NISAR)' : ''}`}
          </span>
        </div>
        <div className="guardrail-sentences" data-testid="non-attribution-statement">
          {agentDataMode === 'fixture' ? <strong>The investigator is showing synthetic spatial ranking. Its values and story are not NASA observations.</strong> : agentDataMode === 'cache' ? <strong>{fingerprintData?.cache_hit ? 'B-team cached fingerprint loaded; external provenance review remains pending. This is not live HDF5 computation.' : 'Cached evidence for this AOI is unavailable. No synthetic result is substituted.'}</strong> : fingerprintData ? <>
            <span>NISAR-derived radar analysis: {fingerprintData.t0_acquisition_utc} → {fingerprintData.t1_acquisition_utc}.</span>{' '}
            <strong>Radar change alone does not establish the physical cause.</strong>
          </> : <strong>No verified local radar analysis is loaded for the selected AOI.</strong>}
        </div>
      </section>

      {/* Experience 1: Radar Reveal Layer Switcher */}
      <section className="reveal-controls-bar" aria-label="Radar Reveal Layer Modes">
        <div className="reveal-bar-label">① RADAR REVEAL LAYER:</div>
        <div className="reveal-buttons-group" data-testid="reveal-buttons-group">
          {REVEAL_BUTTONS.map((btn) => {
            const disabled =
              polFilter === 'HH_ONLY' &&
              (btn.mode.includes('hv') || btn.mode === 'combined_change');
            return (
              <button
                key={btn.mode}
                type="button"
                disabled={disabled}
                data-testid={`layer-btn-${btn.mode}`}
                className={`btn-layer ${revealMode === btn.mode ? 'active' : ''}`}
                onClick={() => setRevealMode(btn.mode)}
              >
                {btn.label}
              </button>
            );
          })}
        </div>
      </section>

      {/* API / Science Error Banner (Explicit Error State Propagation) */}
      {agentDataMode === 'live' && apiError && (
        <div className="science-error-banner" role="alert" data-testid="science-error-banner">
          <div className="error-header">
            <strong>SCIENCE GATE REFUSAL [{apiError.error_code}]</strong>
            <span className="quality-badge status-insufficient">
              {apiError.science_status}
            </span>
          </div>
          <p>{apiError.message}</p>
        </div>
      )}

      {/* Main Split Workspace: Left = 2D MapLibre & AOI Controls; Right = Fingerprint, Epistemic Panel & Evidence Trail */}
      <main className="main-workspace">
        <div className="left-column">
          <RadarMapCanvas
            activeCase={activeCase}
            revealMode={revealMode}
            layers={agentDataMode === 'fixture' ? {} : fingerprintData?.layers || {}}
            selectedBbox={selectedBbox}
            agentFocusBbox={agentFocusBbox}
            rankedRegions={agentRankedRegions}
            onSelectBbox={(bbox) => {
              setSelectedAoiId(undefined);
              setSelectedBbox(bbox);
              if (activeCase) {
                void runFingerprint(activeCase.case_id, bbox, undefined, polFilter);
              }
            }}
          />

          {/* AOI & Polarization Query Controls */}
          <div className="aoi-control-panel" data-testid="aoi-control-panel">
            <h3>AOI Selection & Radar Fingerprint Request</h3>
            <div className="preset-aois-row">
              <span>Preset AOIs:</span>
              {activeCase?.preset_aois.map((preset) => (
                <button
                  key={preset.aoi_id}
                  type="button"
                  data-testid={`preset-aoi-${preset.aoi_id}`}
                  className={`btn-preset ${selectedAoiId === preset.aoi_id ? 'active' : ''}`}
                  onClick={() => handleSelectPresetAoi(preset.aoi_id)}
                >
                  {preset.name}
                </button>
              ))}
              <button
                type="button"
                data-testid="btn-test-outside-aoi"
                className="btn-preset btn-outside-test"
                onClick={() => {
                  const outsideBbox: [number, number, number, number] = [100.1, 0.1, 100.2, 0.2];
                  setSelectedAoiId('AOI-OUTSIDE-TEST');
                  setSelectedBbox(outsideBbox);
                  if (activeCase) {
                    void runFingerprint(activeCase.case_id, outsideBbox, 'AOI-OUTSIDE-TEST', polFilter);
                  }
                }}
              >
                Test Outside-Coverage AOI (Gate Refusal)
              </button>
            </div>

            <div className="polarization-request-row">
              <div className="pol-toggle-group">
                <span>Polarization Mode:</span>
                <button
                  type="button"
                  data-testid="pol-mode-dual"
                  className={`btn-pol-mode ${polFilter === 'DUAL' ? 'active' : ''}`}
                  onClick={() => {
                    setPolFilter('DUAL');
                    if (activeCase) {
                      void runFingerprint(activeCase.case_id, selectedBbox, selectedAoiId, 'DUAL');
                    }
                  }}
                >
                  HH + HV (Dual-Pol)
                </button>
                <button
                  type="button"
                  data-testid="pol-mode-hh-only"
                  className={`btn-pol-mode ${polFilter === 'HH_ONLY' ? 'active' : ''}`}
                  onClick={() => {
                    setPolFilter('HH_ONLY');
                    if (activeCase) {
                      void runFingerprint(activeCase.case_id, selectedBbox, selectedAoiId, 'HH_ONLY');
                    }
                  }}
                >
                  HH Only (Verify Missing HV Handling)
                </button>
              </div>

              <button
                type="button"
                data-testid="btn-request-fingerprint"
                className="btn-primary-fingerprint"
                disabled={loading || !activeCase}
                onClick={() => {
                  if (activeCase) {
                    void runFingerprint(activeCase.case_id, selectedBbox, selectedAoiId, polFilter);
                  }
                }}
              >
                {loading ? 'Computing Windowed HDF5 Analysis...' : 'Request Radar Fingerprint'}
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Experience 2 (Radar Fingerprint), Section 3.4 (What We Know / Don't Know), Section 3.5 (Claim-to-Evidence) */}
        <div className="right-column">
          {agentDataMode === 'live' && fingerprintData && (
            <>
              {/* Section 3.3: Radar Fingerprint Panel */}
              <section id="fingerprint-panel"
                className="panel-card fingerprint-panel"
                data-testid="radar-fingerprint-panel"
              >
                <div className="panel-header">
                  <h2>② Radar Fingerprint ({fingerprintData.roi_id})</h2>
                  <span
                    className={`quality-badge status-${fingerprintData.quality_status.toLowerCase()}`}
                    data-testid="fingerprint-quality-status"
                  >
                    {fingerprintData.quality_status}
                  </span>
                </div>

                <div className="fingerprint-summary-strip">
                  <div>
                    <span className="strip-label">Evidence ID</span>
                    <strong data-testid="fingerprint-evidence-id">
                      {fingerprintData.evidence_id}
                    </strong>
                  </div>
                  <div>
                    <span className="strip-label">Valid Pixels (10 m)</span>
                    <strong data-testid="fingerprint-valid-pixels">
                      {fingerprintData.valid_pixel_count.toLocaleString()}
                    </strong>
                  </div>
                  <div>
                    <span className="strip-label">Valid Area</span>
                    <strong data-testid="fingerprint-valid-area">
                      {fingerprintData.valid_area_km2.toFixed(3)} km² (
                      {fingerprintData.valid_area_ha.toLocaleString()} ha)
                    </strong>
                  </div>
                  <div>
                    <span className="strip-label">Missing / Invalid</span>
                    <strong data-testid="fingerprint-missing-fraction">
                      {(fingerprintData.missing_invalid_fraction * 100).toFixed(2)}%
                    </strong>
                  </div>
                  <div>
                    <span className="strip-label">AOI Selection</span>
                    <strong data-testid="fingerprint-selection-method">
                      {fingerprintData.selection_method || 'PREDEFINED_GEOGRAPHIC_AOI'}
                    </strong>
                  </div>
                </div>

                <div className="fingerprint-dates-row">
                  <span>
                    <strong>T0:</strong> {fingerprintData.t0_acquisition_utc}
                  </span>
                  <span>
                    <strong>T1:</strong> {fingerprintData.t1_acquisition_utc}
                  </span>
                  <span>
                    <strong>Available Polarizations:</strong>{' '}
                    {fingerprintData.available_polarizations.join(', ')}
                  </span>
                </div>

                <div className="pol-cards-container">
                  {renderPolarizationCard(fingerprintData.hh_detail)}
                  {renderPolarizationCard(fingerprintData.hv_detail)}
                </div>

                {fingerprintData.combined_radar_change_detail && (
                  <div
                    className="combined-change-box"
                    data-testid="combined-change-summary"
                  >
                    <div className="combined-header">
                      <strong>
                        {fingerprintData.combined_radar_change_detail.metric_name} (|ΔHH| + |ΔHV| —{' '}
                        {fingerprintData.combined_radar_change_detail.unit || 'dB composite'}: custom change magnitude / sum of absolute dB changes)
                      </strong>
                      <span>
                        Median:{' '}
                        {formatDbComposite(
                          fingerprintData.combined_radar_change_detail.stats.median
                        )}{' '}
                        | Mean:{' '}
                        {formatDbComposite(
                          fingerprintData.combined_radar_change_detail.stats.mean
                        )}{' '}
                        | p90:{' '}
                        {formatDbComposite(fingerprintData.combined_radar_change_detail.stats.p90)}
                      </span>
                    </div>
                    <p className="combined-disclaimer-text">
                      {fingerprintData.combined_radar_change_detail.disclaimer}
                    </p>
                  </div>
                )}
              </section>

              {/* Section 3.4: Non-AI What We Observed / What May Explain It / What We Do Not Know */}
              <section
                className="panel-card epistemic-panel"
                data-testid="epistemic-summary-panel"
              >
                <h2>③ What We Know / What We Don&apos;t Know (Deterministic Epistemic Guardrails)</h2>
                <div className="epistemic-grid">
                  <div className="epistemic-box box-observed">
                    <h4>WHAT WE OBSERVED</h4>
                    <ul>
                      {fingerprintData.epistemic_panel.what_we_observed.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="epistemic-box box-explain">
                    <h4>WHAT MAY EXPLAIN IT</h4>
                    <ul>
                      {fingerprintData.epistemic_panel.what_may_explain_it.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="epistemic-box box-unknown">
                    <h4>WHAT WE DO NOT KNOW</h4>
                    <ul>
                      {fingerprintData.epistemic_panel.what_we_do_not_know.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </section>

              {/* Section 3.5: Claim-to-Evidence Interactive Trail & Evidence Record Inspector */}
              <section
                className="panel-card claims-evidence-panel"
                data-testid="claims-evidence-panel"
              >
                <h2>④ Claim-to-Evidence Trail (Click Any Claim to Verify Provenance)</h2>
                <div className="claims-list">
                  {fingerprintData.claims.map((claim) => (
                    <button
                      key={claim.claim_id}
                      type="button"
                      data-testid={`claim-btn-${claim.claim_id}`}
                      className={`claim-card-btn ${
                        selectedClaim?.claim_id === claim.claim_id ? 'selected' : ''
                      }`}
                      onClick={() => void handleClaimClick(claim)}
                    >
                      <span className="claim-evidence-pill">[{claim.evidence_id}]</span>
                      <span className="claim-statement">{claim.statement}</span>
                    </button>
                  ))}
                </div>

                {inspectedEvidence && (
                  <div
                    className="evidence-inspector-drawer"
                    data-testid="evidence-inspector-drawer"
                  >
                    <div className="inspector-header">
                      <h3>
                        Evidence Record Inspector: <code>{inspectedEvidence.evidence_id}</code>
                      </h3>
                      <span className="algo-tag">
                        Algorithm: {inspectedEvidence.algorithm_version}
                      </span>
                    </div>
                    <div className="inspector-meta-grid">
                      <div>
                        <strong>ROI / AOI ID:</strong> {inspectedEvidence.roi_id} (
                        {inspectedEvidence.selection_method || 'PREDEFINED_GEOGRAPHIC_AOI'})
                      </div>
                      <div>
                        <strong>Quality Status:</strong> {inspectedEvidence.quality_status}
                      </div>
                      <div>
                        <strong>Valid Pixels:</strong>{' '}
                        {inspectedEvidence.valid_pixel_count.toLocaleString()} (
                        {(inspectedEvidence.coverage_ratio * 100).toFixed(2)}% coverage)
                      </div>
                      <div>
                        <strong>Calculation Formula:</strong>{' '}
                        <code>
                          {selectedClaim?.calculation_formula ||
                            '10*log10(P_T1) - 10*log10(P_T0) where 0 < mask < 255 and P > 0'}
                        </code>
                      </div>
                      {inspectedEvidence.selection_basis && (
                        <div style={{ gridColumn: '1 / -1' }}>
                          <strong>AOI Selection Provenance:</strong>{' '}
                          <span>{inspectedEvidence.selection_basis}</span>
                        </div>
                      )}
                    </div>
                    <div className="inspector-scenes">
                      <strong>Source NISAR Granules:</strong>
                      <ul>
                        {inspectedEvidence.scene_ids.map((sid) => (
                          <li key={sid}>
                            <code>{sid}</code>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="inspector-limitations">
                      <strong>Mandatory Limitations:</strong>{' '}
                      {inspectedEvidence.limitations.map((lim) => (
                        <span key={lim} className="limitation-tag">
                          {lim}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      </main>
      <AgentPanel
        initialDataMode={initialDataMode}
        initialAgentMode={releaseDemo === 'A' ? 'real' : 'deterministic'}
        activeCase={activeCase}
        bbox={selectedBbox}
        aoiId={selectedAoiId}
        polarizationMode={polFilter}
        currentEvidenceId={fingerprintData?.evidence_id}
        availableLayers={agentDataMode === 'fixture' ? {} : fingerprintData?.layers || {}}
        activeLayer={revealMode}
        onFocusBbox={setAgentFocusBbox}
        onSetLayer={setRevealMode}
        onOpenEvidence={(id) => {
          const claim = fingerprintData?.claims.find((item) => item.evidence_id === id);
          if (claim) void handleClaimClick(claim);
        }}
        onDataModeChange={setAgentDataMode}
        onRankedRegions={setAgentRankedRegions}
      />
    </div>
  );
};
