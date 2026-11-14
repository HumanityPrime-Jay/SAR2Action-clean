import React from 'react';
import type { FieldComparison } from './contracts';

const signed = (value: number | null | undefined) => value == null ? 'unavailable' :
  `${value > 0 ? '+' : ''}${value.toFixed(3)} dB`;
const base = import.meta.env.BASE_URL || '/';
const figure = (name: string) => `${base}studio/${name}`;

export function FieldFindings({ comparison, fieldId, onEvidence }: {
  comparison: FieldComparison; fieldId: string; onEvidence: (id: string) => void;
}) {
  const field = comparison.fields.find(item => item.field_id === fieldId);
  if (!field) return <p className="studio-warning">Selected field is absent from the verified comparison.</p>;
  const candidates = [...comparison.fields].sort((a, b) =>
    (b['2026_pre_to_warning_window']?.median_difference_db ?? -Infinity) -
    (a['2026_pre_to_warning_window']?.median_difference_db ?? -Infinity));
  const dates = [...field.observations['2025'], ...field.observations['2026']];
  return <section id="studio-field-change" className="studio-card" aria-label="Verified five-field investigation">
    <p className="studio-kicker">FIELD-SCALE OBSERVATIONS / REAL DATA</p>
    <h2>{fieldId} · observed VH comparison</h2>
    <p className="studio-warning">The {comparison.event_reference.middle_scene_utc.slice(0, 10)} UTC scene was acquired on <strong>{comparison.event_reference.middle_scene_taiwan.slice(0, 16).replace('T', ' ')} Taiwan</strong>,
      inside the CWA land-warning interval. A warning is not a measured field-impact time.
      Only one 2026 observation precedes the warning; a strictly pre-warning change is unavailable.</p>
    <div className="studio-field-metrics">
      <article><small>Pre-warning → warning window</small><strong>{signed(field['2026_pre_to_warning_window']?.median_difference_db)}</strong><span>Descriptive median VH difference</span></article>
      <article><small>Pre-warning → post-warning</small><strong>{signed(field['2026_pre_to_post_warning']?.median_difference_db)}</strong><span>Includes unobserved days</span></article>
      <article><small>Strict pre-warning change</small><strong>Unavailable</strong><span>{field['2026_pre_warning_status']}</span></article>
      <article><small>Spatial support</small><strong>{field.spatial_support.min_valid_pixels} pixels minimum</strong><span>{field.spatial_support.assessment}</span></article>
    </div>
    <p className="studio-muted">Largest warning-window differences: {candidates.slice(0, 2).map(item =>
      `${item.field_id} ${signed(item['2026_pre_to_warning_window']?.median_difference_db)}`).join(' · ')}.
      These are observed radar changes, <strong>not confirmed crop damage</strong>.</p>
    <h3>2025 and 2026 acquisitions · Taiwan time and original UTC</h3>
    <div className="studio-table-scroll"><table><thead><tr><th>Year</th><th>Taiwan acquisition</th><th>Original UTC</th><th>Warning relation</th><th>Median VH</th><th>Valid / interior</th><th>Coverage</th><th>Source scene</th><th>QA</th><th>Evidence ID</th></tr></thead>
      <tbody>{dates.map(row => <tr key={row.evidence_id}>
        <td>{row.acquisition_taiwan.slice(0, 4)}</td><td>{row.acquisition_taiwan}</td><td>{row.acquisition_utc}</td>
        <td><span className={`studio-phase ${row.warning_relation === 'WARNING_WINDOW' ? 'studio-phase-warning' : ''}`}>{row.warning_relation.replaceAll('_', ' ')}</span></td>
        <td>{row.vh_median_db.toFixed(3)} dB</td><td>{row.valid_pixel_count} / {row.interior_pixel_count}</td>
        <td>{(row.valid_coverage_ratio * 100).toFixed(1)}%</td>
        <td title={row.source_scene_id} className="studio-scene-id">{row.source_scene_id}</td>
        <td>{row.qa_flags.length ? row.qa_flags.join(', ') : 'PASS'}</td>
        <td><button type="button" className="studio-link" onClick={() => onEvidence(row.evidence_id)}>{row.evidence_id}</button></td>
      </tr>)}</tbody></table></div>
    <h3>Matched dates across years</h3>
    <p className="studio-muted">Each pair is within six calendar days on the same platform, orbit, burst and processing version. Differences describe separate seasons; they are not a causal baseline.</p>
    <div className="studio-pairings">{field.matched_date_pairs.map(pair => <div key={pair.evidence_ids.join('-')}>
      <span>{pair['2025_utc'].slice(0, 10)} ↔ {pair['2026_utc'].slice(0, 10)}</span>
      <strong>{signed(pair['2026_minus_2025_db'])}</strong>
      <small>{pair.evidence_ids.map(id => <button type="button" className="studio-link" key={id} onClick={() => onEvidence(id)}>{id}</button>)}</small>
    </div>)}</div>
    <h3>Other candidate fields</h3>
    <div className="studio-field-overview">{comparison.fields.map(item => <article key={item.field_id}>
      <strong>{item.field_id}</strong><span>Pre-warning → warning window</span>
      <b>{signed(item['2026_pre_to_warning_window']?.median_difference_db)}</b>
      <small>{item.spatial_support.min_valid_pixels} valid pixels minimum</small>
    </article>)}</div>
    <p className="studio-muted">{comparison.cross_field_pattern.pre_to_warning_increase_count}/5 fields increased in the warning-window observation; {comparison.cross_field_pattern.pre_to_post_increase_count}/5 retained a positive pre-to-post difference. Shared timing does not establish a shared cause. Crop identity and local noise-floor margin remain unverified.</p>
    <details><summary>Verified scientific figures</summary><div className="studio-figure-grid">
      <figure><img src={figure('five_fields_comparison.png')} alt="Real 2025 and 2026 VH curves for five agricultural candidates" /><figcaption>Five-field time series</figcaption></figure>
      {fieldId === 'YL-CAND-01' && <figure><img src={figure('selected_field_comparison.png')} alt="Real detailed VH comparison for YL-CAND-01" /><figcaption>YL-CAND-01 detail</figcaption></figure>}
      <figure><img src={figure('event_timeline.png')} alt="Acquisition times and CWA warning interval in Taiwan time" /><figcaption>Event timeline</figcaption></figure>
      <figure><img src={figure('cross_field_change_comparison.png')} alt="Observed median VH differences across five candidates" /><figcaption>Cross-field differences</figcaption></figure>
    </div></details>
  </section>;
}
