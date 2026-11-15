import React, { useState } from 'react';
import { useLang, useT } from '../../i18n';
import { useEarthContext } from '../EarthContext';
import { earthApi, type AIMapAction, type GuidedDiscoveryResponse } from '../api';

const QUICK_QUERIES = [
  { zh: '帶我去雲林。', en: 'Take me to Yunlin.' },
  { zh: '選擇第三塊農田。', en: 'Select the third farmland parcel.' },
  { zh: '比較這五塊田。', en: 'Compare these five fields.' },
  { zh: '播放時間軸。', en: 'Play the timeline.' },
  { zh: '解釋這個 VH 變化。', en: 'What does this number mean?' },
  { zh: '打開未知證據。', en: 'Switch to Unknown Reality Lens.' },
  { zh: '開始研究原因。', en: 'Start investigating the cause.' },
  { zh: '產生互動式地球故事。', en: 'Generate an interactive Earth story.' },
];

export function GuidedDiscoveryPanel({ compact = false }: { compact?: boolean }) {
  const t = useT();
  const { lang } = useLang();
  const {
    eventId,
    aoi,
    selectedFieldId,
    timelinePosition,
    activeLayers,
    selectedLens,
    userMode,
    setUserMode,
    applyMapActions,
    lastDiscoveryResult: result,
    setLastDiscoveryResult: setResult,
  } = useEarthContext();

  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [showChips, setShowChips] = useState(!compact);

  const submit = async (text: string) => {
    if (!text.trim() || loading) return;
    setLoading(true);
    try {
      const fn = (earthApi.guidedDiscovery || (earthApi as unknown as Record<string, typeof earthApi.guidedDiscovery>).discoveryQuery);
      const res = await fn({
        query: text,
        context: {
          event_id: eventId,
          region: aoi,
          aoi,
          selected_field_id: selectedFieldId,
          timeline_position: timelinePosition,
          active_layers: activeLayers,
          selected_lens: selectedLens,
          user_mode: userMode,
          lang,
        },
        prefer_gemini: true,
      });
      setResult(res);
      if (res?.actions?.length) {
        applyMapActions(res.actions);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="eci-glass" style={{ padding: compact ? '10px 13px' : undefined }}>
      <div className="eci-header" style={{ marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span className="eci-badge">AI GUIDED DISCOVERY</span>
          {!compact && (
            <h3 className="h3" style={{ margin: 0, fontSize: 15.5, color: '#f8fafc' }}>
              {t('自然語言地球探索', 'AI Guided Earth Exploration')}
            </h3>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          {compact && (
            <button
              type="button"
              className="eci-btn secondary"
              style={{ padding: '3px 8px', minHeight: 26, fontSize: 11 }}
              onClick={() => setShowChips((v) => !v)}
            >
              {showChips ? t('收合提示', 'Hide Prompts') : t('快捷指令 (8)', 'Prompts (8)')}
            </button>
          )}
          <div className="eci-tabs" style={{ marginBottom: 0 }}>
            <button
              type="button"
              className="eci-tab"
              style={{ padding: '4px 8px', fontSize: 11 }}
              aria-selected={userMode === 'FARMER'}
              onClick={() => setUserMode('FARMER')}
            >
              FARMER
            </button>
            <button
              type="button"
              className="eci-tab"
              style={{ padding: '4px 8px', fontSize: 11 }}
              aria-selected={userMode === 'AUTHORITY'}
              onClick={() => setUserMode('AUTHORITY')}
            >
              AUTHORITY
            </button>
          </div>
        </div>
      </div>

      {showChips && (
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 8 }}>
          {QUICK_QUERIES.map((q) => (
            <button
              key={q.zh}
              type="button"
              className="eci-btn secondary"
              style={{ fontSize: 11.5, padding: '4px 9px', minHeight: 28 }}
              onClick={() => submit(t(q.zh, q.en))}
            >
              {t(q.zh, q.en)}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(query);
          setQuery('');
        }}
        style={{ display: 'flex', gap: 6 }}
      >
        <input
          className="eci-input"
          aria-label={t('輸入自然語言探索指令', 'Guided discovery query')}
          placeholder={t('例如：帶我去雲林、比較這五塊田、播放時間軸…', 'Ask anything, e.g., Zoom to Taixi Yunlin, or Why is damage not confirmed?')}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="submit" className="eci-btn" disabled={loading || !query.trim()}>
          {loading ? t('解析中…', 'Running…') : t('執行', 'Explore')}
        </button>
      </form>

      {result && (
        <div className="eci-card active" style={{ marginTop: 8, marginBottom: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6 }}>
            <span className="eci-badge">{result.execution_mode || 'VERIFIED'} · {result.user_mode || (result as unknown as Record<string, string>).mode || userMode}</span>
            {typeof result.validated_actions_count === 'number' && (
              <span className="eci-badge ok">Validated Actions: {result.validated_actions_count}</span>
            )}
          </div>
          <p style={{ fontSize: 12.5, color: '#f1f5f9', margin: '6px 0' }}>{result.answer}</p>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: 11, color: '#67e8f9', fontFamily: 'var(--f-mono, monospace)' }}>
              Actions:{' '}
              {(result.actions || [])
                .map((a) => a.action || (a as unknown as Record<string, string>).action_type)
                .join(' → ') || 'NONE'}
            </span>
            {(result.actions || []).map((a, idx) => {
              const anyA = a as unknown as Record<string, string>;
              const lbl = anyA.label || a.action || anyA.action_type;
              return (
                <button
                  key={idx}
                  type="button"
                  className="eci-btn secondary"
                  style={{ fontSize: 11, padding: '2px 7px', minHeight: 24 }}
                  onClick={() => applyMapActions([a as AIMapAction])}
                >
                  {lbl}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
