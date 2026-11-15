import React from 'react';
import { useT } from '../i18n';
import type { ScreenProps } from '../screens/types';
import { EarthInvestigationProvider, type EarthModuleTab, useEarthContext } from './EarthContext';
import { EarthChangeExplorer } from './components/EarthChangeExplorer';
import { EarthMemoryTimeline } from './components/EarthMemoryTimeline';
import { EvidenceGapNavigator } from './components/EvidenceGapNavigator';
import { FingerprintViewer } from './components/FingerprintViewer';
import { GuidedDiscoveryPanel } from './components/GuidedDiscoveryPanel';
import { PlanetaryStoryPlayer } from './components/PlanetaryStoryPlayer';
import { RealityLensSelector } from './components/RealityLensSelector';
import { ScientificHypothesisArena } from './components/ScientificHypothesisArena';
import './earth.css';

const MODULE_TABS: { id: EarthModuleTab; zh: string; en: string }[] = [
  { id: 'forensics', zh: '鑑識與圖層', en: 'Forensics' },
  { id: 'timeline', zh: '地球記憶時間軸', en: 'Earth Memory' },
  { id: 'lens', zh: '實相透鏡', en: 'Reality Lens' },
  { id: 'fingerprint', zh: '變化指紋', en: 'Fingerprint' },
  { id: 'hypotheses', zh: '假設競技場', en: 'Hypothesis Arena' },
  { id: 'gaps', zh: '證據缺口', en: 'Evidence Gaps' },
  { id: 'discovery', zh: 'AI 探索', en: 'AI Discovery' },
  { id: 'story', zh: '行星故事', en: 'Story' },
];

function WorkspaceInner({ go }: { go: ScreenProps['go'] }) {
  const t = useT();
  const { activeTab, setActiveTab, eventId, selectedFieldId, selectedLens, userMode } = useEarthContext();

  return (
    <div className="eci-shell">
      <div>
        <EarthChangeExplorer onReturnToGlobe={() => go('home')} />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="eci-glass">
          <div className="eci-header" style={{ marginBottom: 8 }}>
            <span className="eci-badge">
              CONTEXT: {eventId} · {selectedFieldId} · {selectedLens} · {userMode}
            </span>
            <button className="eci-btn secondary" style={{ fontSize: 12 }} onClick={() => go('assist')}>
              {t('切回農民 / 救助助手', 'Switch to Farmer / Relief')}
            </button>
          </div>
          <nav className="eci-tabs" role="tablist" aria-label={t('地球變化智慧模組', 'Earth Intelligence Modules')}>
            {MODULE_TABS.map((m) => (
              <button
                key={m.id}
                role="tab"
                aria-selected={activeTab === m.id}
                className="eci-tab"
                onClick={() => setActiveTab(m.id)}
              >
                {t(m.zh, m.en)}
              </button>
            ))}
          </nav>
        </div>

        {/* Always show AI Guided Discovery bar at top of right column for unified natural language control */}
        {activeTab !== 'discovery' && <GuidedDiscoveryPanel />}

        {activeTab === 'forensics' && <RealityLensSelector />}
        {activeTab === 'timeline' && <EarthMemoryTimeline />}
        {activeTab === 'lens' && <RealityLensSelector />}
        {activeTab === 'fingerprint' && <FingerprintViewer />}
        {activeTab === 'hypotheses' && <ScientificHypothesisArena />}
        {activeTab === 'gaps' && <EvidenceGapNavigator />}
        {activeTab === 'discovery' && <GuidedDiscoveryPanel />}
        {activeTab === 'story' && <PlanetaryStoryPlayer />}
      </div>
    </div>
  );
}

export function EarthIntelligenceScreen({ selectedId, onSelect, eventId, onEvent, go }: ScreenProps) {
  return (
    <EarthInvestigationProvider
      initialEventId={eventId === 'champi-2026-yunlin' || !eventId ? 'CHAMPI-YUNLIN-TAIXI' : eventId}
      initialFieldId={selectedId || 'YL-CAND-03'}
      onExternalSelectField={onSelect}
      onExternalSelectEvent={onEvent}
    >
      <WorkspaceInner go={go} />
    </EarthInvestigationProvider>
  );
}
