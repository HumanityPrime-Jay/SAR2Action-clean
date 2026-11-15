import React, { useEffect, useState } from 'react';
import { useT } from '../../i18n';
import { useEarthContext } from '../EarthContext';
import { earthApi, type EarthMemoryTimelineResponse } from '../api';
import { IndicatorTooltip } from './IndicatorTooltip';

export function EarthMemoryTimeline({ compactDock = false }: { compactDock?: boolean }) {
  const t = useT();
  const {
    eventId,
    selectedFieldId,
    timelinePosition,
    setTimelinePosition,
    isPlayingTimeline,
    setIsPlayingTimeline,
    playbackSpeed,
    setPlaybackSpeed,
  } = useEarthContext();

  const [data, setData] = useState<EarthMemoryTimelineResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    setError(null);
    earthApi
      .getTimeline(eventId, selectedFieldId, ctrl.signal)
      .then((res) => {
        setData(res);
        if (res?.acquisitions?.length && !res.acquisitions.some((a) => a.date_label === timelinePosition)) {
          setTimelinePosition(res.acquisitions[0].date_label);
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') setError(String(err.message || err));
      });
    return () => ctrl.abort();
  }, [eventId, selectedFieldId, setTimelinePosition, timelinePosition]);

  const acquisitions = data?.acquisitions ?? [];
  const activeIdx = Math.max(
    0,
    acquisitions.findIndex((a) => a.date_label === timelinePosition),
  );
  const activePoint = acquisitions[activeIdx] ?? acquisitions[0];

  useEffect(() => {
    if (!isPlayingTimeline || acquisitions.length <= 1) return;
    const intervalMs = Math.max(400, Math.round(1400 / playbackSpeed));
    const timer = window.setInterval(() => {
      const nextIdx = (activeIdx + 1) % acquisitions.length;
      setTimelinePosition(acquisitions[nextIdx].date_label);
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [isPlayingTimeline, acquisitions, activeIdx, playbackSpeed, setTimelinePosition]);

  // Build SVG points for temporal chart
  const numericPoints = acquisitions
    .map((a, idx) => ({ a, idx, val: typeof a.metric_value === 'number' ? a.metric_value : null }))
    .filter((p): p is { a: (typeof acquisitions)[0]; idx: number; val: number } => p.val !== null);

  if (compactDock) {
    return (
      <div className="eci-glass" style={{ padding: '9px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="eci-badge">EARTH MEMORY</span>
            <strong style={{ fontSize: 12.5, color: '#f8fafc' }}>
              {activePoint ? `${activePoint.date_label} · ${activePoint.sensor}` : t('無時間序列', 'No Timeline')}
            </strong>
            {activePoint?.warning_phase === 'DURING_TYPHOON_WARNING' && (
              <span className="eci-badge warn">DURING_TYPHOON_WARNING</span>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1, minWidth: 200 }}>
            <button
              type="button"
              className="eci-btn"
              style={{ padding: '4px 10px', minHeight: 28, fontSize: 11.5 }}
              onClick={() => setIsPlayingTimeline(!isPlayingTimeline)}
              disabled={!acquisitions.length}
            >
              {isPlayingTimeline ? t('暫停', 'Pause') : t('播放', 'Play')}
            </button>
            <input
              type="range"
              aria-label="Bottom timeline scrubber"
              min={0}
              max={Math.max(0, acquisitions.length - 1)}
              value={activeIdx}
              onChange={(e) => {
                const pt = acquisitions[parseInt(e.target.value, 10)];
                if (pt) setTimelinePosition(pt.date_label);
              }}
              style={{ flex: 1 }}
            />
            <span className="mono" style={{ fontSize: 11, color: '#67e8f9' }}>
              {activePoint?.metric_value !== null && activePoint?.metric_value !== undefined
                ? `${activePoint.metric_value} ${activePoint.metric_unit || 'dB'}`
                : 'QA'}
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="eci-glass">
      <div className="eci-header">
        <div>
          <span className="eci-badge">EARTH MEMORY · TIME MACHINE</span>
          <h3 className="h3" style={{ margin: '5px 0 0', fontSize: 16, color: '#f8fafc' }}>
            {t('真實衛星觀測時間軸', 'Acquisition-Based Earth Memory')}
            <IndicatorTooltip indicatorKey="vh_change" />
          </h3>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <button
            type="button"
            className="eci-btn"
            onClick={() => setIsPlayingTimeline(!isPlayingTimeline)}
            disabled={!acquisitions.length}
          >
            {isPlayingTimeline ? t('暫停', 'Pause') : t('播放', 'Play')}
          </button>
          <button
            type="button"
            className="eci-btn secondary"
            onClick={() => {
              setIsPlayingTimeline(false);
              if (acquisitions[0]) setTimelinePosition(acquisitions[0].date_label);
            }}
            disabled={!acquisitions.length}
          >
            {t('重設', 'Restart')}
          </button>
          <select
            className="eci-input"
            style={{ width: 'auto', padding: '4px 8px' }}
            aria-label={t('播放速度', 'Playback speed')}
            value={playbackSpeed}
            onChange={(e) => setPlaybackSpeed(parseFloat(e.target.value))}
          >
            <option value={0.5}>0.5x</option>
            <option value={1}>1x</option>
            <option value={2}>2x</option>
          </select>
        </div>
      </div>

      {error && <p className="eci-badge warn">{error}</p>}

      {data && acquisitions.length === 0 && (
        <div className="eci-card">
          <strong>{data.provenance.data_status}</strong>
          <p style={{ fontSize: 12.5, color: '#94a3b8', margin: '6px 0 0' }}>{data.cross_sensor_warnings[0]}</p>
        </div>
      )}

      {acquisitions.length > 0 && (
        <>
          {/* Video-Editor-Grade Date Node Strip with Explicit Gap Markers */}
          <div className="eci-card" style={{ padding: '10px 12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <label htmlFor="eci-timeline-slider" style={{ fontSize: 12, color: '#cbd5e1' }}>
                {t('觀測日期滑桿', 'Observation Scrubber')}: <b style={{ color: '#22d3ee' }}>{activePoint?.date_label}</b> ({activePoint?.sensor})
              </label>
              <span className="eci-badge muted">{acquisitions.length} Real Passes</span>
            </div>
            <input
              id="eci-timeline-slider"
              type="range"
              min={0}
              max={acquisitions.length - 1}
              value={activeIdx}
              onChange={(e) => setTimelinePosition(acquisitions[parseInt(e.target.value, 10)].date_label)}
              style={{ width: '100%', marginBottom: 8 }}
            />
            <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', alignItems: 'center' }}>
              {acquisitions.map((acq, i) => (
                <React.Fragment key={acq.acquisition_id}>
                  <button
                    type="button"
                    className="eci-tab"
                    aria-selected={acq.date_label === activePoint?.date_label}
                    onClick={() => setTimelinePosition(acq.date_label)}
                    style={{ padding: '4px 8px', fontSize: 11 }}
                  >
                    {acq.date_label}
                    {acq.warning_phase === 'DURING_TYPHOON_WARNING' ? ' ⚡' : ''}
                  </button>
                  {i === 0 && (data?.observation_gaps?.length ?? 0) > 0 && (
                    <span className="eci-badge warn" style={{ fontSize: 9.5 }} title={data?.observation_gaps[0]?.note}>
                      GAP: NO OBSERVATION
                    </span>
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>

          {/* Synchronized SVG Temporal Backscatter Chart with Full Metadata Header */}
          <div className="eci-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 4, fontSize: 11, color: '#94a3b8', marginBottom: 6 }}>
              <span>
                <b style={{ color: '#e2e8f0' }}>{t('多時序雷達後向散射曲線', 'Temporal Radar Backscatter Curve')}</b> · Unit: <code>dB</code>
              </span>
              <span>Source: OPERA_RTC_S1 / NISAR · QA: {activePoint?.qa_status}</span>
            </div>
            <svg viewBox="0 0 380 120" style={{ width: '100%', height: 116, display: 'block' }} role="img" aria-label="Temporal Backscatter Chart">
              <line x1="28" y1="22" x2="364" y2="22" stroke="rgba(148,163,184,0.16)" strokeDasharray="3 3" />
              <line x1="28" y1="60" x2="364" y2="60" stroke="rgba(148,163,184,0.22)" />
              <line x1="28" y1="96" x2="364" y2="96" stroke="rgba(148,163,184,0.16)" strokeDasharray="3 3" />
              <text x="4" y="25" fill="#64748b" fontSize="9">+8dB</text>
              <text x="4" y="63" fill="#64748b" fontSize="9">-10dB</text>
              <text x="4" y="99" fill="#64748b" fontSize="9">-20dB</text>

              {numericPoints.map((pt, i) => {
                const x1 = 42 + (pt.idx / Math.max(1, acquisitions.length - 1)) * 308;
                const y1 = 88 - ((pt.val + 20) / 30) * 65;
                const next = numericPoints[i + 1];
                if (!next) return null;
                const x2 = 42 + (next.idx / Math.max(1, acquisitions.length - 1)) * 308;
                const y2 = 88 - ((next.val + 20) / 30) * 65;
                return (
                  <line
                    key={`line-${pt.a.acquisition_id}`}
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke="#22d3ee"
                    strokeWidth="2.2"
                    strokeDasharray={next.idx - pt.idx > 1 ? '4 4' : undefined}
                  />
                );
              })}

              {numericPoints.map((pt) => {
                const cx = 42 + (pt.idx / Math.max(1, acquisitions.length - 1)) * 308;
                const cy = 88 - ((pt.val + 20) / 30) * 65;
                const isActive = pt.a.date_label === activePoint?.date_label;
                return (
                  <g key={pt.a.acquisition_id} style={{ cursor: 'pointer' }} onClick={() => setTimelinePosition(pt.a.date_label)}>
                    {isActive && <circle cx={cx} cy={cy} r={10} fill="rgba(251, 146, 60, 0.25)" />}
                    <circle cx={cx} cy={cy} r={isActive ? 5.5 : 4} fill={isActive ? '#fb923c' : '#22d3ee'} />
                    <text x={cx} y={113} textAnchor="middle" fill={isActive ? '#f8fafc' : '#94a3b8'} fontSize="9.5">
                      {pt.a.date_label.slice(5)}
                    </text>
                  </g>
                );
              })}
            </svg>
            <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
              Limitation: Dashed segments indicate <code>NO_OBSERVATION</code> intervals; cross-CRID points are excluded from differencing.
            </div>
          </div>

          {/* Active Acquisition Metadata */}
          {activePoint && (
            <div className="eci-card active">
              <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6 }}>
                <strong>{activePoint.acquisition_id}</strong>
                <span className={`eci-badge ${activePoint.compatible_with_baseline ? 'ok' : 'warn'}`}>{activePoint.qa_status}</span>
              </div>
              <div style={{ fontSize: 12, color: '#cbd5e1', marginTop: 5 }}>
                UTC: <code>{activePoint.acquisition_time_utc}</code> · Local: <code>{activePoint.acquisition_time_local}</code>
              </div>
              <div style={{ fontSize: 12, color: '#cbd5e1', marginTop: 3 }}>
                Sensor: {activePoint.sensor} ({activePoint.polarization}) · Version: {activePoint.product_version} · Phase:{' '}
                <b style={{ color: activePoint.warning_phase === 'DURING_TYPHOON_WARNING' ? '#fb923c' : '#e2e8f0' }}>
                  {activePoint.warning_phase}
                </b>
              </div>
              {activePoint.metric_value !== null && activePoint.metric_value !== undefined && (
                <div className="eci-metric" style={{ marginTop: 5 }}>
                  {activePoint.metric_value > 0 ? `+${activePoint.metric_value}` : activePoint.metric_value} {activePoint.metric_unit}
                </div>
              )}
              {activePoint.compatibility_note && (
                <div style={{ fontSize: 11.5, color: '#fdba74', marginTop: 4 }}>{activePoint.compatibility_note}</div>
              )}
            </div>
          )}

          {/* Explicit NO OBSERVATION Gaps & Cross-Sensor Warnings */}
          <div className="eci-card">
            <div style={{ fontSize: 12, fontWeight: 600, color: '#cbd5e1', marginBottom: 4 }}>
              NO OBSERVATION Gaps ({data?.observation_gaps.length ?? 0}) & QA Warnings
              <IndicatorTooltip indicatorKey="crid_compat" />
            </div>
            {(data?.observation_gaps || []).map((g, idx) => (
              <div key={idx} style={{ fontSize: 11.5, color: '#94a3b8', marginTop: 2 }}>
                • [{g.status}] {g.start_utc.slice(0, 10)} → {g.end_utc.slice(0, 10)} ({g.gap_days}d): {g.note}
              </div>
            ))}
            {(data?.cross_sensor_warnings || []).map((w, i) => (
              <div key={i} style={{ fontSize: 11.5, color: '#fdba74', marginTop: 3 }}>
                • {w}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
