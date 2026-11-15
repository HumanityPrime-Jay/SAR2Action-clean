import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AssistScreen } from '../screens/AssistScreen';
import * as tw05Api from '../api/tw05';
import type { FarmerInfo } from '../data/farmer';

/** Relief schedule (附表二) items and Yunlin announcements, trimmed to what the estimate panel reads. */
const CATALOG: tw05Api.TwAgroReliefCatalog = {
  schedule_version_id: 'MOA-RELIEF-SCHEDULE-1150629-V1',
  regulation_title: '農業天然災害救助辦法',
  min_application_area_ha: 0.01,
  statutory_loss_threshold_fraction: 0.2,
  items: [
    { item_id: 'unknown_crop', display_name: '未知作物／尚未現場勘查確認', statutory_category: '', rate_twd_per_ha: null, unit: '元／公頃', announced_in_yunlin_11510: false },
    { item_id: 'veg_6', display_name: '蔬菜（六）：蘆筍、大蒜、青蒜、洋蔥、甜椒等', statutory_category: '', rate_twd_per_ha: 95000, unit: '元／公頃', announced_in_yunlin_11510: true },
    { item_id: 'unannounced_other_crop', display_name: '其他未列入本次雲林縣公告品項（如水稻）', statutory_category: '', rate_twd_per_ha: null, unit: '元／公頃', announced_in_yunlin_11510: false },
  ],
  announcements: [{ doc_id: 'MOA-1151112527F', application_end_iso: '2026-11-09', expired_as_of_reference_date: true }],
};

const estimate = (over: Partial<tw05Api.TwAgroReliefEstimateResponse>): tw05Api.TwAgroReliefEstimateResponse => ({
  calculation_allowed: false,
  result_status: 'BLOCKED_UNKNOWN_CROP',
  result_label: '',
  conditional_reference_amount_twd: null,
  confirmed_facts: {},
  user_assumptions: {},
  unconfirmed_eligibility: [],
  non_approval_disclaimer: '',
  ...over,
});

const farmerWith = (crop: FarmerInfo['crop']): FarmerInfo => ({ cadastral: '', crop, cropOther: '' });

function renderAssist(farmer: FarmerInfo | null) {
  const noop = vi.fn();
  render(<AssistScreen selectedId="YL-CAND-01" go={noop} eventId="champi-2026-yunlin" onEvent={noop} farmer={farmer} onFarmer={noop} onSelect={noop} />);
}

describe('AssistScreen relief estimate (official schedule)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(tw05Api, 'fetchReliefCatalog').mockResolvedValue(CATALOG);
  });

  it("uses the farmer's crop to pick the schedule item and its rate, over the whole field, with the 20% gate stated", async () => {
    const spy = vi.spyOn(tw05Api, 'estimateRelief').mockResolvedValue(
      estimate({ calculation_allowed: true, result_status: 'CONDITIONAL_REFERENCE_ESTIMATE', conditional_reference_amount_twd: 1189846 }),
    );
    renderAssist(farmerWith('garlic'));
    expect(await screen.findByText('NT$ 1,189,846')).toBeInTheDocument();
    expect(screen.getByText('95,000 /ha')).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: '救助品項（附表二）' })).toHaveValue('veg_6');
    expect(screen.getByText('假設整塊田核定、損失率達 20%。')).toBeInTheDocument();
    expect(spy).toHaveBeenLastCalledWith({ crop_item_id: 'veg_6', assumed_approved_area_ha: expect.closeTo(12.5247, 3), assumed_loss_threshold: 'meets_20_percent' });
    expect(screen.getByText('待主管機關認定')).toBeInTheDocument();
  });

  it('says the application window has closed', async () => {
    vi.spyOn(tw05Api, 'estimateRelief').mockResolvedValue(estimate({}));
    renderAssist(null);
    expect(await screen.findByText('申請期限已過')).toBeInTheDocument();
    expect(screen.getByText('公告受理至 2026-11-09。')).toBeInTheDocument();
  });

  it('shows no amount for a crop outside the announcement, and says why', async () => {
    vi.spyOn(tw05Api, 'estimateRelief').mockResolvedValue(estimate({ result_status: 'BLOCKED_UNANNOUNCED_OR_EXCLUDED_ITEM' }));
    renderAssist(farmerWith('rice'));
    expect(await screen.findByText('這個品項不在本次雲林縣救助公告內，沒有現金救助。')).toBeInTheDocument();
    expect(screen.getByText('試算上限').nextElementSibling).toHaveTextContent('—');
  });

  it('shows no amount when the estimate service is down, rather than a made-up rate', async () => {
    vi.spyOn(tw05Api, 'fetchReliefCatalog').mockRejectedValue(new Error('offline'));
    const spy = vi.spyOn(tw05Api, 'estimateRelief');
    renderAssist(farmerWith('garlic'));
    expect(await screen.findByText('試算服務連不上')).toBeInTheDocument();
    await waitFor(() => expect(spy).not.toHaveBeenCalled());
    expect(screen.getByText('試算上限').nextElementSibling).toHaveTextContent('—');
  });

  it('has a single field: no demo / TW-05 scope switch', () => {
    vi.spyOn(tw05Api, 'estimateRelief').mockResolvedValue(estimate({}));
    renderAssist(null);
    expect(screen.queryByRole('button', { name: /TW-05/ })).not.toBeInTheDocument();
    expect(screen.queryByText('DEMO · TAIXI')).not.toBeInTheDocument();
  });
});
