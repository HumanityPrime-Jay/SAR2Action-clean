import React, { createContext, useCallback, useContext, useState } from 'react';
import type { AIMapAction, EarthStory, LensMode, UserMode } from './api';

export type EarthModuleTab =
  | 'forensics'
  | 'timeline'
  | 'lens'
  | 'fingerprint'
  | 'hypotheses'
  | 'gaps'
  | 'discovery'
  | 'story';

export interface EarthInvestigationState {
  eventId: string;
  aoi: string;
  selectedFieldIds: string[];
  selectedFieldId: string;
  sensor: string;
  observationIds: string[];
  timelinePosition: string;
  selectedLens: LensMode;
  activeLayers: string[];
  activeHypothesis: string;
  investigationId: string | null;
  evidenceIds: string[];
  storyId: string | null;
  activeStory: EarthStory | null;
  userMode: UserMode;
  activeTab: EarthModuleTab;
  isPlayingTimeline: boolean;
  playbackSpeed: number;
  cameraTarget: { lon: number; lat: number; zoom: number; label?: string } | null;
}

interface EarthContextValue extends EarthInvestigationState {
  setEventId: (id: string) => void;
  setSelectedFieldId: (id: string) => void;
  setSelectedLens: (lens: LensMode) => void;
  setTimelinePosition: (date: string) => void;
  setActiveTab: (tab: EarthModuleTab) => void;
  setUserMode: (mode: UserMode) => void;
  setActiveHypothesis: (id: string) => void;
  setInvestigationResult: (id: string | null, evidenceIds: string[]) => void;
  setActiveStory: (story: EarthStory | null) => void;
  setIsPlayingTimeline: (playing: boolean) => void;
  setPlaybackSpeed: (speed: number) => void;
  toggleLayer: (layer: string, visible?: boolean) => void;
  flyToRegion: (lon: number, lat: number, zoom?: number, label?: string) => void;
  applyMapActions: (actions: AIMapAction[]) => void;
}

const EarthContext = createContext<EarthContextValue | null>(null);

export function EarthInvestigationProvider({
  children,
  initialEventId = 'CHAMPI-YUNLIN-TAIXI',
  initialFieldId = 'YL-CAND-03',
  onExternalSelectField,
  onExternalSelectEvent,
}: {
  children: React.ReactNode;
  initialEventId?: string;
  initialFieldId?: string;
  onExternalSelectField?: (id: string) => void;
  onExternalSelectEvent?: (id: string) => void;
}) {
  const [state, setState] = useState<EarthInvestigationState>({
    eventId: initialEventId,
    aoi: 'Taixi Township, Yunlin',
    selectedFieldIds: ['YL-CAND-01', 'YL-CAND-02', 'YL-CAND-03', 'YL-CAND-04', 'YL-CAND-05'],
    selectedFieldId: initialFieldId,
    sensor: 'OPERA_RTC_S1 + NISAR_GCOV',
    observationIds: ['OPERA-S1-20261010', 'OPERA-S1-20261022', 'OPERA-S1-20261103'],
    timelinePosition: '2026-10-22',
    selectedLens: 'OBSERVED',
    activeLayers: ['vh-change', 'fields-outline'],
    activeHypothesis: 'typhoon_surface_change',
    investigationId: null,
    evidenceIds: ['EV-OPERA-S1-YL-CAND-03-VH', 'EV-NISAR-TW03-CRID-QA'],
    storyId: null,
    activeStory: null,
    userMode: 'AUTHORITY',
    activeTab: 'forensics',
    isPlayingTimeline: false,
    playbackSpeed: 1,
    cameraTarget: { lon: 120.1945, lat: 23.7025, zoom: 12.4, label: 'Taixi, Yunlin' },
  });

  const setEventId = useCallback(
    (id: string) => {
      setState((s) => ({ ...s, eventId: id }));
      onExternalSelectEvent?.(id);
    },
    [onExternalSelectEvent],
  );

  const setSelectedFieldId = useCallback(
    (id: string) => {
      setState((s) => ({ ...s, selectedFieldId: id }));
      onExternalSelectField?.(id);
    },
    [onExternalSelectField],
  );

  const setSelectedLens = useCallback((selectedLens: LensMode) => {
    setState((s) => ({ ...s, selectedLens }));
  }, []);

  const setTimelinePosition = useCallback((timelinePosition: string) => {
    setState((s) => ({ ...s, timelinePosition }));
  }, []);

  const setActiveTab = useCallback((activeTab: EarthModuleTab) => {
    setState((s) => ({ ...s, activeTab }));
  }, []);

  const setUserMode = useCallback((userMode: UserMode) => {
    setState((s) => ({ ...s, userMode }));
  }, []);

  const setActiveHypothesis = useCallback((activeHypothesis: string) => {
    setState((s) => ({ ...s, activeHypothesis }));
  }, []);

  const setInvestigationResult = useCallback((investigationId: string | null, evidenceIds: string[]) => {
    setState((s) => ({ ...s, investigationId, evidenceIds: Array.from(new Set([...s.evidenceIds, ...evidenceIds])) }));
  }, []);

  const setActiveStory = useCallback((activeStory: EarthStory | null) => {
    setState((s) => ({ ...s, activeStory, storyId: activeStory?.story_id ?? s.storyId }));
  }, []);

  const setIsPlayingTimeline = useCallback((isPlayingTimeline: boolean) => {
    setState((s) => ({ ...s, isPlayingTimeline }));
  }, []);

  const setPlaybackSpeed = useCallback((playbackSpeed: number) => {
    setState((s) => ({ ...s, playbackSpeed }));
  }, []);

  const toggleLayer = useCallback((layer: string, visible?: boolean) => {
    setState((s) => {
      const exists = s.activeLayers.includes(layer);
      const shouldAdd = visible ?? !exists;
      return {
        ...s,
        activeLayers: shouldAdd ? (exists ? s.activeLayers : [...s.activeLayers, layer]) : s.activeLayers.filter((l) => l !== layer),
      };
    });
  }, []);

  const flyToRegion = useCallback((lon: number, lat: number, zoom = 12.2, label?: string) => {
    setState((s) => ({ ...s, cameraTarget: { lon, lat, zoom, label } }));
  }, []);

  const applyMapActions = useCallback((actions: AIMapAction[]) => {
    setState((prev) => {
      let next = { ...prev };
      for (const act of actions) {
        const p = act.params || {};
        switch (act.action) {
          case 'SELECT_EVENT':
            if (typeof p.event_id === 'string') next.eventId = p.event_id;
            break;
          case 'FLY_TO_REGION':
            if (typeof p.lon === 'number' && typeof p.lat === 'number') {
              next.cameraTarget = {
                lon: p.lon,
                lat: p.lat,
                zoom: typeof p.zoom === 'number' ? p.zoom : 12.2,
                label: typeof p.region === 'string' ? p.region : undefined,
              };
            }
            break;
          case 'SELECT_FIELD':
            if (typeof p.field_id === 'string') next.selectedFieldId = p.field_id;
            break;
          case 'SHOW_LAYER':
            if (typeof p.layer === 'string' && !next.activeLayers.includes(p.layer)) {
              next.activeLayers = [...next.activeLayers, p.layer];
            }
            break;
          case 'HIDE_LAYER':
            if (typeof p.layer === 'string') {
              next.activeLayers = next.activeLayers.filter((l) => l !== p.layer);
            }
            break;
          case 'OPEN_TIMELINE':
            next.activeTab = 'timeline';
            break;
          case 'PLAY_TIMELINE':
            next.activeTab = 'timeline';
            next.isPlayingTimeline = true;
            break;
          case 'PAUSE_TIMELINE':
            next.isPlayingTimeline = false;
            break;
          case 'SET_TIMELINE_DATE':
            if (typeof p.date === 'string') next.timelinePosition = p.date;
            break;
          case 'OPEN_REALITY_LENS':
            if (typeof p.lens === 'string') next.selectedLens = p.lens as LensMode;
            next.activeTab = 'lens';
            break;
          case 'COMPARE_FIELDS':
          case 'SHOW_FINGERPRINT':
            next.activeTab = 'fingerprint';
            break;
          case 'OPEN_HYPOTHESIS_ARENA':
          case 'RUN_INVESTIGATION':
            next.activeTab = 'hypotheses';
            break;
          case 'OPEN_EVIDENCE':
            next.activeTab = 'forensics';
            break;
          case 'GENERATE_EARTH_STORY':
            next.activeTab = 'story';
            break;
          default:
            break;
        }
      }
      return next;
    });
  }, []);

  return (
    <EarthContext.Provider
      value={{
        ...state,
        setEventId,
        setSelectedFieldId,
        setSelectedLens,
        setTimelinePosition,
        setActiveTab,
        setUserMode,
        setActiveHypothesis,
        setInvestigationResult,
        setActiveStory,
        setIsPlayingTimeline,
        setPlaybackSpeed,
        toggleLayer,
        flyToRegion,
        applyMapActions,
      }}
    >
      {children}
    </EarthContext.Provider>
  );
}

export function useEarthContext() {
  const ctx = useContext(EarthContext);
  if (!ctx) throw new Error('useEarthContext must be used inside EarthInvestigationProvider');
  return ctx;
}
