import type { FieldComparison, GraphEdge, GraphNode, StudioAssets, StudioInvestigation, StudioMode, TraceEvent, VhObservation } from './contracts';

const base = import.meta.env.BASE_URL || '/';
const asset = (name: string) => `${base}studio/${name}`;

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Expected an object from science data');
  return value as Record<string, unknown>;
}
function array(value: unknown): unknown[] { if (!Array.isArray(value)) throw new Error('Expected an array from science data'); return value; }
function string(value: unknown): string { if (typeof value !== 'string') throw new Error('Expected text from science data'); return value; }

export function parseInvestigation(value: unknown): StudioInvestigation {
  const item = object(value);
  for (const key of ['case_id', 'aoi_id', 'investigation_id', 'question', 'data_mode', 'provenance_status']) string(item[key]);
  for (const key of ['observation_timeline', 'available_sensors', 'observed_changes', 'hypotheses', 'hypothesis_tests', 'evidence_ids', 'scientific_limitations', 'missing_evidence', 'tool_trace']) array(item[key]);
  object(item.qa);
  object(item.expert_report);
  return item as unknown as StudioInvestigation;
}

export function parseVh(value: unknown): StudioAssets['vh'] {
  const root = object(value);
  if (root.status !== 'OBSERVED_OPERA_RTC_S1') throw new Error('VH data is not observed OPERA RTC-S1');
  const observations = array(root.observations).map(raw => {
    const row = object(raw);
    for (const key of ['field_id', 'acquisition_datetime', 'platform', 'orbit_direction', 'source_scene_id', 'evidence_id']) string(row[key]);
    if (![2025, 2026].includes(Number(row.year))) throw new Error('VH observation has unexpected year');
    if (!Number.isFinite(Date.parse(String(row.acquisition_datetime)))) throw new Error('VH acquisition datetime is invalid');
    if (row.vh_median_db !== null && typeof row.vh_median_db !== 'number') throw new Error('VH median must be numeric or null');
    if (!Number.isFinite(Number(row.valid_pixel_count))) throw new Error('VH pixel count missing');
    array(row.qa_flags);
    return row as unknown as VhObservation;
  });
  return { status: string(root.status), observations, mean_definition: typeof root.mean_definition === 'string' ? root.mean_definition : undefined };
}

export function parseFieldComparison(value: unknown): FieldComparison {
  const root = object(value);
  if (root.status !== 'OBSERVED_DESCRIPTIVE_ONLY') throw new Error('Five-field comparison is not observed');
  const fields = array(root.fields);
  if (fields.length !== 5) throw new Error('Expected five observed field comparisons');
  const event = object(root.event_reference);
  const start = Date.parse(string(event.start_taiwan)), end = Date.parse(string(event.end_taiwan));
  if (!Number.isFinite(start) || !Number.isFinite(end) || start >= end) throw new Error('Invalid local warning window');
  const seen = new Set<string>();
  for (const entry of fields) {
    const field = object(entry);
    string(field.field_id);
    const byYear = object(field.observations);
    for (const year of ['2025', '2026']) {
      const rows = array(byYear[year]);
      if (rows.length !== 3) throw new Error(`Incomplete observed ${year} field series`);
      for (const raw of rows) {
        const row = object(raw);
        const id = string(row.evidence_id);
        if (seen.has(id)) throw new Error('Duplicate field Evidence ID');
        seen.add(id);
        const utc = Date.parse(string(row.acquisition_utc));
        const local = Date.parse(string(row.acquisition_taiwan));
        if (!Number.isFinite(utc) || utc !== local) throw new Error('UTC and Taiwan timestamps disagree');
        const relation = year === '2025' ? 'HISTORICAL_REFERENCE' :
          utc < start ? 'PRE_WARNING' : utc > end ? 'POST_WARNING' : 'WARNING_WINDOW';
        if (row.warning_relation !== relation) throw new Error('Observation warning relation disagrees with time');
        if (typeof row.vh_median_db !== 'number' || !Number.isFinite(row.vh_median_db) ||
            Number(row.valid_pixel_count) < 8 || Number(row.valid_coverage_ratio) < .8)
          throw new Error('Field comparison lacks valid pixel support');
      }
    }
  }
  if (seen.size !== 30 || object(root.pixel_reverification).reextracted_field_scene_count !== 30 ||
      object(root.cross_field_pattern).shared_response_is_causal_evidence !== false)
    throw new Error('Five-field source QA or causality guard is incomplete');
  return root as unknown as FieldComparison;
}

async function getJson(url: string): Promise<unknown> {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  return response.json();
}

export async function loadStudioAssets(): Promise<StudioAssets> {
  const [fieldsRaw, vhRaw, recordedRaw, traceRaw, champiRaw, vhEvidenceRaw, officialRaw,
    comparisonRaw, deterministicRaw, recentGeminiRaw] = await Promise.all([
    'fields.geojson', 'vh_timeseries.json', 'recorded_investigation.json', 'recorded_trace.json',
    'champi_evidence.json', 'vh_evidence.json', 'official_loss_record.json',
    'field_comparison.json', 'field_investigation.json', 'field_investigation_gemini_trace.json',
  ].map(name => getJson(asset(name))));
  const fields = object(fieldsRaw);
  if (fields.type !== 'FeatureCollection') throw new Error('Field GeoJSON is invalid');
  const features = array(fields.features).map(value => {
    const feature = object(value);
    return { type: string(feature.type), geometry: object(feature.geometry) as unknown as StudioAssets['fields']['features'][number]['geometry'], properties: object(feature.properties) };
  });
  const vh = parseVh(vhRaw);
  const comparison = parseFieldComparison(comparisonRaw);
  const recorded = parseInvestigation(recordedRaw);
  const deterministicArtifact = object(deterministicRaw);
  if (deterministicArtifact.agent_mode !== 'deterministic' || deterministicArtifact.parcel_damage_status !== 'UNKNOWN')
    throw new Error('Recorded deterministic case has wrong provenance');
  const recordedDeterministic = parseInvestigation(deterministicArtifact.api_response);
  if (recordedDeterministic.vh_timeseries?.field_id !== deterministicArtifact.selected_field ||
      recordedDeterministic.tool_trace.length === 0)
    throw new Error('Recorded deterministic trace does not match its field');
  const recentGemini = object(recentGeminiRaw);
  if (recentGemini.agent_mode !== 'gemini' || !Array.isArray(recentGemini.tool_trace) ||
      recentGemini.tool_trace.length === 0)
    throw new Error('Recorded Gemini execution trace is missing');
  const trace = object(traceRaw);
  const records = [...array(object(champiRaw).records), ...array(object(vhEvidenceRaw).records)].map(object);
  const evidence = new Map(records.map(r => [string(r.evidence_id), r]));
  const warnings: string[] = [];
  if (trace.investigation_id !== recorded.investigation_id) warnings.push('Recorded trace investigation ID does not match the saved response.');
  if (trace.mode !== 'gemini') warnings.push('Recorded trace is not identified as a Gemini execution.');
  for (const id of recorded.evidence_ids) if (!evidence.has(id)) warnings.push(`UNRESOLVED_REFERENCE: ${id}`);
  for (const row of vh.observations) if (!evidence.has(row.evidence_id)) warnings.push(`UNRESOLVED_REFERENCE: ${row.evidence_id}`);
  for (const id of recordedDeterministic.evidence_ids) if (!evidence.has(id)) warnings.push(`UNRESOLVED_REFERENCE: ${id}`);
  for (const field of comparison.fields) for (const id of field.evidence_ids)
    if (!evidence.has(id)) warnings.push(`UNRESOLVED_REFERENCE: ${id}`);
  return { fields: { type: 'FeatureCollection', features }, vh, recorded,
           recordedDeterministic, comparison,
           recentGeminiTrace: { investigation_id: string(recentGemini.investigation_id),
                                selected_tools: array(recentGemini.selected_tools) as string[][],
                                tool_trace: array(recentGemini.tool_trace).map(object) as TraceEvent[] },
           recordedTrace: { investigation_id: String(trace.investigation_id), mode: String(trace.mode), trace: array(trace.trace).map(object) as TraceEvent[] },
           evidence, officialLoss: object(officialRaw), integrityWarnings: [...new Set(warnings)] };
}

export async function investigateLive(fieldId: string, question: string,
                                      agentMode: 'deterministic' | 'gemini' = 'deterministic'): Promise<StudioInvestigation> {
  const response = await fetch('/api/agent/investigate-v3', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ case_id: 'CHAMPI-YUNLIN-TAIXI', aoi_id: '10009160', field_id: fieldId,
                           question, agent_mode: agentMode }),
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Investigation API HTTP ${response.status}: ${body.slice(0, 300)}`);
  }
  return parseInvestigation(await response.json());
}

export type ChallengeKind = 'timing' | 'seasonal' | 'cross_field' | 'cross_crid' | 'ground_truth';

export async function runEvidenceChallenge(kind: ChallengeKind, fieldId: string,
  ledger: Map<string, Record<string, unknown>>): Promise<Record<string, unknown>> {
  if (kind === 'cross_crid') {
    const report = await investigateLive(fieldId, 'Recheck deterministic cross-CRID compatibility for this case.', 'deterministic');
    const gate = report.hypothesis_tests.find(test => test.test_id === 'cross_crid_radiometric_compatibility');
    if (!gate) throw new Error('NOT AVAILABLE: cross-CRID gate was not returned by V3');
    const ids = Array.isArray(gate.evidence_ids) ? gate.evidence_ids.filter((id): id is string => typeof id === 'string') : [];
    if (!ids.length || ids.some(id => !ledger.has(id))) throw new Error('UNRESOLVED_REFERENCE: cross-CRID Evidence ID');
    return { ...gate, investigation_id: report.investigation_id, execution: 'LIVE_DETERMINISTIC_V3' };
  }
  const tools: Record<Exclude<ChallengeKind, 'cross_crid'>, string> = {
    timing: 'check_event_temporal_alignment', seasonal: 'compare_seasonal_backscatter',
    cross_field: 'compare_five_fields', ground_truth: 'find_missing_observations',
  };
  const tool = tools[kind];
  const response = await fetch('/api/agent/agriculture-vh/tool', { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tool, field_id: fieldId }) });
  if (!response.ok) throw new Error(`${tool}: HTTP ${response.status}`);
  const result = object(await response.json());
  const ids = array(result.evidence_ids).map(string);
  if (result.status === 'UNKNOWN' || !ids.length) throw new Error(`${tool}: NOT AVAILABLE for observed Evidence`);
  const missing = ids.filter(id => !ledger.has(id));
  if (missing.length) throw new Error(`UNRESOLVED_REFERENCE: ${missing.join(', ')}`);
  return { ...result, tool, field_id: fieldId, execution: 'LIVE_DETERMINISTIC_TOOL' };
}

export function referencedIds(result: StudioInvestigation): string[] {
  const ids = new Set<string>(result.evidence_ids);
  for (const item of result.observation_timeline) if (typeof item.evidence_id === 'string') ids.add(item.evidence_id);
  for (const item of [...result.hypotheses, ...result.hypothesis_tests]) {
    for (const key of ['evidence_ids', 'supporting_evidence_ids', 'contradicting_evidence_ids'])
      if (Array.isArray(item[key])) for (const id of item[key]) if (typeof id === 'string') ids.add(id);
  }
  return [...ids];
}

export function buildEvidenceGraph(result: StudioInvestigation, ledger: Map<string, Record<string, unknown>>): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];
  const seen = new Set<string>();
  const add = (node: GraphNode) => { if (!seen.has(node.id)) { seen.add(node.id); nodes.push(node); } };
  for (const sensor of result.available_sensors) {
    const mission = String(sensor.mission || 'unavailable');
    add({ id: `dataset:${mission}`, type: 'DATASET', label: mission, payload: sensor });
  }
  for (const id of referencedIds(result)) {
    const record = ledger.get(id);
    add({ id: `evidence:${id}`, type: 'EVIDENCE', label: record ? id : `UNRESOLVED_REFERENCE ${id}`,
          payload: record || { evidence_id: id, status: 'UNRESOLVED_REFERENCE' } });
  }
  result.observation_timeline.forEach((item, index) => {
    const id = `observation:${index}`;
    add({ id, type: 'OBSERVATION', label: `${String(item.mission || 'Observation')} ${String(item.acquisition_start_utc || '')}`, payload: item });
    if (typeof item.evidence_id === 'string') edges.push({ from: id, to: `evidence:${item.evidence_id}`, relation: 'REFERENCES' });
    if (typeof item.mission === 'string' && seen.has(`dataset:${item.mission}`))
      edges.push({ from: id, to: `dataset:${item.mission}`, relation: 'DERIVED_FROM' });
  });
  result.hypotheses.forEach((item, index) => {
    const id = `hypothesis:${index}`;
    add({ id, type: 'HYPOTHESIS', label: String(item.hypothesis_id || item.statement || id), payload: item });
    for (const ref of Array.isArray(item.supporting_evidence_ids) ? item.supporting_evidence_ids : [])
      if (typeof ref === 'string') edges.push({ from: id, to: `evidence:${ref}`, relation: 'SUPPORTED_BY' });
    for (const ref of Array.isArray(item.contradicting_evidence_ids) ? item.contradicting_evidence_ids : [])
      if (typeof ref === 'string') edges.push({ from: id, to: `evidence:${ref}`, relation: 'CONTRADICTED_BY' });
  });
  result.hypothesis_tests.forEach((item, index) => {
    const id = `test:${index}`;
    add({ id, type: 'SCIENTIFIC_TEST', label: String(item.test_id || id), payload: item });
    for (const ref of Array.isArray(item.evidence_ids) ? item.evidence_ids : [])
      if (typeof ref === 'string') edges.push({ from: id, to: `evidence:${ref}`, relation: 'REFERENCES' });
  });
  return { nodes, edges: edges.filter(edge => seen.has(edge.from) && seen.has(edge.to)) };
}

export function makeDossier(result: StudioInvestigation, mode: StudioMode, selectedField: string, trace: TraceEvent[]) {
  return {
    dossier_schema: 'sar2action-investigation-dossier-v1', investigation_id: result.investigation_id,
    mode, investigation_time_utc: trace.find(x => x.timestamp_utc)?.timestamp_utc || null,
    selected_aoi: { case_id: result.case_id, aoi_id: result.aoi_id, field_id: selectedField },
    satellite_sources: result.available_sensors, real_observations: result.observation_timeline,
    scientific_qa: result.qa, temporal_context: result.vh_comparison,
    five_field_comparison: result.field_comparison,
    selected_field_temporal_changes: result.temporal_changes,
    hypotheses: result.hypotheses, executed_tests: result.hypothesis_tests,
    evidence_references: result.evidence_ids, observed_facts: result.expert_report.observed || [],
    supported_interpretations: result.expert_report.possible_interpretation || [],
    unresolved_hypotheses: result.expert_report.unknown || [],
    recommended_action: result.recommended_next_action, missing_evidence: result.missing_evidence,
    official_disaster_context: result.official_loss_context, scientific_limitations: result.scientific_limitations,
    actual_tool_trace: trace,
  };
}
