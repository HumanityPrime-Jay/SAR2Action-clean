import React, { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useT } from '../../i18n';
import { useEarthContext } from '../EarthContext';
import { earthApi, type GlobalEventRecord, type LensMode } from '../api';
import { IndicatorTooltip } from './IndicatorTooltip';

const PARCEL_IDS = ['YL-CAND-01', 'YL-CAND-02', 'YL-CAND-03', 'YL-CAND-04', 'YL-CAND-05'];

export function EarthChangeExplorer({
  onReturnToGlobe,
  mode = 'combined',
}: {
  onReturnToGlobe?: () => void;
  mode?: 'canvas' | 'controls' | 'combined';
}) {
  const t = useT();
  const {
    eventId,
    setEventId,
    selectedFieldId,
    setSelectedFieldId,
    selectedLens,
    setSelectedLens,
    activeLayers,
    toggleLayer,
    sarOpacity,
    setSarOpacity,
    cameraTarget,
    flyToRegion,
    setInvestigationResult,
    evidenceIds,
    pushActionFeedback,
  } = useEarthContext();

  const [events, setEvents] = useState<GlobalEventRecord[]>([]);
  const [eventTypes, setEventTypes] = useState<string[]>([]);
  const [filterType, setFilterType] = useState<string>('');
  const [searchQ, setSearchQ] = useState<string>('');
  const [investigating, setInvestigating] = useState(false);
  const [invStatus, setInvStatus] = useState<string>('IDLE');
  const [invResult, setInvResult] = useState<Record<string, unknown> | null>(null);
  const [animPaused, setAnimPaused] = useState(false);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const invAbortRef = useRef<AbortController | null>(null);

  const showCanvas = mode === 'canvas' || mode === 'combined';
  const showControls = mode === 'controls' || mode === 'combined';

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

  const activeEvent = (events || []).find((e) => e.event_id === eventId) || events[0];

  // Initialize MapLibre GL map with real committed parcel GeoJSON & Global Event Markers
  useEffect(() => {
    if (!showCanvas || !mapContainerRef.current || mapRef.current) return;
    let resizeObserver: ResizeObserver | null = null;
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
          layers: [
            {
              id: 'osm-base',
              type: 'raster',
              source: 'osm',
              paint: {
                'raster-opacity': 0.62,
                'raster-saturation': -0.35,
                'raster-contrast': 0.15,
              },
            },
          ],
        },
        center: [120.1945, 23.7025],
        zoom: 12.6,
      });

      if (typeof ResizeObserver !== 'undefined') {
        resizeObserver = new ResizeObserver(() => {
          map.resize();
        });
        resizeObserver.observe(mapContainerRef.current);
      }

      map.on('load', () => {
        map.resize();
        map.addSource('champi-fields', {
          type: 'geojson',
          data: '/studio/fields.geojson',
        });
        map.addLayer({
          id: 'champi-fields-fill',
          type: 'fill',
          source: 'champi-fields',
          paint: {
            'fill-color': ['case', ['==', ['get', 'field_id'], 'YL-CAND-03'], '#f97316', '#22d3ee'],
            'fill-opacity': 0.52,
          },
        });
        map.addLayer({
          id: 'champi-fields-line',
          type: 'line',
          source: 'champi-fields',
          paint: {
            'line-color': ['case', ['==', ['get', 'field_id'], 'YL-CAND-03'], '#ffedd5', '#ecfeff'],
            'line-width': ['case', ['==', ['get', 'field_id'], 'YL-CAND-03'], 3, 1.8],
          },
        });
        map.on('click', 'champi-fields-fill', (ev: maplibregl.MapLayerMouseEvent) => {
          const fid = ev.features?.[0]?.properties?.field_id;
          if (typeof fid === 'string') {
            setSelectedFieldId(fid);
            pushActionFeedback([`Selected Parcel ${fid}`]);
          }
        });
      });

      mapRef.current = map;
    } catch {
      // Headless / WebGL-less fallback
    }
    return () => {
      resizeObserver?.disconnect();
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [showCanvas, setSelectedFieldId, pushActionFeedback]);

  // Sync Global Event Markers on MapLibre whenever events load
  useEffect(() => {
    const map = mapRef.current;
    if (!showCanvas || !map || !events.length) return;
    const syncEventPoints = () => {
      try {
        const geojson = {
          type: 'FeatureCollection' as const,
          features: events
            .filter((e) => typeof e.center_lon === 'number' && typeof e.center_lat === 'number')
            .map((e) => ({
              type: 'Feature' as const,
              geometry: { type: 'Point' as const, coordinates: [e.center_lon, e.center_lat] },
              properties: {
                event_id: e.event_id,
                status: e.change_analysis_status,
                name: e.event_name,
              },
            })),
        };
        const existing = map.getSource('global-events-src') as maplibregl.GeoJSONSource | undefined;
        if (existing) {
          existing.setData(geojson);
        } else if (map.isStyleLoaded()) {
          map.addSource('global-events-src', { type: 'geojson', data: geojson });
          map.addLayer({
            id: 'global-events-halo',
            type: 'circle',
            source: 'global-events-src',
            paint: {
              'circle-radius': ['case', ['==', ['get', 'event_id'], eventId], 14, 9],
              'circle-color': ['case', ['==', ['get', 'status'], 'CHANGE_ANALYZED'], '#22d3ee', '#fb923c'],
              'circle-opacity': 0.25,
            },
          });
          map.addLayer({
            id: 'global-events-dot',
            type: 'circle',
            source: 'global-events-src',
            paint: {
              'circle-radius': ['case', ['==', ['get', 'event_id'], eventId], 6, 4.5],
              'circle-color': ['case', ['==', ['get', 'status'], 'CHANGE_ANALYZED'], '#22d3ee', '#fb923c'],
              'circle-stroke-width': 2,
              'circle-stroke-color': '#040812',
            },
          });
        }
      } catch {
        // ignore if style not yet ready
      }
    };
    if (map.isStyleLoaded()) syncEventPoints();
    else map.once('load', syncEventPoints);
  }, [showCanvas, events, eventId]);

  // Sync camera Fly-To when cameraTarget changes
  useEffect(() => {
    const map = mapRef.current;
    if (!showCanvas || !map || !cameraTarget || animPaused) return;
    try {
      const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
      map.flyTo({
        center: [cameraTarget.lon, cameraTarget.lat],
        zoom: cameraTarget.zoom,
        duration: reduced ? 0 : 1100,
        essential: true,
      });
    } catch {
      // ignore in non-WebGL test env
    }
  }, [showCanvas, cameraTarget, animPaused]);

  // Sync Reality Lens / selected field styling on MapLibre
  useEffect(() => {
    const map = mapRef.current;
    if (!showCanvas || !map || !map.isStyleLoaded()) return;
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
        map.setPaintProperty(
          'champi-fields-fill',
          'fill-opacity',
          activeLayers.includes('vh-change') ? sarOpacity * 0.68 : 0.18,
        );
      }
      if (map.getLayer('champi-fields-line')) {
        map.setPaintProperty('champi-fields-line', 'line-width', [
          'case',
          ['==', ['get', 'field_id'], selectedFieldId],
          3.2,
          1.6,
        ]);
      }
    } catch {
      // ignore if style not ready
    }
  }, [showCanvas, selectedLens, selectedFieldId, activeLayers, sarOpacity]);

  const selectEvent = (ev: GlobalEventRecord) => {
    setEventId(ev.event_id);
    flyToRegion(ev.center_lon, ev.center_lat, ev.default_zoom, ev.region);
    pushActionFeedback([`Selected ${ev.event_name || ev.event_id}`]);
  };

  const runInvestigation = async () => {
    invAbortRef.current?.abort();
    const ctrl = new AbortController();
    invAbortRef.current = ctrl;
    setInvestigating(true);
    setInvStatus('RUNNING_SCIENTIFIC_AGENT');
    pushActionFeedback([`Running Scientific Agent V3 on ${selectedFieldId}…`]);
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

  if (mode === 'canvas') {
    return (
      <div className="eci-canvas-stage" data-lens={selectedLens}>
        <div ref={mapContainerRef} className="eci-map-canvas" aria-label="Earth Change Interactive Map" />
        <div className="eci-canvas-vignette" />

        {/* Floating Map Center Telemetry & Camera Controls */}
        <div className="eci-map-center-hud">
          <div className="eci-glass" style={{ padding: '7px 12px', display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <span className="eci-badge">{selectedLens}</span>
            <span className="mono" style={{ fontSize: 12, color: '#f8fafc', fontWeight: 600 }}>
              {activeEvent?.region || 'Taixi Township, Yunlin'} · {selectedFieldId}
            </span>
            <span className="eci-badge warn">
              {selectedFieldId === 'YL-CAND-03' ? '+7.55336 dB OBSERVED' : 'OBSERVED ≠ CONFIRMED DAMAGE'}
            </span>
            <label style={{ fontSize: 11.5, display: 'flex', alignItems: 'center', gap: 5, color: '#cbd5e1' }}>
              SAR
              <input
                type="range"
                min={0.1}
                max={1}
                step={0.05}
                value={sarOpacity}
                onChange={(e) => setSarOpacity(parseFloat(e.target.value))}
                aria-label="SAR layer opacity"
                style={{ width: 68 }}
              />
            </label>
          </div>

          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <button
              type="button"
              className="eci-btn secondary"
              onClick={() => flyToRegion(118.5, 22.5, 3.2, 'Global Overview')}
              title={t('鳥瞰全球事件分佈', 'Zoom out to Global Event View')}
            >
              🌐 {t('全球視野', 'Global View')}
            </button>
            <button
              type="button"
              className="eci-btn secondary"
              onClick={() => flyToRegion(120.1945, 23.7025, 13.1, 'Taixi, Yunlin')}
            >
              🎯 {t('聚焦雲林台西', 'Focus Taixi AOI')}
            </button>
            <button type="button" className="eci-btn secondary" onClick={() => setAnimPaused((p) => !p)}>
              {animPaused ? t('恢復鏡頭', 'Resume Camera') : t('鎖定鏡頭', 'Pause Camera')}
            </button>
            <button
              type="button"
              className="eci-btn"
              onClick={runInvestigation}
              disabled={investigating || (activeEvent && activeEvent.change_analysis_status !== 'CHANGE_ANALYZED')}
            >
              {investigating ? t('調查中…', 'Investigating…') : t('啟動科學調查', 'Investigate')}
            </button>
            {investigating && (
              <button type="button" className="eci-btn secondary" onClick={cancelInvestigation}>
                {t('取消', 'Cancel')}
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Global Event Catalog Card */}
      {showControls && (
        <div className="eci-glass">
          <div className="eci-header">
            <div>
              <span className="eci-badge">GLOBAL EVENT CATALOG · {events.length} EVENTS</span>
              <h2 className="h3" style={{ margin: '5px 0 0', fontSize: 16, color: '#f8fafc' }}>
                {t('地球變化鑑識與事件探索', 'Earth Change Forensics & Event Explorer')}
              </h2>
            </div>
            {onReturnToGlobe && (
              <button type="button" className="eci-btn secondary" style={{ fontSize: 11.5, padding: '4px 9px' }} onClick={onReturnToGlobe}>
                ← {t('返回 3D 地球', 'Return to 3D Globe')}
              </button>
            )}
          </div>

          <div className="eci-grid-2" style={{ marginBottom: 8 }}>
            <input
              className="eci-input"
              aria-label={t('搜尋全球事件', 'Search global events')}
              placeholder={t('搜尋國家、地區、災害…', 'Search country, region, event type…')}
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

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 195, overflowY: 'auto', paddingRight: 2 }}>
            {events.map((ev) => {
              const status = ev.change_analysis_status || 'CATALOG_DISCOVERED';
              const titleText = t(ev.event_name_zh || ev.event_id, ev.event_name || ev.event_id);
              return (
                <button
                  key={ev.event_id}
                  type="button"
                  onClick={() => selectEvent(ev)}
                  className={`eci-card${ev.event_id === eventId ? ' active' : ''}`}
                  style={{ textAlign: 'left', cursor: 'pointer', color: '#f1f5f9', width: '100%', marginBottom: 0, padding: '9px 11px' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 6, alignItems: 'center' }}>
                    <strong style={{ fontSize: 12.5, lineHeight: 1.35 }}>{titleText}</strong>
                    <span className={`eci-badge ${status === 'CHANGE_ANALYZED' ? 'ok' : 'muted'}`}>
                      {status}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                    {ev.country} · {ev.event_type} · {ev.sensor} · {ev.demo_mode || 'COMMITTED_STUDY'}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Quick AOI Parcel Selector & Layer Controls */}
      {showControls && (
        <div className="eci-glass">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0' }}>
              {t('農田地塊與圖層控制', 'AOI Parcels & Layer Controls')}
              <IndicatorTooltip indicatorKey="vh_change" />
            </span>
            <span className="eci-badge">{invStatus}</span>
          </div>

          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 8 }}>
            {PARCEL_IDS.map((pid) => (
              <button
                key={pid}
                type="button"
                className="eci-tab"
                aria-selected={selectedFieldId === pid}
                onClick={() => setSelectedFieldId(pid)}
                style={{ padding: '4px 8px', fontSize: 11.5 }}
              >
                {pid}
              </button>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 8 }}>
            {(['OBSERVED', 'HYPOTHESES', 'UNKNOWN', 'NEXT_EVIDENCE'] as LensMode[]).map((l) => (
              <button
                key={l}
                type="button"
                className="eci-tab"
                aria-selected={selectedLens === l}
                onClick={() => setSelectedLens(l)}
                style={{ padding: '4px 8px', fontSize: 11 }}
              >
                {l}
              </button>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', fontSize: 11.5, color: '#cbd5e1' }}>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={activeLayers.includes('vh-change')}
                onChange={() => toggleLayer('vh-change')}
              />
              {t('VH 差分圖層', 'VH Delta Layer')}
            </label>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={activeLayers.includes('fields-outline')}
                onChange={() => toggleLayer('fields-outline')}
              />
              {t('地塊邊界', 'Parcel Boundaries')}
            </label>
          </div>
        </div>
      )}

      {/* Selected Parcel Telemetry & Provenance Card */}
      {showControls && (
        <div className="eci-glass">
          <div className="eci-header" style={{ marginBottom: 6 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#cbd5e1' }}>
              Selected Parcel ({selectedFieldId})
            </span>
            <span className="eci-badge warn">OBSERVED ≠ CONFIRMED DAMAGE</span>
          </div>
          <div className="eci-grid-2">
            <div className="eci-card" style={{ marginBottom: 0 }}>
              <div style={{ fontSize: 11, color: '#94a3b8' }}>
                VH Shift <IndicatorTooltip indicatorKey="valid_pixels" />
              </div>
              <div className="eci-metric">{selectedFieldId === 'YL-CAND-03' ? '+7.55336 dB' : 'OBSERVED'}</div>
              <div style={{ fontSize: 11, color: '#cbd5e1', marginTop: 3 }}>
                Status: <b>OBSERVED</b> · Typhoon Cause: <b>UNRESOLVED</b> · Crop Damage: <b>NOT CONFIRMED</b>
              </div>
            </div>
            <div className="eci-card" style={{ marginBottom: 0 }}>
              <div style={{ fontSize: 11, color: '#94a3b8' }}>Source Provenance & Evidence Ledger</div>
              <div style={{ fontSize: 11, color: '#67e8f9', marginTop: 4, fontFamily: 'var(--f-mono, monospace)', wordBreak: 'break-word' }}>
                {evidenceIds.slice(0, 4).join(', ')}
              </div>
              {invResult && (
                <div style={{ fontSize: 11, color: '#a7f3d0', marginTop: 4 }}>
                  V3 Verified: {String(invResult.execution_mode || 'DETERMINISTIC')}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {mode === 'combined' && (
        <div className="eci-canvas-stage" style={{ position: 'relative', height: 380, borderRadius: 12, overflow: 'hidden' }}>
          <div ref={mapContainerRef} className="eci-map-canvas" aria-label="Earth Change Interactive Map" />
        </div>
      )}
    </div>
  );
}
