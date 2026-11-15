import React, { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useT } from '../../i18n';
import { useEarthContext } from '../EarthContext';
import { earthApi, type GlobalEventRecord } from '../api';

export function EarthChangeExplorer({ onReturnToGlobe }: { onReturnToGlobe?: () => void }) {
  const t = useT();
  const {
    eventId,
    setEventId,
    selectedFieldId,
    setSelectedFieldId,
    selectedLens,
    activeLayers,
    cameraTarget,
    flyToRegion,
    setInvestigationResult,
    evidenceIds,
  } = useEarthContext();

  const [events, setEvents] = useState<GlobalEventRecord[]>([]);
  const [eventTypes, setEventTypes] = useState<string[]>([]);
  const [filterType, setFilterType] = useState<string>('');
  const [searchQ, setSearchQ] = useState<string>('');
  const [investigating, setInvestigating] = useState(false);
  const [invStatus, setInvStatus] = useState<string>('IDLE');
  const [invResult, setInvResult] = useState<Record<string, unknown> | null>(null);
  const [animPaused, setAnimPaused] = useState(false);
  const [sarOpacity, setSarOpacity] = useState(0.75);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const invAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    earthApi
      .listEvents(filterType || undefined, searchQ || undefined, ctrl.signal)
      .then((res) => {
        setEvents(res?.events || []);
        setEventTypes(res?.supported_event_types || []);
      })
      .catch(() => {});
    return () => ctrl.abort();
  }, [filterType, searchQ]);

  const activeEvent = events.find((e) => e.event_id === eventId) || events[0];

  // Initialize MapLibre GL map with real committed parcel GeoJSON
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;
    try {
      const map = new maplibregl.Map({
        container: mapContainerRef.current,
        style: {
          version: 8,
          sources: {
            osm: {
              type: 'raster',
              tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
              tileSize: 256,
              attribution: '© OpenStreetMap',
            },
          },
          layers: [{ id: 'osm-base', type: 'raster', source: 'osm', paint: { 'raster-opacity': 0.52 } }],
        },
        center: [120.1945, 23.7025],
        zoom: 12.2,
      });
      map.on('load', () => {
        map.addSource('champi-fields', {
          type: 'geojson',
          data: '/studio/fields.geojson',
        });
        map.addLayer({
          id: 'champi-fields-fill',
          type: 'fill',
          source: 'champi-fields',
          paint: {
            'fill-color': ['case', ['==', ['get', 'field_id'], 'YL-CAND-03'], '#fb923c', '#22d3ee'],
            'fill-opacity': 0.45,
          },
        });
        map.addLayer({
          id: 'champi-fields-line',
          type: 'line',
          source: 'champi-fields',
          paint: { 'line-color': '#f8fafc', 'line-width': 2 },
        });
        map.on('click', 'champi-fields-fill', (ev: maplibregl.MapLayerMouseEvent) => {
          const fid = ev.features?.[0]?.properties?.field_id;
          if (typeof fid === 'string') setSelectedFieldId(fid);
        });
      });
      mapRef.current = map;
    } catch {
      // Headless / WebGL-less fallback
    }
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [setSelectedFieldId]);

  // Sync camera Fly-To when cameraTarget changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !cameraTarget || animPaused) return;
    try {
      map.flyTo({ center: [cameraTarget.lon, cameraTarget.lat], zoom: cameraTarget.zoom, duration: 900 });
    } catch {
      // ignore in non-WebGL test env
    }
  }, [cameraTarget, animPaused]);

  // Sync Reality Lens / selected field styling on MapLibre
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const lensColor =
      selectedLens === 'OBSERVED'
        ? '#22d3ee'
        : selectedLens === 'HYPOTHESES'
          ? '#fb923c'
          : selectedLens === 'UNKNOWN'
            ? '#94a3b8'
            : '#34d399';
    try {
      if (map.getLayer('champi-fields-fill')) {
        map.setPaintProperty('champi-fields-fill', 'fill-color', [
          'case',
          ['==', ['get', 'field_id'], selectedFieldId],
          '#f97316',
          lensColor,
        ]);
        map.setPaintProperty('champi-fields-fill', 'fill-opacity', activeLayers.includes('vh-change') ? sarOpacity * 0.65 : 0.25);
      }
    } catch {
      // ignore if style not ready
    }
  }, [selectedLens, selectedFieldId, activeLayers, sarOpacity]);

  const selectEvent = (ev: GlobalEventRecord) => {
    setEventId(ev.event_id);
    flyToRegion(ev.center_lon, ev.center_lat, ev.default_zoom, ev.region);
  };

  const runInvestigation = async () => {
    invAbortRef.current?.abort();
    const ctrl = new AbortController();
    invAbortRef.current = ctrl;
    setInvestigating(true);
    setInvStatus('RUNNING_SCIENTIFIC_AGENT');
    try {
      const resp = await fetch('/api/investigation/v3/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: ctrl.signal,
        body: JSON.stringify({
          case_id: 'CHAMPI-YUNLIN-TAIXI',
          field_id: selectedFieldId,
          mode: 'deterministic',
          question: `Investigate observed backscatter change on ${selectedFieldId}`,
        }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = (await resp.json()) as Record<string, unknown>;
      setInvResult(data);
      setInvStatus('COMPLETED');
      const ids = Array.isArray(data.evidence_ids) ? (data.evidence_ids as string[]) : [`EV-OPERA-S1-${selectedFieldId}-VH`];
      setInvestigationResult(String(data.investigation_id || 'INV-V3'), ids);
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setInvStatus('FAILED_OR_UNAVAILABLE');
      }
    } finally {
      setInvestigating(false);
    }
  };

  const cancelInvestigation = () => {
    invAbortRef.current?.abort();
    setInvestigating(false);
    setInvStatus('CANCELLED');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Global Event Discovery */}
      <div className="eci-glass">
        <div className="eci-header">
          <div>
            <span className="eci-badge">GLOBAL EVENT CATALOG · {events.length} EVENTS</span>
            <h2 className="h3" style={{ margin: '6px 0 0', color: '#f8fafc' }}>
              {t('地球變化鑑識與事件探索', 'Earth Change Forensics & Event Explorer')}
            </h2>
          </div>
          {onReturnToGlobe && (
            <button className="eci-btn secondary" onClick={onReturnToGlobe}>
              ← {t('返回 3D 地球', 'Return to 3D Globe')}
            </button>
          )}
        </div>

        <div className="eci-grid-2" style={{ marginBottom: 10 }}>
          <input
            className="eci-input"
            aria-label={t('搜尋全球事件', 'Search global events')}
            placeholder={t('搜尋國家、地區、災害類型…', 'Search country, region, event type…')}
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
          />
          <select
            className="eci-input"
            aria-label={t('事件類型篩選', 'Filter by event type')}
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
          >
            <option value="">{t('全部事件類型 (8 類)', 'All Event Types (8)')}</option>
            {eventTypes.map((et) => (
              <option key={et} value={et}>
                {et}
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 210, overflowY: 'auto' }}>
          {events.map((ev) => (
            <button
              key={ev.event_id}
              type="button"
              onClick={() => selectEvent(ev)}
              className={`eci-card${ev.event_id === eventId ? ' active' : ''}`}
              style={{ textAlign: 'left', cursor: 'pointer', color: '#f1f5f9', width: '100%' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                <strong>{t(ev.event_name_zh, ev.event_name)}</strong>
                <span className={`eci-badge ${ev.change_analysis_status === 'CHANGE_ANALYZED' ? '' : 'muted'}`}>
                  {ev.change_analysis_status}
                </span>
              </div>
              <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>
                {ev.country} · {ev.event_type} · {ev.sensor} · {ev.demo_mode}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Live MapLibre Stage */}
      <div className="eci-map-stage">
        <div ref={mapContainerRef} className="eci-map-canvas" aria-label="Earth Change Interactive Map" />
        <div className="eci-map-hud">
          <div className="eci-glass" style={{ padding: '8px 12px', display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <span className="eci-badge">{selectedLens}</span>
            <span className="mono" style={{ fontSize: 12 }}>
              {activeEvent?.region || eventId} · {selectedFieldId}
            </span>
            <label style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
              SAR
              <input
                type="range"
                min={0.1}
                max={1}
                step={0.05}
                value={sarOpacity}
                onChange={(e) => setSarOpacity(parseFloat(e.target.value))}
                aria-label="SAR layer opacity"
              />
            </label>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="eci-btn secondary" onClick={() => setAnimPaused((p) => !p)}>
              {animPaused ? t('恢復動畫', 'Resume Camera') : t('暫停動畫', 'Pause Camera')}
            </button>
            <button
              className="eci-btn"
              onClick={runInvestigation}
              disabled={investigating || activeEvent?.change_analysis_status !== 'CHANGE_ANALYZED'}
            >
              {investigating ? t('調查中…', 'Investigating…') : t('啟動科學調查 (Investigate)', 'Investigate')}
            </button>
            {investigating && (
              <button className="eci-btn secondary" onClick={cancelInvestigation}>
                {t('取消', 'Cancel')}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Scientific Result Card & Source Provenance Panel */}
      <div className="eci-glass">
        <div className="eci-header">
          <span className="eci-badge">{invStatus}</span>
          <span className="eci-badge warn">OBSERVED ≠ CONFIRMED DAMAGE</span>
        </div>
        <div className="eci-grid-2">
          <div className="eci-card">
            <div style={{ fontSize: 12, color: '#94a3b8' }}>Selected Parcel ({selectedFieldId})</div>
            <div className="eci-metric">{selectedFieldId === 'YL-CAND-03' ? '+7.55336 dB' : 'OBSERVED'}</div>
            <div style={{ fontSize: 12, color: '#cbd5e1', marginTop: 4 }}>
              Status: <b>OBSERVED</b> · Typhoon Cause: <b>UNRESOLVED</b> · Crop Damage: <b>NOT CONFIRMED</b>
            </div>
          </div>
          <div className="eci-card">
            <div style={{ fontSize: 12, color: '#94a3b8' }}>Source Provenance & Evidence Ledger</div>
            <div style={{ fontSize: 12, color: '#67e8f9', marginTop: 4, fontFamily: 'var(--f-mono, monospace)' }}>
              {evidenceIds.slice(0, 4).join(', ')}
            </div>
            {invResult && (
              <div style={{ fontSize: 12, color: '#a7f3d0', marginTop: 4 }}>
                V3 Investigation completed: {String(invResult.execution_mode || 'DETERMINISTIC')}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
