import React, { useState } from 'react';
import { useLang, useT } from '../../i18n';
import { useEarthContext } from '../EarthContext';
import { earthApi, type EarthStory } from '../api';

export function PlanetaryStoryPlayer() {
  const t = useT();
  const { lang } = useLang();
  const {
    eventId,
    selectedFieldId,
    userMode,
    activeStory,
    setActiveStory,
    setSelectedLens,
    setTimelinePosition,
    flyToRegion,
  } = useEarthContext();

  const [chapterIdx, setChapterIdx] = useState(0);
  const [generating, setGenerating] = useState(false);
  const [importJson, setImportJson] = useState('');
  const [importError, setImportError] = useState<string | null>(null);

  const generate = async () => {
    setGenerating(true);
    setImportError(null);
    try {
      const story = await earthApi.generateStory({
        event_id: eventId,
        field_id: selectedFieldId,
        user_mode: userMode,
        lang,
      });
      setActiveStory(story);
      setChapterIdx(0);
      syncChapter(story, 0);
    } finally {
      setGenerating(false);
    }
  };

  const syncChapter = (story: EarthStory, idx: number) => {
    const ch = story.chapters[idx];
    if (!ch) return;
    setSelectedLens(ch.lens);
    if (ch.timeline_date) setTimelinePosition(ch.timeline_date);
    if (typeof ch.camera.lon === 'number' && typeof ch.camera.lat === 'number') {
      flyToRegion(ch.camera.lon, ch.camera.lat, typeof ch.camera.zoom === 'number' ? ch.camera.zoom : 12.4);
    }
  };

  const goChapter = (idx: number) => {
    if (!activeStory) return;
    const bounded = Math.max(0, Math.min(idx, activeStory.chapters.length - 1));
    setChapterIdx(bounded);
    syncChapter(activeStory, bounded);
  };

  const exportJson = () => {
    if (!activeStory) return;
    const blob = new Blob([JSON.stringify(activeStory, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${activeStory.story_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImport = async () => {
    setImportError(null);
    try {
      const parsed = JSON.parse(importJson) as EarthStory;
      const verified = await earthApi.importStory(parsed);
      setActiveStory(verified);
      setChapterIdx(0);
      syncChapter(verified, 0);
      setImportJson('');
    } catch (err) {
      setImportError((err as Error).message);
    }
  };

  const current = activeStory?.chapters[chapterIdx];

  return (
    <div className="eci-glass">
      <div className="eci-header">
        <div>
          <span className="eci-badge">PLANETARY CHANGE STORIES · 7 CHAPTERS</span>
          <h3 className="h3" style={{ margin: '6px 0 0', color: '#f8fafc' }}>
            {t('互動式地球科學故事播放器', 'Planetary Change Story Player')}
          </h3>
        </div>
        <button className="eci-btn" disabled={generating} onClick={generate}>
          {generating ? t('產生中…', 'Generating…') : t('產生 7 章節故事', 'Generate Story')}
        </button>
      </div>

      {activeStory && current && (
        <div className="eci-card active">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
            <span className="eci-badge">{current.chapter_code}</span>
            <span className="mono" style={{ fontSize: 11.5, color: '#94a3b8' }}>
              {chapterIdx + 1} / {activeStory.chapters.length} · ID: {activeStory.story_id}
            </span>
          </div>
          <h4 style={{ margin: '8px 0 4px', color: '#f8fafc' }}>{current.title}</h4>
          <p style={{ fontSize: 13, color: '#e2e8f0', margin: '4px 0 8px' }}>{current.narrative}</p>
          <div style={{ fontSize: 11.5, color: '#67e8f9', fontFamily: 'var(--f-mono, monospace)' }}>
            Evidence: {current.evidence_ids.join(', ') || 'Catalog Metadata'}
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
            <button className="eci-btn secondary" disabled={chapterIdx === 0} onClick={() => goChapter(chapterIdx - 1)}>
              ← {t('上一章', 'Prev')}
            </button>
            <button className="eci-btn" disabled={chapterIdx >= activeStory.chapters.length - 1} onClick={() => goChapter(chapterIdx + 1)}>
              {t('下一章', 'Next')} →
            </button>
            <button className="eci-btn secondary" onClick={exportJson}>
              {t('匯出 JSON', 'Export JSON')}
            </button>
            <a className="eci-btn secondary" href={`/api/earth/stories/${activeStory.story_id}/export.html`} target="_blank" rel="noreferrer">
              {t('匯出 HTML 報告', 'Export HTML')}
            </a>
          </div>
        </div>
      )}

      <div className="eci-card">
        <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 6 }}>
          {t('匯入並驗證故事 JSON (Schema Validation)', 'Import & Validate Story JSON')}
        </div>
        <textarea
          className="eci-input"
          rows={2}
          aria-label="Import story JSON"
          placeholder='{"story_id": "STORY-...", ...}'
          value={importJson}
          onChange={(e) => setImportJson(e.target.value)}
        />
        {importError && <div style={{ color: '#fdba74', fontSize: 12, marginTop: 4 }}>{importError}</div>}
        <button className="eci-btn secondary" style={{ marginTop: 6 }} disabled={!importJson.trim()} onClick={handleImport}>
          {t('匯入故事', 'Import Story')}
        </button>
      </div>
    </div>
  );
}
