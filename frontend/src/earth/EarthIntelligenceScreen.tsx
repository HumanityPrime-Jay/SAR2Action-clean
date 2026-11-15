import React, { useState } from 'react';
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

const MODULE_TABS: { id: EarthModuleTab; step: string; zh: string; en: string }[] = [
  { id: 'forensics', step: '01', zh: '鑑識與圖層', en: 'Forensics' },
  { id: 'timeline', step: '02', zh: '地球記憶時間軸', en: 'Earth Memory' },
  { id: 'lens', step: '03', zh: '實相透鏡', en: 'Reality Lens' },
  { id: 'fingerprint', step: '04', zh: '變化指紋', en: 'Fingerprint' },
  { id: 'hypotheses', step: '05', zh: '假設競技場', en: 'Hypothesis Arena' },
  { id: 'gaps', step: '06', zh: '證據缺口', en: 'Evidence Gaps' },
  { id: 'discovery', step: '07', zh: 'AI 探索', en: 'AI Discovery' },
  { id: 'story', step: '08', zh: '行星故事', en: 'Story' },
];

function WorkspaceInner({ go }: { go: ScreenProps['go'] }) {
  const t = useT();
  const {
    activeTab,
    setActiveTab,
    eventId,
    selectedFieldId,
    selectedLens,
    userMode,
    leftDockOpen,
    setLeftDockOpen,
    rightDockOpen,
    setRightDockOpen,
    bottomTimelineOpen,
    setBottomTimelineOpen,
    actionFeedback,
  } = useEarthContext();

  const [mobilePane, setMobilePane] = useState<'intel' | 'events' | 'time'>('intel');

  const handleSelectTab = (tab: EarthModuleTab) => {
    setActiveTab(tab);
    setMobilePane('intel');
  };

  return (
    <div
      className="eci-shell"
      data-left={leftDockOpen ? 'open' : 'closed'}
      data-right={rightDockOpen ? 'open' : 'closed'}
    >
      {/* Live Action Feedback Toast */}
      {actionFeedback.length > 0 && (
        <div className="eci-action-toast" role="status" aria-live="polite">
          <span>⚡</span>
          <span>{actionFeedback.join(' · ')}</span>
        </div>
      )}

      {/* Top Mission Control HUD & Continuous 8-Step Journey Bar */}
      <header className="eci-top-hud">
        <div className="eci-hud-left">
          <button
            type="button"
            className="eci-btn secondary"
            style={{ padding: '4px 9px', minHeight: 28, fontSize: 11.5 }}
            onClick={() => setLeftDockOpen(!leftDockOpen)}
            aria-expanded={leftDockOpen}
            title={t('切換左側探索面板', 'Toggle Left Discovery Dock')}
          >
            {leftDockOpen ? '◀ Catalog' : '▶ Catalog'}
          </button>
          <span className="eci-badge">
            CONTEXT: {eventId} · {selectedFieldId} · {selectedLens} · {userMode}
          </span>
        </div>

        <nav
          className="eci-journey-nav"
          role="tablist"
          aria-label={t('地球變化智慧模組', 'Earth Intelligence Modules')}
        >
          {MODULE_TABS.map((m) => (
            <button
              key={m.id}
              type="button"
              role="tab"
              aria-selected={activeTab === m.id}
              className="eci-tab"
              onClick={() => handleSelectTab(m.id)}
              style={{ whiteSpace: 'nowrap', padding: '5px 9px', fontSize: 11.5 }}
            >
              {t(m.zh, m.en)}
            </button>
          ))}
        </nav>

        <div className="eci-hud-right">
          <button
            type="button"
            className="eci-btn secondary"
            style={{ padding: '4px 9px', minHeight: 28, fontSize: 11.5 }}
            onClick={() => setBottomTimelineOpen(!bottomTimelineOpen)}
            aria-expanded={bottomTimelineOpen}
          >
            {bottomTimelineOpen ? '▼ Time' : '▲ Time'}
          </button>
          <button
            type="button"
            className="eci-btn secondary"
            style={{ padding: '4px 9px', minHeight: 28, fontSize: 11.5 }}
            onClick={() => setRightDockOpen(!rightDockOpen)}
            aria-expanded={rightDockOpen}
          >
            {rightDockOpen ? 'Intel ▶' : '◀ Intel'}
          </button>
          <button
            type="button"
            className="eci-btn secondary"
            style={{ padding: '4px 10px', minHeight: 28, fontSize: 11.5 }}
            onClick={() => go('assist')}
          >
            {t('切回農民 / 救助助手', 'Switch to Farmer / Relief')}
          </button>
        </div>
      </header>

      {/* Center Full-Bleed Interactive Earth & SAR Canvas */}
      <EarthChangeExplorer mode="canvas" onReturnToGlobe={() => go('home')} />

      {/* Mobile / Tablet Bottom-Sheet Mode Switcher */}
      <div className="eci-mobile-bar" role="group" aria-label="Mobile workspace view switcher">
        <button
          type="button"
          className="eci-tab"
          aria-selected={mobilePane === 'events'}
          onClick={() => setMobilePane('events')}
        >
          {t('1. 事件與圖層', '1. Events & Layers')}
        </button>
        <button
          type="button"
          className="eci-tab"
          aria-selected={mobilePane === 'intel'}
          onClick={() => setMobilePane('intel')}
        >
          {t('2. 科學分析與 AI', '2. Science & AI')}
        </button>
        <button
          type="button"
          className="eci-tab"
          aria-selected={mobilePane === 'time'}
          onClick={() => {
            setMobilePane('time');
            setActiveTab('timeline');
          }}
        >
          {t('3. 時間軸', '3. Time Machine')}
        </button>
      </div>

      {/* Left Collapsible Discovery Controls Dock */}
      <aside
        className={`eci-left-dock${!leftDockOpen ? ' collapsed' : ''}${mobilePane !== 'events' ? ' mobile-hidden' : ''}`}
        aria-label="Global Event Discovery and Layer Controls"
      >
        <EarthChangeExplorer mode="controls" onReturnToGlobe={() => go('home')} />
      </aside>

      {/* Right Contextual Scientific Intelligence Dock */}
      <section
        className={`eci-right-dock${activeTab === 'story' || activeTab === 'hypotheses' ? ' wide' : ''}${!rightDockOpen ? ' collapsed' : ''}${mobilePane !== 'intel' ? ' mobile-hidden' : ''}`}
        aria-label="Scientific Intelligence Panel"
      >
        {/* Sleek AI Command Bar at top of Right Dock for natural-language control */}
        {activeTab !== 'discovery' && <GuidedDiscoveryPanel compact />}

        {activeTab === 'forensics' && <RealityLensSelector />}
        {activeTab === 'timeline' && <EarthMemoryTimeline />}
        {activeTab === 'lens' && <RealityLensSelector />}
        {activeTab === 'fingerprint' && <FingerprintViewer />}
        {activeTab === 'hypotheses' && <ScientificHypothesisArena />}
        {activeTab === 'gaps' && <EvidenceGapNavigator />}
        {activeTab === 'discovery' && <GuidedDiscoveryPanel compact={false} />}
        {activeTab === 'story' && <PlanetaryStoryPlayer />}
      </section>

      {/* Bottom Video-Editor-Grade Earth Memory Time Dock */}
      {activeTab !== 'timeline' && (
        <div
          className={`eci-bottom-dock${!bottomTimelineOpen ? ' collapsed' : ''}${mobilePane !== 'time' ? ' mobile-hidden' : ''}`}
          aria-label="Earth Memory Quick Scrubber"
        >
          <EarthMemoryTimeline compactDock />
        </div>
      )}

      {/* Mission Control Bottom Provenance Status Bar (Replaces colliding floating demo-note) */}
      <footer className="eci-status-bar">
        <span>
          {t(
            '臺西 CHAMPI-YUNLIN-TAIXI · 雷達資料為真實觀測 · 救助金額為示意試算',
            'CHAMPI-YUNLIN-TAIXI · Radar data are real observations · relief amounts are illustrative',
          )}
        </span>
        <span>
          YL-CAND-03: +7.55336 dB (2026-10-23 05:51:56 CST · DURING_TYPHOON_WARNING) · NISAR Cross-CRID: UNVERIFIED
        </span>
      </footer>
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
