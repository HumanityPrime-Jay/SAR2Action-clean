import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import type { AIMapAction, EarthStory, GuidedDiscoveryResponse, LensMode, UserMode } from './api';

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
  sarOpacity: number;
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
  leftDockOpen: boolean;
  rightDockOpen: boolean;
  bottomTimelineOpen: boolean;
  actionFeedback: string[];
  lastDiscoveryResult: GuidedDiscoveryResponse | null;
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
  setSarOpacity: (opacity: number) => void;
  setLeftDockOpen: (open: boolean) => void;
  setRightDockOpen: (open: boolean) => void;
  setBottomTimelineOpen: (open: boolean) => void;
  setLastDiscoveryResult: (res: GuidedDiscoveryResponse | null) => void;
  toggleLayer: (layer: string, visible?: boolean) => void;
  flyToRegion: (lon: number, lat: number, zoom?: number, label?: string) => void;
  applyMapActions: (actions: AIMapAction[]) => void;
  pushActionFeedback: (messages: string[]) => void;
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
    sarOpacity: 0.78,
    activeHypothesis: 'typhoon_surface_change',
    investigationId: null,
    evidenceIds: ['EV-OPERA-S1-YL-CAND-03-VH', 'EV-NISAR-TW03-CRID-QA'],
    storyId: null,
    activeStory: null,
    userMode: 'AUTHORITY',
    activeTab: 'forensics',
    isPlayingTimeline: false,
    playbackSpeed: 1,
    cameraTarget: { lon: 120.1945, lat: 23.7025, zoom: 12.6, label: 'Taixi, Yunlin' },
    leftDockOpen: true,
    rightDockOpen: true,
    bottomTimelineOpen: true,
    actionFeedback: [],
    lastDiscoveryResult: null,
  });

  const feedbackTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (feedbackTimerRef.current !== null) {
        window.clearTimeout(feedbackTimerRef.current);
      }
    };
  }, []);

  const pushActionFeedback = useCallback((messages: string[]) => {
    if (!messages.length) return;
    setState((s) => ({ ...s, actionFeedback: messages }));
    if (feedbackTimerRef.current !== null) {
      window.clearTimeout(feedbackTimerRef.current);
    }
    feedbackTimerRef.current = window.setTimeout(() => {
      setState((s) => ({ ...s, actionFeedback: [] }));
      feedbackTimerRef.current = null;
    }, 3400);
  }, []);

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
    setState((s) => ({
      ...s,
      activeTab,
      rightDockOpen: true,
      bottomTimelineOpen: activeTab === 'timeline' ? true : s.bottomTimelineOpen,
    }));
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
    setState((s) => ({
      ...s,
      isPlayingTimeline,
      bottomTimelineOpen: isPlayingTimeline ? true : s.bottomTimelineOpen,
    }));
  }, []);

  const setPlaybackSpeed = useCallback((playbackSpeed: number) => {
    setState((s) => ({ ...s, playbackSpeed }));
  }, []);

  const setSarOpacity = useCallback((sarOpacity: number) => {
    setState((s) => ({ ...s, sarOpacity: Math.max(0.1, Math.min(1, sarOpacity)) }));
  }, []);

  const setLeftDockOpen = useCallback((leftDockOpen: boolean) => {
    setState((s) => ({ ...s, leftDockOpen }));
  }, []);

  const setRightDockOpen = useCallback((rightDockOpen: boolean) => {
    setState((s) => ({ ...s, rightDockOpen }));
  }, []);

  const setBottomTimelineOpen = useCallback((bottomTimelineOpen: boolean) => {
    setState((s) => ({ ...s, bottomTimelineOpen }));
  }, []);

  const setLastDiscoveryResult = useCallback((lastDiscoveryResult: GuidedDiscoveryResponse | null) => {
    setState((s) => ({ ...s, lastDiscoveryResult }));
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

  const flyToRegion = useCallback((lon: number, lat: number, zoom = 12.6, label?: string) => {
    setState((s) => ({ ...s, cameraTarget: { lon, lat, zoom, label } }));
  }, []);

  const applyMapActions = useCallback(
    (actions: AIMapAction[]) => {
      const feedback: string[] = [];
      setState((prev) => {
        const next = { ...prev, rightDockOpen: true };
        for (const rawAct of actions || []) {
          const anyAct = rawAct as unknown as Record<string, unknown>;
          const actionName = String(rawAct.action || anyAct.action_type || '');
          const p = (rawAct.params || anyAct.payload || {}) as Record<string, unknown>;
          switch (actionName) {
            case 'SELECT_EVENT':
            case 'SWITCH_EVENT':
              if (typeof p.event_id === 'string') {
                next.eventId = p.event_id;
                feedback.push(`Selecting Event ${p.event_id}`);
              }
              break;
            case 'FLY_TO_REGION':
              if (typeof p.lon === 'number' && typeof p.lat === 'number') {
                next.cameraTarget = {
                  lon: p.lon,
                  lat: p.lat,
                  zoom: typeof p.zoom === 'number' ? p.zoom : 12.6,
                  label: typeof p.region === 'string' ? p.region : undefined,
                };
                feedback.push(`Flying to ${p.region || `${p.lat.toFixed(2)}°N, ${p.lon.toFixed(2)}°E`}`);
              }
              break;
            case 'SELECT_FIELD':
            case 'SELECT_PARCEL':
              if (typeof p.field_id === 'string') {
                next.selectedFieldId = p.field_id;
                feedback.push(`Selecting ${p.field_id}`);
              }
              break;
            case 'SELECT_AOI':
              if (typeof p.aoi === 'string') {
                next.aoi = p.aoi;
                feedback.push(`Focusing AOI ${p.aoi}`);
              }
              break;
            case 'SHOW_LAYER':
              if (typeof p.layer === 'string' && !next.activeLayers.includes(p.layer)) {
                next.activeLayers = [...next.activeLayers, p.layer];
                feedback.push(`Showing Layer ${p.layer}`);
              }
              break;
            case 'HIDE_LAYER':
              if (typeof p.layer === 'string') {
                next.activeLayers = next.activeLayers.filter((l) => l !== p.layer);
                feedback.push(`Hiding Layer ${p.layer}`);
              }
              break;
            case 'SET_LAYER_OPACITY':
              if (typeof p.opacity === 'number') {
                next.sarOpacity = Math.max(0.1, Math.min(1, p.opacity));
                feedback.push(`Setting SAR Opacity to ${Math.round(next.sarOpacity * 100)}%`);
              }
              break;
            case 'OPEN_TIMELINE':
            case 'COMPARE_OBSERVATIONS':
              next.activeTab = 'timeline';
              next.bottomTimelineOpen = true;
              feedback.push('Opening Timeline');
              break;
            case 'PLAY_TIMELINE':
              next.activeTab = 'timeline';
              next.bottomTimelineOpen = true;
              next.isPlayingTimeline = true;
              feedback.push('Playing Earth Memory Timeline');
              break;
            case 'PAUSE_TIMELINE':
              next.isPlayingTimeline = false;
              feedback.push('Pausing Timeline');
              break;
            case 'SET_TIMELINE_DATE':
              if (typeof p.date === 'string') {
                next.timelinePosition = p.date;
                feedback.push(`Scrubbing to ${p.date}`);
              }
              break;
            case 'OPEN_REALITY_LENS':
            case 'SWITCH_LENS':
              if (typeof p.lens === 'string') {
                next.selectedLens = p.lens as LensMode;
                feedback.push(`Switching Reality Lens → ${p.lens}`);
              }
              next.activeTab = 'lens';
              break;
            case 'COMPARE_FIELDS':
            case 'SHOW_FINGERPRINT':
              next.activeTab = 'fingerprint';
              feedback.push(actionName === 'COMPARE_FIELDS' ? 'Comparing Fields' : 'Showing Surface Fingerprint');
              break;
            case 'OPEN_HYPOTHESIS_ARENA':
            case 'RUN_INVESTIGATION':
              next.activeTab = 'hypotheses';
              feedback.push('Opening Hypothesis Arena');
              break;
            case 'OPEN_EVIDENCE':
              next.activeTab = 'forensics';
              feedback.push('Showing Evidence & Provenance');
              break;
            case 'GENERATE_EARTH_STORY':
            case 'PLAY_STORY':
              next.activeTab = 'story';
              feedback.push('Opening Planetary Story Experience');
              break;
            default:
              break;
          }
        }
        return next;
      });
      if (feedback.length > 0) {
        pushActionFeedback(feedback);
      }
    },
    [pushActionFeedback],
  );

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
        setSarOpacity,
        setLeftDockOpen,
        setRightDockOpen,
        setBottomTimelineOpen,
        setLastDiscoveryResult,
        toggleLayer,
        flyToRegion,
        applyMapActions,
        pushActionFeedback,
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
