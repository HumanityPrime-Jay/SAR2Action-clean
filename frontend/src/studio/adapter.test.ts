import { beforeEach, describe, expect, it, vi } from 'vitest';
import recorded from '../../public/studio/recorded_investigation.json';
import trace from '../../public/studio/recorded_trace.json';
import vh from '../../public/studio/vh_timeseries.json';
import champiEvidence from '../../public/studio/champi_evidence.json';
import vhEvidence from '../../public/studio/vh_evidence.json';
import fields from '../../public/studio/fields.geojson?raw';
import official from '../../public/studio/official_loss_record.json';
import comparison from '../../public/studio/field_comparison.json';
import deterministic from '../../public/studio/field_investigation.json';
import recentGemini from '../../public/studio/field_investigation_gemini_trace.json';
import nisarMap from '../../public/studio/nisar_map_manifest.json';
import { buildEvidenceGraph, investigateLive, loadStudioAssets, makeDossier, parseFieldComparison, parseInvestigation, parseVh } from './adapter';
import { parseNisarMapManifest } from './mapScience';

const fixtures: Record<string, unknown> = {
  'fields.geojson': JSON.parse(fields), 'vh_timeseries.json': vh,
  'recorded_investigation.json': recorded, 'recorded_trace.json': trace,
  'champi_evidence.json': champiEvidence, 'vh_evidence.json': vhEvidence,
  'official_loss_record.json': official,
  'field_comparison.json': comparison, 'field_investigation.json': deterministic,
  'field_investigation_gemini_trace.json': recentGemini,
};

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const name = url.split('/').pop() || '';
    const body = fixtures[name];
    return { ok: body !== undefined, status: body === undefined ? 404 : 200, json: async () => body };
  }));
});

describe('real investigation adapter', () => {
  it('requires separate hash-traced NISAR HH/HV observation layers', () => {
    const map = parseNisarMapManifest(nisarMap);
    expect(map.scenes.map(scene => [scene.crid, scene.product_maturity])).toEqual([
      ['P05023', 'PROVISIONAL'], ['P05036', 'VALIDATED'],
    ]);
    expect(map.scenes[0].layers.HH.valid_pixels).toBe(173852);
    expect(map.scenes[1].layers.HV.valid_pixels).toBe(110287);
    expect(() => parseNisarMapManifest({ ...nisarMap, verified_typhoon_delta_allowed: true })).toThrow();
  });
  it('parses the observed five-field VH file and keeps acquisition dates/numbers', () => {
    const parsed = parseVh(vh);
    expect(parsed.observations).toHaveLength(30);
    expect(new Set(parsed.observations.map(x => x.field_id)).size).toBe(5);
    expect(parsed.observations[0].acquisition_datetime).toBe('2025-10-08T21:51:54+00:00');
    expect(parsed.observations[0].vh_median_db).toBe(-29.44731);
    expect(parsed.observations[0].valid_pixel_count).toBe(60);
  });

  it('parses all five scientific comparisons and checks Taiwan warning timing', () => {
    const parsed = parseFieldComparison(comparison);
    expect(parsed.fields).toHaveLength(5);
    expect(parsed.pixel_reverification.reextracted_field_scene_count).toBe(30);
    const first = parsed.fields[0];
    expect(first.observations['2026'][1].acquisition_utc).toBe('2026-10-22T21:51:56+00:00');
    expect(first.observations['2026'][1].acquisition_taiwan).toBe('2026-10-23T05:51:56+08:00');
    expect(first.observations['2026'][1].warning_relation).toBe('WARNING_WINDOW');
    expect(first['2026_pre_warning_change']).toBeNull();
    expect(parsed.fields[2]['2026_pre_to_warning_window']?.median_difference_db).toBe(7.55336);
    expect(parsed.fields[3]['2026_pre_to_warning_window']?.median_difference_db).toBe(6.51834);
    expect(parsed.cross_field_pattern.shared_response_is_causal_evidence).toBe(false);
  });

  it('rejects a false before-warning label for the October 22 UTC observation', () => {
    const altered = structuredClone(comparison);
    altered.fields[0].observations['2026'][1].warning_relation = 'PRE_WARNING';
    expect(() => parseFieldComparison(altered)).toThrow('warning relation');
  });

  it('rejects non-observed VH input', () => {
    expect(() => parseVh({ status: 'NOT_COMPUTED', observations: [] })).toThrow();
  });

  it('parses the real V3 response and recorded Gemini trace with resolvable evidence', async () => {
    const assets = await loadStudioAssets();
    expect(assets.recordedTrace.mode).toBe('gemini');
    expect(assets.recordedDeterministic.vh_timeseries?.field_id).toBe('YL-CAND-01');
    expect(assets.recentGeminiTrace.investigation_id).not.toBe(assets.recorded.investigation_id);
    expect(assets.recordedTrace.trace.length).toBeGreaterThan(10);
    expect(assets.integrityWarnings).toEqual([]);
    expect(assets.evidence.has('E-CHAMPI-NISAR-TAIXI-PRE')).toBe(true);
    expect(assets.evidence.has(vh.observations[0].evidence_id)).toBe(true);
  });

  it('calls the actual V3 API with the selected field and parses the response', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => recorded })));
    const result = await investigateLive('YL-CAND-03', 'Inspect this candidate');
    expect(result.investigation_id).toBe(recorded.investigation_id);
    const init = vi.mocked(fetch).mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(init.body)).field_id).toBe('YL-CAND-03');
    expect(JSON.parse(String(init.body)).agent_mode).toBe('deterministic');
  });

  it('requests Gemini explicitly for a live Gemini run', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => recorded })));
    await investigateLive('YL-CAND-03', 'Investigate actual warning-window change', 'gemini');
    const init = vi.mocked(fetch).mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(init.body)).agent_mode).toBe('gemini');
    expect(JSON.parse(String(init.body)).field_id).toBe('YL-CAND-03');
  });

  it('builds graph edges only from actual Evidence references', async () => {
    const assets = await loadStudioAssets();
    const graph = buildEvidenceGraph(assets.recorded, assets.evidence);
    const ids = new Set(graph.nodes.map(node => node.id));
    expect(graph.edges.length).toBeGreaterThan(0);
    expect(graph.edges.every(edge => ids.has(edge.from) && ids.has(edge.to))).toBe(true);
    expect(graph.nodes.some(node => node.label.startsWith('UNRESOLVED_REFERENCE'))).toBe(false);
    expect(graph.nodes.some(node => node.type === 'SCIENTIFIC_TEST')).toBe(true);
  });

  it('retains unresolved references instead of inventing evidence', async () => {
    const assets = await loadStudioAssets();
    const altered = parseInvestigation({ ...assets.recorded, evidence_ids: [...assets.recorded.evidence_ids, 'E-MISSING'] });
    const graph = buildEvidenceGraph(altered, assets.evidence);
    expect(graph.nodes.find(node => node.id === 'evidence:E-MISSING')?.payload.status).toBe('UNRESOLVED_REFERENCE');
  });

  it('exports a dossier with actual observations, QA and the cross-CRID refusal', async () => {
    const assets = await loadStudioAssets();
    const dossier = makeDossier(assets.recordedDeterministic, 'RECORDED_DETERMINISTIC', 'YL-CAND-01', assets.recordedDeterministic.tool_trace);
    expect(dossier.investigation_id).toBe(assets.recordedDeterministic.investigation_id);
    expect(dossier.real_observations).toHaveLength(assets.recordedDeterministic.observation_timeline.length);
    expect(dossier.five_field_comparison).toBeTruthy();
    expect(dossier.actual_tool_trace.length).toBeGreaterThan(10);
    expect(dossier.scientific_qa.verified_typhoon_delta_allowed).toBe(false);
    expect(dossier.executed_tests.some(x => x.test_id === 'cross_crid_radiometric_compatibility' && x.status === 'FAIL')).toBe(true);
  });
});
