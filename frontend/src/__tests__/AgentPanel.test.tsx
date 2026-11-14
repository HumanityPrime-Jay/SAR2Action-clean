import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AgentPanel } from '../components/AgentPanel';

const region = {
  region_id: 'REG-DEMO', rank: 1, bbox_wgs84: [100.02, 0.02, 100.07, 0.07], crs: 'EPSG:4326',
  median_abs_change_db: 3.14, median_signed_change_db: 3.01, pixel_count: 40,
  valid_pixel_percentage: 95, area_km2_approx: 0.7, evidence_ids: ['SYN-SP-DEMO'],
  observation_times: ['SIMULATED_T0', 'SIMULATED_T1'], polarization: 'HV', limitations: ['SIMULATED DATA'],
};
const result = {
  status: 'completed', mode: 'fixture', narrative: 'Synthetic connected change.',
  claims: [{ statement: 'Median change 3.14 dB', evidence_id: 'SYN-SP-DEMO', unit: 'dB' }],
  evidence_ids: ['SYN-SP-DEMO'], unknowns: ['Cause unknown'],
  trace: [{ tool: 'rank_change_regions', status: 'complete' }], map_actions: [],
  data_notice: 'SIMULATED DATA — NOT NASA OBSERVATIONS', ranked_regions: [region],
};
const story = { story_id: 'story-demo', status: 'current', mode: 'fixture', evidence_ids: ['SYN-SP-DEMO'],
  frames: Array.from({ length: 5 }, (_, index) => ({ title: `Scene ${index+1}`, narrative: `Narrative ${index+1}`,
    evidence_ids: ['SYN-SP-DEMO'], map_state: { bbox: region.bbox_wgs84, layer_id: 'delta_hv' },
    visualization: 'map', source: ['SIMULATED_T0', 'SIMULATED_T1'] })) };

const props = {
  activeCase: { case_id: 'fixture-case', region_name: 'Fixture area', default_t0_scene_id: 'SIMULATED_T0',
    default_t1_scene_id: 'SIMULATED_T1' } as any,
  bbox: [100, 0, 100.2, 0.2] as [number, number, number, number],
  polarizationMode: 'DUAL' as const, availableLayers: {},
  onFocusBbox: vi.fn(), onSetLayer: vi.fn(), onOpenEvidence: vi.fn(),
};

const jsonResponse = (value: unknown) => ({ ok: true, json: async () => value });
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks(); });

describe('AgentPanel spatial flow', () => {
  it('shows ranked evidence, focuses a region, and navigates a story', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: string) => {
      if (input.endsWith('/status')) return jsonResponse({ agent: { status: 'offline' } });
      if (input.endsWith('/investigate')) return jsonResponse(result);
      if (input.includes('/spatial/evidence/')) return jsonResponse({ evidence_id: 'SYN-SP-DEMO', data_kind: 'synthetic', scene_ids: ['SIMULATED_T0', 'SIMULATED_T1'] });
      if (input.endsWith('/story')) return jsonResponse(story);
      throw Error(`Unexpected fetch ${input}`);
    }));
    render(<AgentPanel {...props} />);
    fireEvent.change(screen.getByLabelText('Data mode'), { target: { value: 'fixture' } });
    fireEvent.change(screen.getByLabelText('Ask about this area'), { target: { value: 'top three regions' } });
    fireEvent.click(screen.getByRole('button', { name: 'Investigate' }));
    await waitFor(() => expect(screen.getByText(/REG-DEMO/)).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Focus on Map' }));
    expect(props.onFocusBbox).toHaveBeenCalledWith(region.bbox_wgs84);
    fireEvent.click(screen.getByRole('button', { name: 'Inspect Evidence' }));
    await waitFor(() => expect(screen.getByText(/Data: synthetic/)).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Generate story' }));
    await waitFor(() => expect(screen.getByText('Narrative 1')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: '2. Scene 2' }));
    expect(screen.getByText('Narrative 2')).toBeInTheDocument();
  });

  it('marks a completed story stale after AOI changes', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: string) => {
      if (input.endsWith('/status')) return jsonResponse({ agent: { status: 'offline' } });
      if (input.endsWith('/investigate')) return jsonResponse(result);
      if (input.endsWith('/story')) return jsonResponse(story);
      throw Error(`Unexpected fetch ${input}`);
    }));
    const view = render(<AgentPanel {...props} />);
    fireEvent.change(screen.getByLabelText('Data mode'), { target: { value: 'fixture' } });
    fireEvent.click(screen.getByRole('button', { name: 'Investigate' }));
    await waitFor(() => expect(screen.getByText(/REG-DEMO/)).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Generate story' }));
    await waitFor(() => expect(screen.getByText('Narrative 1')).toBeInTheDocument());
    view.rerender(<AgentPanel {...props} bbox={[100.1, 0, 100.2, 0.2]} />);
    await waitFor(() => expect(screen.getByText(/Earth Change Story \(Stale\)/)).toBeInTheDocument());
  });
});
