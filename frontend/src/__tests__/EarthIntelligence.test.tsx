import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LangProvider } from '../i18n';
import { EarthIntelligenceScreen } from '../earth/EarthIntelligenceScreen';
import { earthApi, type ProvenanceMeta } from '../earth/api';

const PROV: ProvenanceMeta = {
  data_status: 'OBSERVED',
  evidence_ids: ['EV-YL-CAND-03'],
  scientific_limitations: ['Typhoon Cause: UNRESOLVED', 'Crop Damage: NOT CONFIRMED'],
  sources: ['Sentinel-1 IW GRD'],
};

function renderWithI18n(ui: React.ReactElement) {
  localStorage.setItem('sar2action.lang', 'en');
  return render(<LangProvider>{ui}</LangProvider>);
}

describe('EarthIntelligenceScreen & 8 Feature Modules', () => {
  beforeEach(() => {
    vi.spyOn(earthApi, 'listEvents').mockResolvedValue({
      events: [
        {
          event_id: 'CHAMPI-YUNLIN-TAIXI',
          event_name: 'Typhoon Champi — Yunlin Taixi Coastal SAR Anomaly',
          event_name_zh: '山陀兒颱風 — 雲林台西海岸 SAR 異常',
          event_type: 'TYPHOON',
          country: 'Taiwan',
          region: 'Yunlin, Taixi',
          center_lon: 120.1945,
          center_lat: 23.7025,
          default_zoom: 12.5,
          aoi_bbox: [120.16, 23.67, 120.23, 23.74],
          aoi_geometry: { type: 'Polygon', coordinates: [] },
          observation_sources: ['Sentinel-1 IW GRD'],
          sensor: 'Sentinel-1',
          polarization: ['VH'],
          acquisition_dates: ['2026-10-10', '2026-10-22'],
          product_versions: ['003610'],
          available_layers: ['sar_delta'],
          change_analysis_status: 'CHANGE_ANALYZED',
          demo_mode: 'COMMITTED_STUDY',
          scientific_qa: {},
          evidence_ids: ['EV-YL-CAND-03'],
          data_provenance: ['committed-study'],
          story_available: true,
          summary: 'Real S1 VH backscatter delta +7.55336 dB on YL-CAND-03.',
          summary_zh: 'YL-CAND-03 實測 VH +7.55336 dB。',
        },
      ],
      supported_event_types: ['TYPHOON', 'FLOOD', 'LANDSLIDE', 'SUBSIDENCE', 'COASTAL_CHANGE', 'AGRICULTURAL_ANOMALY', 'DROUGHT', 'THERMAL'],
      total: 1,
      provenance: PROV,
    });

    vi.spyOn(earthApi, 'getTimeline').mockResolvedValue({
      event_id: 'CHAMPI-YUNLIN-TAIXI',
      field_id: 'YL-CAND-03',
      acquisitions: [
        {
          acquisition_id: 'S1-PRE-01',
          acquisition_time_utc: '2026-10-10T21:51:56Z',
          acquisition_time_local: '2026-10-11 05:51:56 CST',
          date_label: '2026-10-11',
          sensor: 'Sentinel-1',
          polarization: 'VH',
          product_version: '003610',
          source: 'Copernicus',
          qa_status: 'OBSERVED',
          warning_phase: 'PRE_WARNING',
          compatible_with_baseline: true,
          metric_name: 'VH',
          metric_value: -18.21,
          metric_unit: 'dB',
        },
        {
          acquisition_id: 'S1-POST-01',
          acquisition_time_utc: '2026-10-22T21:51:56Z',
          acquisition_time_local: '2026-10-23 05:51:56 CST',
          date_label: '2026-10-23',
          sensor: 'Sentinel-1',
          polarization: 'VH',
          product_version: '003610',
          source: 'Copernicus',
          qa_status: 'OBSERVED',
          warning_phase: 'DURING_TYPHOON_WARNING',
          compatible_with_baseline: true,
          metric_name: 'Delta VH',
          metric_value: 7.55336,
          metric_unit: 'dB',
        },
      ],
      observation_gaps: [
        {
          start_utc: '2026-10-11T00:00:00Z',
          end_utc: '2026-10-22T00:00:00Z',
          gap_days: 11,
          status: 'NO_OBSERVATION',
          note: 'Explicit gap: no Sentinel-1 pass archived.',
        },
      ],
      cross_sensor_warnings: ['Cross-CRID delta between P05023 and P05036 is blocked without calibration.'],
      provenance: PROV,
    });

    vi.spyOn(earthApi, 'getLens').mockImplementation(async (_eid, lens) => ({
      event_id: 'CHAMPI-YUNLIN-TAIXI',
      lens,
      title: `Lens ${lens}`,
      subtitle: 'Strict evidence vs hypothesis separation.',
      no_fake_confidence: true,
      spatial_qa_available: true,
      legend_items: [{ label: 'YL-CAND-03', color: '#fb923c' }],
      features: [
        {
          feature_id: 'YL-CAND-03',
          label: 'YL-CAND-03 (+7.55336 dB)',
          scale: 'PARCEL',
          status: lens === 'HYPOTHESES' ? 'HYPOTHESIS_ACTIVE' : 'OBSERVED',
          explanation: 'Typhoon Cause: UNRESOLVED · Crop Damage: NOT CONFIRMED.',
          metrics: { delta_vh_db: '+7.55336 dB', warning_phase: 'DURING_TYPHOON_WARNING' },
          evidence_ids: ['EV-YL-CAND-03'],
        },
      ],
      provenance: PROV,
    }));

    vi.spyOn(earthApi, 'getFingerprint').mockResolvedValue({
      region_id: 'YL-CAND-03',
      event_id: 'CHAMPI-YUNLIN-TAIXI',
      label: 'YL-CAND-03 Coastal Parcel',
      sensor: 'Sentinel-1 IW GRD',
      polarizations: ['VH'],
      product_version: '003610',
      observation_count: 2,
      vh_temporal_signature: [
        { date: '2026-10-10', vh_db: -18.21, season: 'Autumn' },
        { date: '2026-10-22', vh_db: -10.65664, season: 'Autumn' },
      ],
      hh_hv_signature: 'NOT_AVAILABLE',
      temporal_difference_db: 7.55336,
      seasonal_reference_db: -17.5,
      spatial_heterogeneity: 'NOT_AVAILABLE',
      valid_pixel_ratio: 1.0,
      qa_status: 'OBSERVED',
      missing_evidence: ['HH/HV NISAR cross-pol'],
      feature_vector: { vh_delta: 7.55336 },
      evidence_ids: ['EV-YL-CAND-03'],
    });

    vi.spyOn(earthApi, 'compareFingerprints').mockResolvedValue({
      source: {
        region_id: 'YL-CAND-03',
        event_id: 'CHAMPI-YUNLIN-TAIXI',
        label: 'YL-CAND-03',
        sensor: 'Sentinel-1',
        polarizations: ['VH'],
        product_version: '003610',
        observation_count: 2,
        vh_temporal_signature: [],
        hh_hv_signature: 'NOT_AVAILABLE',
        spatial_heterogeneity: 'NOT_AVAILABLE',
        valid_pixel_ratio: 1.0,
        qa_status: 'OBSERVED',
        missing_evidence: [],
        feature_vector: {},
        evidence_ids: [],
      },
      target: {
        region_id: 'YL-REF-01',
        event_id: 'CHAMPI-YUNLIN-TAIXI',
        label: 'YL-REF-01',
        sensor: 'Sentinel-1',
        polarizations: ['VH'],
        product_version: '003610',
        observation_count: 2,
        vh_temporal_signature: [],
        hh_hv_signature: 'NOT_AVAILABLE',
        spatial_heterogeneity: 'NOT_AVAILABLE',
        valid_pixel_ratio: 1.0,
        qa_status: 'OBSERVED',
        missing_evidence: [],
        feature_vector: {},
        evidence_ids: [],
      },
      comparable: true,
      incompatibility_reasons: [],
      normalized_feature_distance: 0.58,
      temporal_pattern_similarity: 0.42,
      scientific_caution: 'Radar similarity does not prove identical crop damage.',
      provenance: PROV,
    });

    vi.spyOn(earthApi, 'findSimilar').mockResolvedValue({
      query_region_id: 'YL-CAND-03',
      candidates: [
        {
          region_id: 'YL-REF-01',
          label: 'YL-REF-01',
          comparable: true,
          normalized_feature_distance: 0.58,
          temporal_pattern_similarity: 0.42,
          causal_warning: 'Correlation only.',
        },
      ],
      provenance: PROV,
    });

    vi.spyOn(earthApi, 'getArena').mockResolvedValue({
      event_id: 'CHAMPI-YUNLIN-TAIXI',
      field_id: 'YL-CAND-03',
      research_question: 'Did Typhoon Champi cause physical inundation on YL-CAND-03?',
      hypotheses: [
        {
          hypothesis_id: 'H1',
          title: 'Typhoon Inundation / Standing Water',
          description: 'Strong VH increase from wind-roughened standing water.',
          status: 'ACTIVE',
          supporting_evidence: ['VH +7.55336 dB'],
          alternative_explanations: ['Aquaculture pond refill'],
          direct_contradictions: [],
          missing_evidence: ['Cloud-free post-event Sentinel-2'],
          test_outcomes: [],
          available_experiments: [
            {
              experiment_id: 'EXP-1',
              experiment_type: 'temporal_alignment_check',
              tool: 'temporal_alignment_check',
              feasibility: 'EXECUTABLE',
              predicted_outcome: 'Aligns with DURING_TYPHOON_WARNING',
            },
          ],
        },
      ],
      provenance: PROV,
    });

    vi.spyOn(earthApi, 'runExperiment').mockResolvedValue({
      event_id: 'CHAMPI-YUNLIN-TAIXI',
      field_id: 'YL-CAND-03',
      hypothesis_id: 'H1',
      executed: true,
      status: 'COMPLETED',
      experiment_type: 'temporal_alignment_check',
      summary: 'Aligned with 2026-10-23 05:51:56 CST (DURING_TYPHOON_WARNING).',
      metrics: { phase: 'DURING_TYPHOON_WARNING' },
      evidence_ids: ['EV-EXP-1'],
      hypothesis_status_after: 'SUPPORTED_BY_TIMING_STILL_UNRESOLVED',
      evaluation_outcome: 'SUPPORTING',
      provenance: PROV,
    });

    vi.spyOn(earthApi, 'getEvidenceGaps').mockResolvedValue({
      event_id: 'CHAMPI-YUNLIN-TAIXI',
      field_id: 'YL-CAND-03',
      gaps: [
        {
          gap_id: 'GAP-OPT-01',
          title: 'Post-event cloud-free optical check',
          priority: 'HIGH',
          why_missing: 'Cloud cover blocked initial pass',
          research_value: 'Distinguishes aquaculture from crop flooding',
          where_to_find: 'Copernicus Sentinel-2 L2A',
          recommended_action: 'SEARCH_AND_REQUEST_APPROVAL',
        },
      ],
      stage_one_policy: 'STAGE_1_SEARCH_VALIDATE_PLAN_APPROVAL',
      provenance: PROV,
    });

    vi.spyOn(earthApi, 'searchCatalog').mockResolvedValue({
      event_id: 'CHAMPI-YUNLIN-TAIXI',
      product_family: 'Sentinel-2',
      search_executed: true,
      network_status: 'MOCK_OFFLINE',
      scenes: [{ granule_id: 'S2A_20261025' }],
      compatibility_summary: 'Compatible L2A product',
      download_permitted: false,
      provenance: PROV,
    });

    vi.spyOn(earthApi, 'guidedDiscovery').mockResolvedValue({
      query: 'Why did YL-CAND-03 change?',
      user_mode: 'FARMER',
      execution_mode: 'DETERMINISTIC_FALLBACK',
      answer: 'Observed +7.55336 dB VH shift at 2026-10-23 05:51:56 CST; Typhoon Cause remains UNRESOLVED.',
      actions: [
        { action: 'FLY_TO_REGION', params: { lon: 120.1945, lat: 23.7025, zoom: 14 } },
        { action: 'SWITCH_LENS', params: { lens: 'HYPOTHESES' } },
      ],
      validated_actions_count: 2,
      rejected_actions: [],
      facts_used: ['YL-CAND-03 +7.55336 dB'],
      provenance: PROV,
    });

    vi.spyOn(earthApi, 'generateStory').mockResolvedValue({
      story_id: 'STORY-CHAMPI',
      event_id: 'CHAMPI-YUNLIN-TAIXI',
      field_id: 'YL-CAND-03',
      title: 'Typhoon Champi — From Signal to Scientific Decision',
      created_at_utc: '2026-10-25T00:00:00Z',
      user_mode: 'FARMER',
      chapters: [
        {
          chapter_number: 1,
          chapter_code: 'CHAPTER 01 · THE PLACE',
          title: '1. Signal Detection',
          narrative: 'YL-CAND-03 recorded +7.55336 dB.',
          lens: 'OBSERVED',
          camera: { lon: 120.1945, lat: 23.7025, zoom: 13 },
          active_layers: ['vh-change'],
          metrics: [{ delta_vh_db: 7.55336 }],
          evidence_ids: ['EV-YL-CAND-03'],
          limitations: ['Crop Damage: NOT CONFIRMED'],
        },
        {
          chapter_number: 2,
          chapter_code: 'CHAPTER 02 · HYPOTHESES',
          title: '2. Competing Hypotheses',
          narrative: 'Typhoon Cause remains UNRESOLVED.',
          lens: 'HYPOTHESES',
          camera: { lon: 120.1945, lat: 23.7025, zoom: 13.5 },
          active_layers: ['vh-change'],
          metrics: [],
          evidence_ids: ['EV-YL-CAND-03'],
          limitations: ['Crop Damage: NOT CONFIRMED'],
        },
      ],
      provenance: PROV,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders all 8 module tabs and navigates across Reality Lens, Timeline, Fingerprint, Arena, Gaps, Discovery, and Story', async () => {
    renderWithI18n(
      <EarthIntelligenceScreen
        selectedId="YL-CAND-03"
        onSelect={vi.fn()}
        eventId="CHAMPI-YUNLIN-TAIXI"
        onEvent={vi.fn()}
        go={vi.fn()}
        farmer={null}
        onFarmer={vi.fn()}
      />
    );

    // Context badge & Reality Lens default view
    expect(screen.getByText(/CONTEXT: CHAMPI-YUNLIN-TAIXI · YL-CAND-03/)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/YL-CAND-03 \(\+7\.55336 dB\)/)).toBeInTheDocument();
    });

    // Switch Reality Lens tab
    fireEvent.click(screen.getByRole('tab', { name: /B · HYPOTHESES/i }));
    await waitFor(() => {
      expect(earthApi.getLens).toHaveBeenCalledWith('CHAMPI-YUNLIN-TAIXI', 'HYPOTHESES', 'YL-CAND-03', expect.any(AbortSignal));
    });

    // Switch to Earth Memory Timeline
    fireEvent.click(screen.getByRole('tab', { name: 'Earth Memory' }));
    await waitFor(() => {
      expect(screen.getByText(/NO OBSERVATION Gaps/i)).toBeInTheDocument();
      expect(screen.getByText(/Cross-CRID delta between P05023 and P05036/)).toBeInTheDocument();
    });

    // Switch to Fingerprint
    fireEvent.click(screen.getByRole('tab', { name: 'Fingerprint' }));
    await waitFor(() => {
      expect(screen.getAllByText(/NOT_AVAILABLE/).length).toBeGreaterThan(0);
    });

    // Switch to Hypothesis Arena & run experiment
    fireEvent.click(screen.getByRole('tab', { name: 'Hypothesis Arena' }));
    await waitFor(() => {
      expect(screen.getByText(/Strong VH increase from wind-roughened standing water/)).toBeInTheDocument();
    });
    const runBtn = screen.getByRole('button', { name: 'Run Experiment' });
    fireEvent.click(runBtn);
    await waitFor(() => {
      expect(earthApi.runExperiment).toHaveBeenCalled();
    });

    // Switch to Evidence Gaps
    fireEvent.click(screen.getByRole('tab', { name: 'Evidence Gaps' }));
    await waitFor(() => {
      expect(screen.getByText(/Post-event cloud-free optical check/)).toBeInTheDocument();
    });

    // Switch to Story Player
    fireEvent.click(screen.getByRole('tab', { name: 'Story' }));
    fireEvent.click(screen.getByRole('button', { name: 'Generate Story' }));
    await waitFor(() => {
      expect(screen.getByText(/1\. Signal Detection/)).toBeInTheDocument();
    });

    // Guided Discovery Query & AI Map Action
    const input = screen.getByLabelText('Guided discovery query');
    fireEvent.change(input, { target: { value: 'Why did YL-CAND-03 change?' } });
    fireEvent.submit(input.closest('form')!);
    await waitFor(() => {
      expect(screen.getByText(/Typhoon Cause remains UNRESOLVED/)).toBeInTheDocument();
    });
  });
});
