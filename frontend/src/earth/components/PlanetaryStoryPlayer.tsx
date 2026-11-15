import React, { useEffect, useState } from 'react';
import { useLang, useT } from '../../i18n';
import { useEarthContext } from '../EarthContext';
import { earthApi, type EarthStory, type LensMode } from '../api';

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
    setActiveTab,
    flyToRegion,
    pushActionFeedback,
  } = useEarthContext();

  const [chapterIdx, setChapterIdx] = useState(0);
  const [generating, setGenerating] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [importJson, setImportJson] = useState('');
  const [importError, setImportError] = useState<string | null>(null);

  const syncChapter = (story: EarthStory, idx: number) => {
    const ch = story.chapters?.[idx] as unknown as Record<string, unknown> | undefined;
    if (!ch) return;
    const lens = (ch.lens || ch.lens_mode) as LensMode | undefined;
    if (lens) setSelectedLens(lens);
    if (typeof ch.timeline_date === 'string') setTimelinePosition(ch.timeline_date);
    const cam = (ch.camera || {}) as Record<string, number>;
    if (typeof cam.lon === 'number' && typeof cam.lat === 'number') {
      flyToRegion(cam.lon, cam.lat, typeof cam.zoom === 'number' ? cam.zoom : 12.8);
    }
  };

  const generate = async () => {
    setGenerating(true);
    setImportError(null);
    try {
      const fn = (earthApi.generateStory || (earthApi as unknown as Record<string, typeof earthApi.generateStory>).getStory);
      const story = await fn({
        event_id: eventId,
        field_id: selectedFieldId,
        user_mode: userMode,
        lang,
      });
      setActiveStory(story);
      setChapterIdx(0);
      syncChapter(story, 0);
      pushActionFeedback([`Generated 7-Chapter Documentary for ${selectedFieldId}`]);
    } finally {
      setGenerating(false);
    }
  };

  const goChapter = (idx: number) => {
    if (!activeStory?.chapters?.length) return;
    const bounded = Math.max(0, Math.min(idx, activeStory.chapters.length - 1));
    setChapterIdx(bounded);
    syncChapter(activeStory, bounded);
  };

  useEffect(() => {
    if (!playing || !activeStory?.chapters?.length) return;
    const timer = window.setInterval(() => {
      setChapterIdx((prev) => {
        const next = prev + 1;
        if (next >= activeStory.chapters.length) {
          setPlaying(false);
          return prev;
        }
        syncChapter(activeStory, next);
        return next;
      });
    }, 3600);
    return () => window.clearInterval(timer);
  });

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

  const current = activeStory?.chapters?.[chapterIdx] as unknown as Record<string, unknown> | undefined;

  return (
    <div className="eci-glass">
      <div className="eci-header">
        <div>
          <span className="eci-badge">PLANETARY CHANGE STORIES · 7 CHAPTERS</span>
          <h3 className="h3" style={{ margin: '5px 0 0', fontSize: 16, color: '#f8fafc' }}>
            {t('互動式地球科學故事播放器', 'Planetary Change Story Player')}
          </h3>
        </div>
        <button type="button" className="eci-btn" disabled={generating} onClick={generate}>
          {generating ? t('產生中…', 'Generating…') : t('產生 7 章節故事', 'Generate Story')}
        </button>
      </div>

      {activeStory && current && (
        <div className="eci-card active">
          {/* Chapter Progress Strip */}
          <div style={{ display: 'flex', gap: 4, marginBottom: 8 }}>
            {activeStory.chapters.map((ch, idx) => (
              <button
                key={String((ch as unknown as Record<string, unknown>).chapter_id || idx)}
                type="button"
                aria-label={`Chapter ${idx + 1}`}
                onClick={() => goChapter(idx)}
                style={{
                  flex: 1,
                  height: 6,
                  borderRadius: 99,
                  background: idx === chapterIdx ? '#fb923c' : idx < chapterIdx ? '#22d3ee' : 'rgba(148,163,184,0.28)',
                }}
              />
            ))}
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
            <span className="eci-badge">
              {String(current.chapter_code || `CHAPTER 0${chapterIdx + 1}`)}
            </span>
            <span className="mono" style={{ fontSize: 11.5, color: '#94a3b8' }}>
              {chapterIdx + 1} / {activeStory.chapters.length} · ID: {activeStory.story_id}
            </span>
          </div>

          <h4 style={{ margin: '8px 0 4px', fontSize: 15, color: '#f8fafc' }}>{String(current.title || '')}</h4>
          <p style={{ fontSize: 12.5, color: '#e2e8f0', margin: '4px 0 8px', lineHeight: 1.5 }}>
            {String(current.narrative || '')}
          </p>

          {/* Chapter Visual Evidence Artifact */}
          <div className="eci-card" style={{ background: 'rgba(6, 12, 24, 0.85)', marginBottom: 8, padding: '8px 10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#94a3b8' }}>
              <span>Lens: <b style={{ color: '#22d3ee' }}>{String(current.lens || current.lens_mode || 'OBSERVED')}</b></span>
              <span>Target: <b style={{ color: '#f8fafc' }}>{selectedFieldId}</b></span>
              <span>Status: <b style={{ color: '#fdba74' }}>OBSERVED · CAUSE UNRESOLVED</b></span>
            </div>
            <div style={{ fontSize: 11, color: '#67e8f9', marginTop: 4, fontFamily: 'var(--f-mono, monospace)' }}>
              Evidence: {Array.isArray(current.evidence_ids) && current.evidence_ids.length > 0 ? current.evidence_ids.join(', ') : 'EV-OPERA-S1-YL-CAND-03-VH'}
            </div>
          </div>

          {/* Documentary Controls */}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
            <button type="button" className="eci-btn secondary" disabled={chapterIdx === 0} onClick={() => goChapter(chapterIdx - 1)}>
              ← {t('上一章', 'Prev')}
            </button>
            <button
              type="button"
              className="eci-btn"
              disabled={chapterIdx >= activeStory.chapters.length - 1}
              onClick={() => goChapter(chapterIdx + 1)}
            >
              {t('下一章', 'Next')} →
            </button>
            <button type="button" className="eci-btn secondary" onClick={() => setPlaying((p) => !p)}>
              {playing ? t('暫停播放', 'Pause') : t('自動播放', 'Play')}
            </button>
            <button
              type="button"
              className="eci-btn secondary"
              onClick={() => {
                setPlaying(false);
                goChapter(0);
              }}
            >
              {t('重頭開始', 'Restart')}
            </button>
            <button type="button" className="eci-btn secondary" onClick={() => setActiveTab('forensics')}>
              {t('檢視原始證據', 'View Original Evidence')}
            </button>
            <button type="button" className="eci-btn secondary" onClick={exportJson}>
              {t('匯出 JSON', 'Export JSON')}
            </button>
            <a
              className="eci-btn secondary"
              href={`/api/earth/stories/${activeStory.story_id}/export.html`}
              target="_blank"
              rel="noreferrer"
              style={{ textDecoration: 'none' }}
            >
              {t('匯出 HTML', 'Export HTML')}
            </a>
            <button
              type="button"
              className="eci-btn secondary"
              onClick={() => {
                setPlaying(false);
                setActiveStory(null);
              }}
            >
              {t('結束故事', 'Exit Story')}
            </button>
          </div>
        </div>
      )}

      <div className="eci-card" style={{ marginBottom: 0 }}>
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
        {importError && <div style={{ color: '#fdba74', fontSize: 11.5, marginTop: 4 }}>{importError}</div>}
        <button
          type="button"
          className="eci-btn secondary"
          style={{ marginTop: 6 }}
          disabled={!importJson.trim()}
          onClick={handleImport}
        >
          {t('匯入故事', 'Import Story')}
        </button>
      </div>
    </div>
  );
}
