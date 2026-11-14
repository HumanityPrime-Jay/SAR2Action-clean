import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AssistScreen } from '../screens/AssistScreen';
import * as tw05Api from '../api/tw05';

describe('AssistScreen TW-05 & Relief Integration', () => {
  const noop = vi.fn();

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders Taixi demo by default and shows illustrative ceiling', () => {
    render(<AssistScreen selectedId="YL-CAND-01" go={noop} eventId={null} onEvent={noop} farmer={null} onFarmer={noop} onSelect={noop} />);
    expect(screen.getByText('NT$ 325,642')).toBeInTheDocument();
    expect(screen.getByText('DEMO · TAIXI')).toBeInTheDocument();
    expect(screen.getByText('待主管機關認定')).toBeInTheDocument();
  });

  it('switches to TW-05 mode, selects parcel #4183 and calculates precise relief of NT$ 16,343', async () => {
    const mockEstimate: tw05Api.TwAgroReliefEstimateResponse = {
      calculation_allowed: true,
      result_status: 'CONDITIONAL_REFERENCE_ESTIMATE',
      result_label: '條件式參考救助額',
      conditional_reference_amount_twd: 16343,
      formula_display: 'NT$ 36,000 /ha × 0.453978 ha = NT$ 16,343',
      confirmed_facts: { parcel_feature_id: 4183 },
      user_assumptions: { crop_item_id: 'grains_3_peanut_sweetpotato' },
      unconfirmed_eligibility: ['待地方公所現地勘查'],
      non_approval_disclaimer: '本試算非核認救助金額',
    };

    vi.spyOn(tw05Api, 'estimateRelief').mockResolvedValue(mockEstimate);
    vi.spyOn(tw05Api, 'fetchAgentStatus').mockResolvedValue({
      agent: { status: 'offline' },
      gemini: {
        status: 'offline',
        provider: 'gemini',
        model: 'gemini-3.1-flash-lite',
        api_key_configured: false,
        live_function_calling_verified: false,
      },
      tw05_agent_available: true,
      tw05_tools: ['query_tw01_s1_parcel_changes', 'query_tw08_s2_optical_qa', 'query_tw07_statutory_relief'],
    });

    render(<AssistScreen selectedId="YL-CAND-01" go={noop} eventId={null} onEvent={noop} farmer={null} onFarmer={noop} onSelect={noop} />);

    // Switch to TW-05
    fireEvent.click(screen.getByRole('button', { name: 'TW-05 雲林實測' }));

    // Select parcel #4183
    const parcelSelect = screen.getByRole('combobox', { name: '選擇 TW-05 農田' });
    fireEvent.change(parcelSelect, { target: { value: '4183' } });

    await waitFor(() => {
      expect(screen.getByText('NT$ 16,343')).toBeInTheDocument();
    });

    expect(screen.getByText(/NT\$ 36,000 \/ha × 0\.453978 ha = NT\$ 16,343/)).toBeInTheDocument();
    expect(screen.getByText(/CONDITIONAL ESTIMATE \/ NOT OFFICIAL/)).toBeInTheDocument();
  });

  it('queries live agent for parcel #74 and displays execution mode, tool trace and facts', async () => {
    const mockInvestigation: tw05Api.Tw05InvestigationResponse = {
      investigation_id: 'inv-test-74',
      status: 'completed',
      execution_mode: 'DETERMINISTIC_TOOL_PIPELINE',
      agent_mode: 'deterministic',
      model_provider: 'deterministic_engine',
      case_id: 'TW-05-YUNLIN-AGRO',
      aoi_id: 'TW-01-YUNLIN-5KM',
      locked_parcel_feature_id: 74,
      question: '檢查此坵塊之雷達回波變化',
      observed_facts: [
        {
          fact_id: 'fact-1',
          sensor_or_source: 'Sentinel-1D',
          metric_name: 'delta_vh_median_db',
          metric_value: -3.85,
          verified_value_str: '-3.85 dB',
          unit: 'dB',
          statement: 'Sentinel-1D 觀測到 VH 回波下降 -3.85 dB',
          epistemic_status: 'OBSERVED',
          evidence_ids: ['E-TW01-PARCEL-74'],
        },
      ],
      inferences: [
        {
          inference_id: 'inf-1',
          statement: '地表散射特徵改變，可能與作物倒伏或收穫相關',
          status: 'SUPPORTED_FOR_FOLLOWUP_ONLY',
          supporting_evidence_ids: ['E-TW01-PARCEL-74'],
          contradicting_evidence_ids: [],
          proposed_by_gemini: false,
          reason: '物理特徵支持進一步現勘',
        },
      ],
      unknowns: ['實際種植作物未經現場查證'],
      evidence_ids: ['E-TW01-PARCEL-74', 'E-TW08A-PARCEL-74'],
      evidence_records: [],
      tool_trace: [
        {
          step: 1,
          timestamp_utc: '2026-11-15T00:00:00Z',
          kind: 'tool_call',
          tool: 'query_tw01_s1_parcel_changes',
          status: 'complete',
          source_references: [],
          evidence_ids: ['E-TW01-PARCEL-74'],
          duration_ms: 12.5,
          detail: {},
        },
      ],
      scientific_limitations: ['雷達散射變化不等於農損因果'],
      epistemic_guardrails: {
        crop_type_label: 'UNKNOWN',
        actual_damage_rate: 'UNKNOWN',
        confirmed_typhoon_damage: false,
        official_relief_eligibility: 'UNKNOWN',
        optical_insufficient_parcel_flag: false,
      },
    };

    vi.spyOn(tw05Api, 'investigateTw05').mockResolvedValue(mockInvestigation);
    vi.spyOn(tw05Api, 'fetchReliefCatalog').mockResolvedValue({
      schedule_version_id: 'v1',
      regulation_title: 'Title',
      min_application_area_ha: 0.01,
      statutory_loss_threshold_fraction: 0.2,
      items: [{ item_id: 'garlic', display_name: '大蒜', statutory_category: '蔬菜', rate_twd_per_ha: 90000, unit: 'ha', announced_in_yunlin_11510: true }],
    });

    render(<AssistScreen selectedId="YL-CAND-01" go={noop} eventId={null} onEvent={noop} farmer={null} onFarmer={noop} onSelect={noop} />);

    // Switch to TW-05
    fireEvent.click(screen.getByRole('button', { name: 'TW-05 雲林實測' }));

    // Ask a question
    const input = screen.getByRole('textbox', { name: '輸入問題' });
    fireEvent.change(input, { target: { value: '檢查此坵塊之雷達回波變化' } });
    fireEvent.click(screen.getByRole('button', { name: '送出' }));

    await waitFor(() => {
      expect(screen.getAllByText(/DETERMINISTIC_TOOL_PIPELINE/).length).toBeGreaterThan(0);
    });

    expect(screen.getByText(/確認觀測事實：1 項/)).toBeInTheDocument();
    expect(screen.getByText(/query_tw01_s1_parcel_changes/)).toBeInTheDocument();
    expect(screen.getAllByText(/E-TW01-PARCEL-74/).length).toBeGreaterThan(0);
  });
});
