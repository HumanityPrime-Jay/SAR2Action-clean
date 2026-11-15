import React, { useEffect, useState } from 'react';
import { useT } from '../../i18n';
import { useEarthContext } from '../EarthContext';
import { earthApi, type EarthMemoryTimelineResponse } from '../api';

export function EarthMemoryTimeline() {
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
      .then(setData)
      .catch((err) => {
        if ((err as Error).name !== 'AbortError') setError((err as Error).message);
      });
    return () => ctrl.abort();
  }, [eventId, selectedFieldId]);

  const acquisitions = data?.acquisitions ?? [];
  const activeIdx = Math.max(
    0,
    acquisitions.findIndex((a) => a.date_label === timelinePosition),
  );
  const activePoint = acquisitions[activeIdx];

  useEffect(() => {
    if (!isPlayingTimeline || acquisitions.length === 0) return;
    const ms = Math.max(350, Math.round(1200 / playbackSpeed));
    const id = window.setInterval(() => {
      const next = (activeIdx + 1) % acquisitions.length;
      setTimelinePosition(acquisitions[next].date_label);
    }, ms);
    return () => window.clearInterval(id);
  }, [isPlayingTimeline, acquisitions, activeIdx, playbackSpeed, setTimelinePosition]);

  // SVG chart coordinates for VH acquisitions
  const vhPoints = acquisitions
    .map((a, idx) => ({ a, idx }))
    .filter((item) => typeof item.a.metric_value === 'number');

  return (
    <div className="eci-glass">
      <div className="eci-header">
        <div>
          <span className="eci-badge">EARTH MEMORY · TIME MACHINE</span>
          <h3 className="h3" style={{ margin: '6px 0 0', color: '#f8fafc' }}>
            {t('真實衛星觀測時間軸', 'Acquisition-Based Earth Memory')}
          </h3>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <button className="eci-btn" onClick={() => setIsPlayingTimeline(!isPlayingTimeline)} disabled={!acquisitions.length}>
            {isPlayingTimeline ? t('暫停', 'Pause') : t('播放', 'Play')}
          </button>
          <button
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
            style={{ width: 'auto' }}
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
          <p style={{ fontSize: 13, color: '#94a3b8', margin: '6px 0 0' }}>{data.cross_sensor_warnings[0]}</p>
        </div>
      )}

      {acquisitions.length > 0 && (
        <>
          {/* Slider Scrubbing */}
          <div className="eci-card">
            <label htmlFor="eci-timeline-slider" style={{ fontSize: 12, color: '#94a3b8', display: 'block', marginBottom: 6 }}>
              {t('觀測日期滑桿', 'Observation Scrubber')}: <b style={{ color: '#22d3ee' }}>{activePoint?.date_label}</b> ({activePoint?.sensor})
            </label>
            <input
              id="eci-timeline-slider"
              type="range"
              min={0}
              max={acquisitions.length - 1}
              value={activeIdx}
              onChange={(e) => setTimelinePosition(acquisitions[parseInt(e.target.value, 10)].date_label)}
              style={{ width: '100%' }}
            />
          </div>

          {/* Synchronized SVG Temporal Backscatter Chart (gaps shown as dashed lines) */}
          <div className="eci-card">
            <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 6 }}>
              VH Backscatter (dB) · NASA OPERA RTC-S1 · {selectedFieldId} (Dashed = NO OBSERVATION gap)
            </div>
            <svg viewBox="0 0 520 120" style={{ width: '100%', height: 120, background: 'rgba(6,11,20,0.6)', borderRadius: 8 }}>
              {vhPoints.length > 1 &&
                vhPoints.slice(0, -1).map((pt, i) => {
                  const next = vhPoints[i + 1];
                  const x1 = 30 + (pt.idx / Math.max(acquisitions.length - 1, 1)) * 460;
                  const x2 = 30 + (next.idx / Math.max(acquisitions.length - 1, 1)) * 460;
                  const y1 = 95 - (((pt.a.metric_value as number) + 22) / 16) * 75;
                  const y2 = 95 - (((next.a.metric_value as number) + 22) / 16) * 75;
                  return (
                    <line
                      key={pt.a.acquisition_id}
                      x1={x1}
                      y1={y1}
                      x2={x2}
                      y2={y2}
                      stroke="#22d3ee"
                      strokeWidth="2"
                      strokeDasharray="5 4"
                    />
                  );
                })}
              {vhPoints.map((pt) => {
                const cx = 30 + (pt.idx / Math.max(acquisitions.length - 1, 1)) * 460;
                const cy = 95 - (((pt.a.metric_value as number) + 22) / 16) * 75;
                const isActive = pt.idx === activeIdx;
                return (
                  <g key={pt.a.acquisition_id}>
                    <circle cx={cx} cy={cy} r={isActive ? 6 : 4} fill={isActive ? '#fb923c' : '#22d3ee'} />
                    <text x={cx} y={112} textAnchor="middle" fill="#94a3b8" fontSize="9">
                      {pt.a.date_label.slice(5)}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Active Acquisition Metadata */}
          {activePoint && (
            <div className="eci-card active">
              <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6 }}>
                <strong>{activePoint.acquisition_id}</strong>
                <span className={`eci-badge ${activePoint.compatible_with_baseline ? '' : 'warn'}`}>{activePoint.qa_status}</span>
              </div>
              <div style={{ fontSize: 12.5, color: '#cbd5e1', marginTop: 6 }}>
                UTC: <code>{activePoint.acquisition_time_utc}</code> · Local: <code>{activePoint.acquisition_time_local}</code>
              </div>
              <div style={{ fontSize: 12.5, color: '#cbd5e1', marginTop: 4 }}>
                Sensor: {activePoint.sensor} ({activePoint.polarization}) · Version: {activePoint.product_version} · Phase:{' '}
                <b>{activePoint.warning_phase}</b>
              </div>
              {activePoint.metric_value !== null && activePoint.metric_value !== undefined && (
                <div className="eci-metric" style={{ marginTop: 6 }}>
                  {activePoint.metric_value} {activePoint.metric_unit}
                </div>
              )}
              {activePoint.compatibility_note && (
                <div style={{ fontSize: 12, color: '#fdba74', marginTop: 4 }}>{activePoint.compatibility_note}</div>
              )}
            </div>
          )}

          {/* Explicit NO OBSERVATION Gaps & Cross-Sensor Warnings */}
          <div className="eci-card">
            <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>
              NO OBSERVATION Gaps ({data?.observation_gaps.length ?? 0}) & QA Warnings
            </div>
            {(data?.cross_sensor_warnings || []).map((w, i) => (
              <div key={i} style={{ fontSize: 12, color: '#fdba74', marginTop: 3 }}>
                • {w}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
