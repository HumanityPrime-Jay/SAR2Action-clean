import React, { useState } from 'react';
import { useLang, useT } from '../../i18n';
import { useEarthContext } from '../EarthContext';
import { earthApi, type GuidedDiscoveryResponse } from '../api';

const QUICK_QUERIES = [
  { zh: '帶我看看台灣的研究案例。', en: 'Show me the Taiwan study case.' },
  { zh: '選擇第三塊農田。', en: 'Select the third farmland parcel.' },
  { zh: '切換到未知證據透鏡。', en: 'Switch to Unknown Reality Lens.' },
  { zh: '這個數字是什麼意思？', en: 'What does this number mean?' },
  { zh: '產生互動式地球故事。', en: 'Generate an interactive Earth story.' },
];

export function GuidedDiscoveryPanel() {
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
  } = useEarthContext();

  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GuidedDiscoveryResponse | null>(null);

  const submit = async (text: string) => {
    if (!text.trim() || loading) return;
    setLoading(true);
    try {
      const res = await earthApi.guidedDiscovery({
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
      applyMapActions(res.actions);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="eci-glass">
      <div className="eci-header">
        <div>
          <span className="eci-badge">AI GUIDED DISCOVERY · ALLOWLISTED ACTIONS</span>
          <h3 className="h3" style={{ margin: '6px 0 0', color: '#f8fafc' }}>
            {t('自然語言地球探索 (Gemini / 確定性)', 'AI Guided Earth Exploration')}
          </h3>
        </div>
        <div className="eci-tabs" style={{ marginBottom: 0 }}>
          <button
            className="eci-tab"
            aria-selected={userMode === 'FARMER'}
            onClick={() => setUserMode('FARMER')}
          >
            FARMER
          </button>
          <button
            className="eci-tab"
            aria-selected={userMode === 'AUTHORITY'}
            onClick={() => setUserMode('AUTHORITY')}
          >
            AUTHORITY
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
        {QUICK_QUERIES.map((q) => (
          <button key={q.zh} className="eci-btn secondary" style={{ fontSize: 12 }} onClick={() => submit(t(q.zh, q.en))}>
            {t(q.zh, q.en)}
          </button>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(query);
          setQuery('');
        }}
        style={{ display: 'flex', gap: 8 }}
      >
        <input
          className="eci-input"
          aria-label={t('輸入自然語言探索指令', 'Guided discovery query')}
          placeholder={t('例如：幫我放大雲林台西、為什麼不能確認是農損？', 'e.g., Zoom to Taixi Yunlin, or Why is damage not confirmed?')}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="eci-btn" disabled={loading || !query.trim()}>
          {loading ? t('解析中…', 'Running…') : t('執行', 'Explore')}
        </button>
      </form>

      {result && (
        <div className="eci-card active" style={{ marginTop: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6 }}>
            <span className="eci-badge">{result.execution_mode} · {result.user_mode}</span>
            <span className="eci-badge muted">Validated Actions: {result.validated_actions_count}</span>
          </div>
          <p style={{ fontSize: 13, color: '#f1f5f9', margin: '8px 0' }}>{result.answer}</p>
          <div style={{ fontSize: 11.5, color: '#67e8f9', fontFamily: 'var(--f-mono, monospace)' }}>
            Actions: {result.actions.map((a) => a.action).join(' → ') || 'NONE'}
          </div>
        </div>
      )}
    </div>
  );
}
