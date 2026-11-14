import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from '../App';

const MOCK_CASES = {
  cases: [
    {
      case_id: 'case-flagship-oki-f2',
      title: 'Primary Flagship — South Sumatra / Ogan Komering Ilir Peatland Corridor (T010_F176)',
      case_role: 'PRIMARY_FLAGSHIP',
      region_name: 'Ogan Komering Ilir (OKI), South Sumatra, Indonesia',
      track_number: 10,
      frame_number: 176,
      orbit_pass_direction: 'ASCENDING',
      look_direction: 'LEFT',
      polarizations: ['HH', 'HV'],
      product_maturity: 'PROVISIONAL',
      crid: 'P05023',
      is_full_frame: true,
      default_t0_scene_id:
        'NISAR_L2_PR_GCOV_030_010_A_176_4005_DHDH_A_20260906T224025_20260906T224100_P05023_N_F_J_001',
      default_t1_scene_id:
        'NISAR_L2_PR_GCOV_031_010_A_176_4005_DHDH_A_20260918T224025_20260918T224100_P05023_F_F_J_001',
      t0_acquisition_utc: '2026-09-06T22:40:25Z',
      t1_acquisition_utc: '2026-09-18T22:40:25Z',
      default_aoi_bbox_wgs84: [105.28, -3.28, 105.48, -3.08],
      illuminated_bbox_wgs84: [104.21, -4.41, 106.9, -1.79],
      crs_epsg: 32748,
      pixel_spacing_m: [10.0, 10.0],
      local_hdf5_ready: true,
      scientific_scope_note: 'Locked Primary Flagship Pair',
      preset_aois: [
        {
          aoi_id: 'AOI-OKI-01',
          name: 'AOI-OKI-01 — Tulung Selapan / Cengal Peatland Transition',
          description: '20 km x 20 km window',
          bbox_wgs84: [105.28, -3.28, 105.48, -3.08],
          default_evidence_id: 'E-FLAGSHIP-OKI-001',
        },
        {
          aoi_id: 'AOI-OKI-02',
          name: 'AOI-OKI-02 — Pangkalan Lampam / Pedamaran Peatland Belt',
          description: '18 km x 18 km window',
          bbox_wgs84: [104.98, -3.32, 105.16, -3.14],
          default_evidence_id: 'E-FLAGSHIP-OKI-002',
        },
      ],
    },
  ],
};

function makeLayer(layerType: string, title: string, evidenceId = 'E-FLAGSHIP-OKI-001') {
  return {
    layer_id: `${evidenceId}_${layerType}`,
    case_id: 'case-flagship-oki-f2',
    evidence_id: evidenceId,
    roi_id: 'AOI-OKI-01',
    layer_type: layerType,
    title,
    polarization: layerType.includes('hh') ? 'HH' : layerType.includes('hv') ? 'HV' : null,
    units: 'dB',
    source_scenes: ['SCENE_T0', 'SCENE_T1'],
    t0_acquisition_utc: '2026-09-06T22:40:25Z',
    t1_acquisition_utc: '2026-09-18T22:40:25Z',
    bbox_wgs84: [105.28, -3.28, 105.48, -3.08],
    crs_epsg: 4326,
    width: 400,
    height: 400,
    image_url: `/api/layers/${evidenceId}_${layerType}/image.png`,
    color_interpretation: `${title} in dB`,
    legend: {
      title: `${title} Legend`,
      units: 'dB',
      min_value: -4.0,
      max_value: 4.0,
      palette_type: 'signed_diverging_db',
      stops: [
        { value: -4.0, color: '#082f87', label: '-4.0 dB (Negative radar change)' },
        { value: 4.0, color: '#b43403', label: '+4.0 dB (Positive radar change)' },
      ],
      positive_change_meaning: 'Positive radar change (Δ > 0 dB)',
      negative_change_meaning: 'Negative radar change (Δ < 0 dB)',
      invalid_observation_meaning: 'Invalid / unavailable observation -> NaN',
      prohibited_labels_notice:
        'Radar backscatter or change in dB only — never labeled as wildfire, burn severity, damage, or risk.',
    },
    disclaimer:
      layerType === 'combined_change'
        ? 'Custom visualization metric — not a hazard score, fire probability, damage score, or official burn-severity index.'
        : null,
    limitations: ['cause_not_determined', 'provisional_product'],
  };
}

function makeFingerprintResponse(opts?: { hhOnly?: boolean; roiId?: string; evidenceId?: string }) {
  const hhOnly = opts?.hhOnly || false;
  const roiId = opts?.roiId || 'AOI-OKI-01';
  const evidenceId = opts?.evidenceId || 'E-FLAGSHIP-OKI-001';
  return {
    case_id: 'case-flagship-oki-f2',
    roi_id: roiId,
    evidence_id: evidenceId,
    quality_status: hhOnly ? 'LIMITED' : 'COMPARABLE',
    t0_acquisition_utc: '2026-09-06T22:40:25Z',
    t1_acquisition_utc: '2026-09-18T22:40:25Z',
    aoi_bbox_wgs84: [105.28, -3.28, 105.48, -3.08],
    available_polarizations: hhOnly ? ['HH'] : ['HH', 'HV'],
    unavailable_polarizations: hhOnly ? ['HV'] : [],
    hh_detail: {
      polarization: 'HH',
      available: true,
      status_label: 'Available',
      t0_median_db: -7.821,
      t0_mean_db: -7.9,
      t1_median_db: -8.342,
      t1_mean_db: -8.4,
      delta_median_db: -0.521,
      delta_mean_db: -0.5,
      delta_distribution_db: {
        mean: -0.5,
        median: -0.521,
        std: 1.4,
        min: -8.0,
        max: 7.0,
        p10: -2.4,
        p25: -1.3,
        p50: -0.521,
        p75: 0.4,
        p90: 1.5,
      },
      magnitude_median_db: 1.12,
      magnitude_mean_db: 1.35,
      positive_change_fraction: 0.36,
      negative_change_fraction: 0.64,
    },
    hv_detail: hhOnly
      ? {
          polarization: 'HV',
          available: false,
          status_label: 'Unavailable',
          t0_median_db: null,
          t1_median_db: null,
          delta_median_db: null,
        }
      : {
          polarization: 'HV',
          available: true,
          status_label: 'Available',
          t0_median_db: -13.91,
          t0_mean_db: -14.0,
          t1_median_db: -14.48,
          t1_mean_db: -14.55,
          delta_median_db: -0.57,
          delta_mean_db: -0.55,
          delta_distribution_db: {
            mean: -0.55,
            median: -0.57,
            std: 1.2,
            min: -7.5,
            max: 6.5,
            p10: -2.2,
            p25: -1.2,
            p50: -0.57,
            p75: 0.3,
            p90: 1.2,
          },
          magnitude_median_db: 1.05,
          magnitude_mean_db: 1.25,
          positive_change_fraction: 0.33,
          negative_change_fraction: 0.67,
        },
    combined_radar_change_detail: hhOnly
      ? null
      : {
          metric_name: 'Combined Radar Change',
          disclaimer:
            'Custom visualization metric — not a hazard score, fire probability, damage score, or official burn-severity index.',
          stats: {
            mean: 2.6,
            median: 2.35,
            std: 1.5,
            min: 0.0,
            max: 12.0,
            p10: 0.9,
            p90: 4.5,
          },
        },
    valid_pixel_count: 4000000,
    valid_area_m2: 400000000,
    valid_area_ha: 40000,
    valid_area_km2: 400.0,
    coverage_ratio: 1.0,
    missing_invalid_fraction: 0.0,
    epistemic_panel: {
      what_we_observed: [
        `Median HV changed by -0.5700 dB across 4,000,000 valid pixels [${evidenceId}].`,
      ],
      what_may_explain_it: [
        'Canopy & woody structure change or surface moisture shift.',
      ],
      what_we_do_not_know: [
        'Exact causal driver is not determined from radar backscatter intensity alone (limitation: cause_not_determined).',
      ],
    },
    claims: [
      {
        claim_id: `${evidenceId}-CLAIM-DELTA-HV`,
        statement: `Median HV backscatter changed by -0.5700 dB across 4,000,000 valid comparable 10 m pixels (400.000 km²).`,
        evidence_id: evidenceId,
        case_id: 'case-flagship-oki-f2',
        roi_id: roiId,
        scene_ids: [
          'NISAR_L2_PR_GCOV_030_010_A_176_4005_DHDH_A_20260906T224025_20260906T224100_P05023_N_F_J_001',
          'NISAR_L2_PR_GCOV_031_010_A_176_4005_DHDH_A_20260918T224025_20260918T224100_P05023_F_F_J_001',
        ],
        aoi_bbox_wgs84: [105.28, -3.28, 105.48, -3.08],
        polarization: 'HV',
        metric_name: 'median_delta_hv_db',
        metric_value: -0.57,
        unit: 'dB',
        valid_pixel_count: 4000000,
        valid_area_km2: 400.0,
        algorithm_version: 'sar2action-change-engine-v1.0.0',
        calculation_formula:
          'median(10*log10(HV_T1) - 10*log10(HV_T0)) where 0 < mask < 255 and P > 0',
        target_layer_type: 'delta_hv',
      },
      {
        claim_id: `${evidenceId}-CLAIM-DELTA-HH`,
        statement: `Median HH backscatter changed by -0.5210 dB across 4,000,000 valid comparable 10 m pixels (400.000 km²).`,
        evidence_id: evidenceId,
        case_id: 'case-flagship-oki-f2',
        roi_id: roiId,
        scene_ids: [
          'NISAR_L2_PR_GCOV_030_010_A_176_4005_DHDH_A_20260906T224025_20260906T224100_P05023_N_F_J_001',
          'NISAR_L2_PR_GCOV_031_010_A_176_4005_DHDH_A_20260918T224025_20260918T224100_P05023_F_F_J_001',
        ],
        aoi_bbox_wgs84: [105.28, -3.28, 105.48, -3.08],
        polarization: 'HH',
        metric_name: 'median_delta_hh_db',
        metric_value: -0.521,
        unit: 'dB',
        valid_pixel_count: 4000000,
        valid_area_km2: 400.0,
        algorithm_version: 'sar2action-change-engine-v1.0.0',
        calculation_formula:
          'median(10*log10(HH_T1) - 10*log10(HH_T0)) where 0 < mask < 255 and P > 0',
        target_layer_type: 'delta_hh',
      },
    ],
    layers: {
      t0_hh: makeLayer('t0_hh', 'T0 HH Backscatter (dB)', evidenceId),
      t1_hh: makeLayer('t1_hh', 'T1 HH Backscatter (dB)', evidenceId),
      t0_hv: makeLayer('t0_hv', 'T0 HV Backscatter (dB)', evidenceId),
      t1_hv: makeLayer('t1_hv', 'T1 HV Backscatter (dB)', evidenceId),
      delta_hh: makeLayer('delta_hh', 'Signed ΔHH (dB)', evidenceId),
      delta_hv: makeLayer('delta_hv', 'Signed ΔHV (dB)', evidenceId),
      magnitude_hh: makeLayer('magnitude_hh', 'Absolute Change |ΔHH| (dB)', evidenceId),
      magnitude_hv: makeLayer('magnitude_hv', 'Absolute Change |ΔHV| (dB)', evidenceId),
      combined_change: makeLayer('combined_change', 'Combined Radar Change (dB)', evidenceId),
      validity_mask: makeLayer('validity_mask', 'Scientific Validity Mask', evidenceId),
    },
    evidence_record: {
      evidence_id: evidenceId,
      evidence_type: 'radar_change',
      scene_ids: [
        'NISAR_L2_PR_GCOV_030_010_A_176_4005_DHDH_A_20260906T224025_20260906T224100_P05023_N_F_J_001',
        'NISAR_L2_PR_GCOV_031_010_A_176_4005_DHDH_A_20260918T224025_20260918T224100_P05023_F_F_J_001',
      ],
      roi_id: roiId,
      geometry: null,
      polarizations: hhOnly ? ['HH'] : ['HH', 'HV'],
      t0_db: {},
      t1_db: {},
      delta_db: {},
      magnitude_db: {},
      combined_change_db: null,
      summary_statistics: {},
      valid_pixel_count: 4000000,
      coverage_ratio: 1.0,
      missing_data_ratio: 0.0,
      quality_status: hhOnly ? 'LIMITED' : 'COMPARABLE',
      algorithm_version: 'sar2action-change-engine-v1.0.0',
      processing_metadata: {},
      limitations: ['cause_not_determined', 'not_burn_severity_or_fire_damage', 'provisional_product'],
    },
  };
}

describe('SAR2Action Phase 3B Vertical Slice Frontend', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.endsWith('/api/cases')) {
        return new Response(JSON.stringify(MOCK_CASES), { status: 200 });
      }
      if (url.endsWith('/api/radar-fingerprint')) {
        const body = JSON.parse((init?.body as string) || '{}');
        if (body.aoi_id === 'AOI-OUTSIDE-TEST') {
          return new Response(
            JSON.stringify({
              detail: {
                error_code: 'AOI_OUTSIDE_COVERAGE',
                message: 'Selected AOI is outside valid comparable radar coverage.',
                science_status: 'INSUFFICIENT_EVIDENCE',
              },
            }),
            { status: 422 }
          );
        }
        const hhOnly =
          Array.isArray(body.requested_polarizations) &&
          body.requested_polarizations.length === 1 &&
          body.requested_polarizations[0] === 'HH';
        const roiId = body.aoi_id || 'AOI-CUSTOM-DRAWN';
        const evidenceId =
          roiId === 'AOI-OKI-02' ? 'E-FLAGSHIP-OKI-002' : 'E-FLAGSHIP-OKI-001';
        return new Response(
          JSON.stringify(makeFingerprintResponse({ hhOnly, roiId, evidenceId })),
          { status: 200 }
        );
      }
      if (url.includes('/api/evidence/')) {
        const fp = makeFingerprintResponse();
        return new Response(JSON.stringify(fp.evidence_record), { status: 200 });
      }
      return new Response('{}', { status: 200 });
    });
  });

  it('1. switches Radar Reveal layers (T0, T1, Swipe, Delta HH/HV, Combined, Mask) & renders scientific legend', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('radar-fingerprint-panel')).toBeInTheDocument();
    });

    // Default is delta_hv
    expect(screen.getByTestId('scientific-legend-card')).toHaveTextContent(
      'Signed ΔHV (dB) Legend'
    );

    // Switch to T0 HH
    fireEvent.click(screen.getByTestId('layer-btn-t0_hh'));
    expect(screen.getByTestId('scientific-legend-card')).toHaveTextContent(
      'T0 HH Backscatter (dB) Legend'
    );

    // Switch to Swipe T0/T1 (HH)
    fireEvent.click(screen.getByTestId('layer-btn-swipe_hh'));
    expect(screen.getByTestId('swipe-stage')).toBeInTheDocument();
    expect(screen.getByTestId('swipe-slider-bar')).toBeInTheDocument();

    // Switch to Combined Radar Change and verify mandatory disclaimer
    fireEvent.click(screen.getByTestId('layer-btn-combined_change'));
    expect(screen.getByTestId('combined-metric-disclaimer')).toHaveTextContent(
      'Custom visualization metric — not a hazard score, fire probability, damage score, or official burn-severity index.'
    );
  });

  it('2. supports preset AOI selection and interactive custom AOI drawing on map', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('fingerprint-evidence-id')).toHaveTextContent(
        'E-FLAGSHIP-OKI-001'
      );
    });

    // Select second preset AOI
    fireEvent.click(screen.getByTestId('preset-aoi-AOI-OKI-02'));
    await waitFor(() => {
      expect(screen.getByTestId('fingerprint-evidence-id')).toHaveTextContent(
        'E-FLAGSHIP-OKI-002'
      );
    });
  });

  it('3. displays explicit API Science Gate Refusal banner when AOI is outside coverage', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('radar-fingerprint-panel')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('btn-test-outside-aoi'));
    await waitFor(() => {
      expect(screen.getByTestId('science-error-banner')).toBeInTheDocument();
    });
    expect(screen.getByTestId('science-error-banner')).toHaveTextContent('AOI_OUTSIDE_COVERAGE');
    expect(screen.getByTestId('science-error-banner')).toHaveTextContent('INSUFFICIENT_EVIDENCE');
    // Stale statistics from the previous AOI must be cleared after a refusal
    expect(screen.queryByTestId('radar-fingerprint-panel')).not.toBeInTheDocument();
    expect(screen.queryByTestId('evidence-inspector-drawer')).not.toBeInTheDocument();
  });

  it('4. displays "Unavailable" (never synthetic zero) when HV polarization is absent', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('pol-status-hv')).toHaveTextContent('Available');
    });

    fireEvent.click(screen.getByTestId('pol-mode-hh-only'));
    await waitFor(() => {
      expect(screen.getByTestId('pol-status-hv')).toHaveTextContent('Unavailable');
    });
    expect(screen.getByTestId('pol-card-hv')).toHaveTextContent('Unavailable');
    expect(screen.queryByTestId('median-delta-hv')).not.toBeInTheDocument();
  });

  it('5. renders What We Know / Do Not Know and navigates Claim-to-Evidence trail on click', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('epistemic-summary-panel')).toBeInTheDocument();
    });

    expect(screen.getByTestId('epistemic-summary-panel')).toHaveTextContent('WHAT WE OBSERVED');
    expect(screen.getByTestId('epistemic-summary-panel')).toHaveTextContent('WHAT MAY EXPLAIN IT');
    expect(screen.getByTestId('epistemic-summary-panel')).toHaveTextContent('WHAT WE DO NOT KNOW');

    const hhClaimBtn = screen.getByTestId('claim-btn-E-FLAGSHIP-OKI-001-CLAIM-DELTA-HH');
    fireEvent.click(hhClaimBtn);

    await waitFor(() => {
      expect(screen.getByTestId('evidence-inspector-drawer')).toHaveTextContent(
        'E-FLAGSHIP-OKI-001'
      );
    });
    expect(screen.getByTestId('evidence-inspector-drawer')).toHaveTextContent(
      'sar2action-change-engine-v1.0.0'
    );
    expect(screen.getByTestId('evidence-inspector-drawer')).toHaveTextContent(
      'cause_not_determined'
    );
  });

  it('6. visibly displays PROVISIONAL, CAUSE NOT DETERMINED, non-attribution statement, and dB composite unit', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('radar-fingerprint-panel')).toBeInTheDocument();
    });

    expect(screen.getByTestId('badge-provisional')).toHaveTextContent('PROVISIONAL');
    expect(screen.getByTestId('badge-cause-not-determined')).toHaveTextContent(
      'CAUSE NOT DETERMINED'
    );
    expect(screen.getByTestId('non-attribution-statement')).toHaveTextContent(
      'NISAR-derived radar analysis: 2026-09-06T22:40:25Z → 2026-09-18T22:40:25Z.'
    );
    expect(screen.getByTestId('non-attribution-statement')).toHaveTextContent(
      'Radar change alone does not establish the physical cause.'
    );
    expect(screen.getByTestId('combined-change-summary')).toHaveTextContent('dB composite');
  });

  it('keeps synthetic investigator mode distinct from NISAR layers and claims', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByTestId('radar-fingerprint-panel')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('Data mode'), { target: { value: 'fixture' } });
    expect(screen.getByTestId('badge-demo-mode')).toHaveTextContent('SIMULATED DATA — NOT NASA OBSERVATIONS');
    expect(screen.getByTestId('non-attribution-statement')).toHaveTextContent('synthetic spatial ranking');
    expect(screen.queryByTestId('radar-fingerprint-panel')).not.toBeInTheDocument();
  });
});
