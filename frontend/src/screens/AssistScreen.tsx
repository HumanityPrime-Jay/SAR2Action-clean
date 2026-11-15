import React, { useEffect, useRef, useState } from 'react';
import { describeSource, farmerChat, replySources } from '../api/farmerAgent';
import { CASE, OFFICIAL_LOSS, type Parcel, bigNtd, parcelById } from '../data/champi';
import { type FarmerInfo, cropName } from '../data/farmer';
import { RELIEF_RATE_PER_HA, SUGGESTED_QUESTIONS, formatDb } from '../demo/fields';
import { useMascotCue } from '../mascot/Mascot';
import { type Lang, type Text, useLang, useT } from '../i18n';
import { Earth, Icon } from '../ui/shared';
import type { ScreenProps } from './types';
import {
  type AgentStatusInfo,
  type Tw05InvestigationResponse,
  type TwAgroReliefCatalog,
  type TwAgroReliefEstimateResponse,
  estimateRelief,
  fetchAgentStatus,
  fetchReliefCatalog,
  investigateTw05,
} from '../api/tw05';

interface Message {
  role: 'user' | 'bot';
  text: string;
  pending?: boolean;
  /** The agent could not answer; nothing is made up in its place. */
  error?: boolean;
  /** Agent reply sources (regulation articles). The opening summary uses CITATIONS instead. */
  sources?: string[];
  /** The English UI asked for English but the agent could only answer in Chinese. */
  untranslated?: boolean;
  executionMode?: string;
  facts?: Array<{ statement: string; metric: string; value: string; sensor: string; evidenceIds: string[] }>;
  inferences?: Array<{ statement: string; status: string; reason: string }>;
  unknowns?: string[];
  toolTrace?: Array<{ tool: string; status: string; duration_ms?: number | null }>;
  evidenceIds?: string[];
}

const newSessionId = () => `assist-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

/** Render "[1]" style citation markers as superscripts. */
function withCitations(text: string) {
  return text.split(/(\[\d+\])/g).map((part, i) => (/^\[\d+\]$/.test(part) ? <sup key={i}>{part}</sup> : part));
}

const CITATIONS: { title: Text; url?: string }[] = [
  { title: { zh: `SAR 調查報告 ${CASE.id}`, en: `SAR investigation ${CASE.id}` } },
  {
    title: { zh: `農業部災損統計（${OFFICIAL_LOSS.date}）`, en: `MOA loss report (${OFFICIAL_LOSS.date})` },
    url: OFFICIAL_LOSS.url,
  },
  { title: { zh: '農業天然災害救助辦法', en: 'Agricultural Natural Disaster Relief Regulations' } },
];

function initialMessages(parcel: Parcel, lang: Lang): Message[] {
  const yunlin = bigNtd(OFFICIAL_LOSS.yunlinNtd, lang);
  if (lang === 'en') {
    return [
      { role: 'user', text: `Was ${parcel.id} damaged by Typhoon Champi? Can I apply for relief?` },
      {
        role: 'bot',
        text: `Radar shows ${formatDb(parcel.preToPost)} on ${parcel.id}, but 2025 looked similar, so it may not be the typhoon.[1]\n\nYunlin lost about NT$ ${yunlin} county-wide.[2] Relief depends on the announcement and a site inspection.[3]`,
      },
    ];
  }
  return [
    { role: 'user', text: `${parcel.id} 這次薔琵颱風有受損嗎？可以申請補助嗎？` },
    {
      role: 'bot',
      text: `${parcel.id} 颱風前後雷達變化 ${formatDb(parcel.preToPost)}，但去年同期也差不多，不一定是颱風造成的。[1]\n\n雲林縣農損約 ${yunlin} 元（全縣）。[2] 能不能申請救助，要看公告和現場勘查。[3]`,
    },
  ];
}

const TW05_PRESET_PARCELS = [
  { id: 74, label: '坵塊 #74（Sentinel-1 雷達 + Sentinel-2 光學）', areaHa: 0.2815, defaultCrop: 'grains_3_peanut_sweetpotato' },
  { id: 174, label: '坵塊 #174（Sentinel-1 雷達，Sentinel-2 光學品質不足）', areaHa: 0.1982, defaultCrop: 'garlic' },
  { id: 4183, label: '坵塊 #4183（法定救助精度回歸測試 0.453978 ha）', areaHa: 0.453978, defaultCrop: 'grains_3_peanut_sweetpotato' },
];

export function AssistScreen({ selectedId, go, farmer, eventId }: ScreenProps) {
  const field = parcelById(selectedId);
  if (!field) return <p role="status">Taixi field not found</p>;
  return <RecordedAssist key={field.id} field={field} go={go} farmer={farmer} eventId={eventId} />;
}

function RecordedAssist({ field, go, farmer, eventId }: Pick<ScreenProps, 'go' | 'farmer' | 'eventId'> & { field: Parcel }) {
  const t = useT();
  const { lang } = useLang();
  const [messages, setMessages] = useState<Message[]>(() => initialMessages(field, lang));
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const cue = useMascotCue();
  const msgsRef = useRef<HTMLDivElement>(null);
  const session = useRef(newSessionId());
  const inflight = useRef<AbortController | null>(null);
  const abortCtrl = useRef<AbortController | null>(null);

  // Target scope: 'taixi' for demo field, 'tw05' for verified Yunlin parcels
  const [activeScope, setActiveScope] = useState<'taixi' | 'tw05'>('taixi');
  const [tw05ParcelId, setTw05ParcelId] = useState<number>(74);
  const [agentMode, setAgentMode] = useState<'deterministic' | 'gemini'>('deterministic');
  const [agentStatus, setAgentStatus] = useState<AgentStatusInfo | null>(null);

  // Relief estimation state
  const [catalog, setCatalog] = useState<TwAgroReliefCatalog | null>(null);
  const [selectedCrop, setSelectedCrop] = useState<string>('grains_3_peanut_sweetpotato');
  const [assumedAreaHa, setAssumedAreaHa] = useState<string>('0.453978');
  const [lossThreshold, setLossThreshold] = useState<
    'unverified' | 'below_20_percent' | 'meets_20_percent' | 'article_12_simplified_exception'
  >('meets_20_percent');
  const [estimateResult, setEstimateResult] = useState<TwAgroReliefEstimateResponse | null>(null);
  const [estimating, setEstimating] = useState(false);

  // Load status and catalog lazily when entering TW-05 mode
  useEffect(() => {
    if (activeScope !== 'tw05' || (agentStatus && catalog)) return;
    let mounted = true;
    if (!agentStatus) {
      fetchAgentStatus()
        .then((st) => {
          if (mounted) setAgentStatus(st);
        })
        .catch(() => {});
    }
    if (!catalog) {
      fetchReliefCatalog()
        .then((cat) => {
          if (mounted) setCatalog(cat);
        })
        .catch(() => {});
    }
    return () => {
      mounted = false;
    };
  }, [activeScope, agentStatus, catalog]);

  // Update default crop if farmer provided one
  useEffect(() => {
    if (farmer?.crop === 'garlic') setSelectedCrop('garlic');
    else if (farmer?.crop === 'peanut' || farmer?.crop === 'sweet_potato') setSelectedCrop('grains_3_peanut_sweetpotato');
    else if (farmer?.crop === 'rice') setSelectedCrop('paddy_rice');
  }, [farmer]);

  // A new field, crop or language starts a new conversation with the agent.
  useEffect(() => {
    inflight.current?.abort();
    abortCtrl.current?.abort();
    session.current = newSessionId();
    setBusy(false);
    if (activeScope === 'taixi') {
      setMessages(initialMessages(field, lang));
    } else {
      const pInfo = TW05_PRESET_PARCELS.find((p) => p.id === tw05ParcelId);
      const area = pInfo?.areaHa ?? 0.453978;
      setAssumedAreaHa(String(area));
      if (pInfo?.defaultCrop) setSelectedCrop(pInfo.defaultCrop);

      setMessages([
        {
          role: 'bot',
          text:
            lang === 'en'
              ? `Loaded TW-05 Yunlin verified parcel #${tw05ParcelId}. Ready to query Sentinel-1 radar changes, Sentinel-2 optical QA, or calculate statutory relief.`
              : `已載入 TW-05 雲林實測農田 #${tw05ParcelId}。可針對 Sentinel-1 雷達回波、Sentinel-2 光學品質或法定救助條件進行提問與試算。`,
        },
      ]);
    }
  }, [field, farmer, lang, activeScope, tw05ParcelId]);

  // Recalculate relief estimate when in TW-05 mode
  useEffect(() => {
    if (activeScope !== 'tw05') return;
    const areaNum = parseFloat(assumedAreaHa);
    if (isNaN(areaNum) || areaNum <= 0) return;

    let cancelled = false;
    setEstimating(true);
    estimateRelief({
      parcel_feature_id: tw05ParcelId,
      crop_item_id: selectedCrop,
      assumed_approved_area_ha: areaNum,
      assumed_loss_threshold: lossThreshold,
      allow_cross_aoi_boundary_area: true,
    })
      .then((res) => {
        if (!cancelled) setEstimateResult(res);
      })
      .catch(() => {
        if (!cancelled) setEstimateResult(null);
      })
      .finally(() => {
        if (!cancelled) setEstimating(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeScope, tw05ParcelId, selectedCrop, assumedAreaHa, lossThreshold]);

  useEffect(() => {
    const el = msgsRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  useEffect(() => () => {
    inflight.current?.abort();
    abortCtrl.current?.abort();
  }, []);

  /** `shown` is what the chat displays; `sent` is what the agent receives (Chinese skips a translation step). */
  const ask = async (shown: string, sent = shown) => {
    if (!shown.trim() || busy) return;

    if (activeScope === 'taixi') {
      const ctrl = new AbortController();
      inflight.current = ctrl;
      setBusy(true);
      cue('think');
      setMessages((m) => [...m, { role: 'user', text: shown }, { role: 'bot', text: t('助手查詢法規中…', 'Checking the regulations…'), pending: true }]);
      let answer: Message;
      try {
        const r = await farmerChat(
          {
            session_id: session.current,
            message: sent,
            selected_field_id: field.id,
            optional_event_id: eventId ?? undefined,
            crop: farmer ? cropName(farmer, 'zh') : undefined,
            lang,
          },
          ctrl.signal,
        );
        answer = { role: 'bot', text: r.reply, sources: replySources(r), untranslated: lang === 'en' && r.reply_language !== 'en' };
        cue('happy');
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        cue('sorry');
        answer = {
          role: 'bot',
          error: true,
          text: t('現在連不上，請稍後再試。', "Can't connect right now. Please try again later."),
        };
      }
      if (inflight.current !== ctrl) return;
      inflight.current = null;
      setBusy(false);
      setMessages((m) => [...m.slice(0, -1), answer]);
      return;
    }

    // Live TW-05 Agent Call
    if (abortCtrl.current) abortCtrl.current.abort();
    const ctrl = new AbortController();
    abortCtrl.current = ctrl;
    setBusy(true);
    cue('think');

    setMessages((m) => [
      ...m,
      { role: 'user', text: shown },
      { role: 'bot', text: t('Agent 執行 Tool Calling 調查中…', 'Agent executing tool calls…'), pending: true },
    ]);

    investigateTw05(
      {
        parcel_feature_id: tw05ParcelId,
        question: shown,
        agent_mode: agentMode,
        session_id: `session-tw05-${tw05ParcelId}-${Date.now()}`,
      },
      ctrl.signal,
    )
      .then((res: Tw05InvestigationResponse) => {
        if (abortCtrl.current !== ctrl) return;
        const factsSummary = res.observed_facts.map((f) => ({
          statement: f.statement,
          metric: f.metric_name,
          value: f.verified_value_str,
          sensor: f.sensor_or_source,
          evidenceIds: f.evidence_ids,
        }));
        const infSummary = res.inferences.map((i) => ({
          statement: i.statement,
          status: i.status,
          reason: i.reason,
        }));
        const traceSummary = res.tool_trace.map((tr) => ({
          tool: tr.tool,
          status: tr.status,
          duration_ms: tr.duration_ms,
        }));

        cue(res.status === 'blocked' ? 'sorry' : 'happy');
        let botReplyText = '';
        if (res.status === 'blocked') {
          botReplyText = `[${res.execution_mode}] ${res.error?.message || 'Agent blocked request.'}`;
        } else {
          botReplyText = `【${res.execution_mode}】針對農田 #${tw05ParcelId} 調查完成：\n` +
            `• 確認觀測事實：${res.observed_facts.length} 項\n` +
            `• 分析推論：${res.inferences.length} 項\n` +
            `• 未知事項：${res.unknowns.length} 項\n` +
            `• 關聯 Evidence ID：${res.evidence_ids.join(', ')}`;
        }

        setMessages((m) => [
          ...m.slice(0, -1),
          {
            role: 'bot',
            text: botReplyText,
            executionMode: res.execution_mode,
            facts: factsSummary,
            inferences: infSummary,
            unknowns: res.unknowns,
            toolTrace: traceSummary,
            evidenceIds: res.evidence_ids,
          },
        ]);
      })
      .catch((err: Error) => {
        if (err.name === 'AbortError' || abortCtrl.current !== ctrl) return;
        cue('sorry');
        setMessages((m) => [
          ...m.slice(0, -1),
          {
            role: 'bot',
            text: `[ERROR] ${err.message}`,
          },
        ]);
      })
      .finally(() => {
        if (abortCtrl.current === ctrl) {
          abortCtrl.current = null;
          setBusy(false);
        }
      });
  };

  const ceiling = Math.round(field.areaHa * RELIEF_RATE_PER_HA);

  return (
    <>
      <div className="chat">
        <div className="chat-head" style={{ flexWrap: 'wrap', gap: 10 }}>
          <Earth size={34} />
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <h1 className="h3" style={{ margin: 0 }}>{t('補助與損失估算助手', 'Relief and loss assistant')}</h1>
              {activeScope === 'tw05' ? (
                <span
                  className="stamp"
                  style={{
                    fontSize: 11,
                    background: agentStatus?.gemini?.api_key_configured ? '#E6F4EA' : '#E8F0FE',
                    color: agentStatus?.gemini?.api_key_configured ? '#137333' : '#1A73E8',
                    border: '1px solid currentColor',
                  }}
                >
                  {agentStatus?.gemini?.api_key_configured ? 'GEMINI LIVE READY' : 'TW-05 AGENT (FAIL-CLOSED / DETERMINISTIC)'}
                </span>
              ) : (
                <span className="stamp outline" style={{ fontSize: 11 }}>
                  DEMO · TAIXI
                </span>
              )}
            </div>
          </div>

          {/* Scope & Field Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <div className="seg" role="group" aria-label="案例切換">
              <button type="button" aria-pressed={activeScope === 'taixi'} onClick={() => setActiveScope('taixi')} style={{ minHeight: 32, padding: '0 10px', fontSize: 12 }}>
                {t('臺西示範', 'Taixi demo')} ({field.id})
              </button>
              <button type="button" aria-pressed={activeScope === 'tw05'} onClick={() => setActiveScope('tw05')} style={{ minHeight: 32, padding: '0 10px', fontSize: 12 }}>
                {t('TW-05 雲林實測', 'TW-05 Yunlin live')}
              </button>
            </div>

            {activeScope === 'tw05' && (
              <select
                aria-label="選擇 TW-05 農田"
                value={tw05ParcelId}
                onChange={(e) => setTw05ParcelId(Number(e.target.value))}
                style={{ padding: '4px 8px', fontSize: 12, borderRadius: 4, border: '1px solid var(--border-strong)' }}
              >
                {TW05_PRESET_PARCELS.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            )}

            {activeScope === 'tw05' && (
              <select
                aria-label="Agent 執行模式"
                value={agentMode}
                onChange={(e) => setAgentMode(e.target.value as 'deterministic' | 'gemini')}
                style={{ padding: '4px 8px', fontSize: 12, borderRadius: 4, border: '1px solid var(--border-strong)' }}
              >
                <option value="deterministic">DETERMINISTIC</option>
                <option value="gemini">GEMINI LIVE</option>
              </select>
            )}

            <span className="event" style={{ padding: '5px 9px' }}>
              <span>FIELD</span>
              <b>{activeScope === 'taixi' ? field.id : `#${tw05ParcelId}`}</b>
            </span>
          </div>
        </div>

        <div className="msgs" ref={msgsRef} aria-live="polite">
          {messages.map((m, i) =>
            m.pending ? (
              <div key={i} className="msg typing">
                {m.text}
              </div>
            ) : m.error ? (
              <div key={i} className="msg bot error" role="alert">
                <span className="eyebrow">{t('AGENT 無法使用', 'AGENT UNAVAILABLE')}</span>
                {m.text}
              </div>
            ) : (
              <div key={i} className={`msg ${m.role}`}>
                {m.untranslated && <span className="eyebrow note">Shown in Chinese</span>}
                {m.role === 'bot' && !m.sources ? withCitations(m.text) : m.text}

                {/* Additional Agent Inspection Badges & Details for TW-05 */}
                {m.executionMode && (
                  <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <span
                      style={{
                        padding: '2px 6px',
                        borderRadius: 3,
                        fontSize: 11,
                        fontFamily: 'var(--f-mono)',
                        background: m.executionMode.includes('LIVE') ? '#E6F4EA' : '#E8F0FE',
                        color: m.executionMode.includes('LIVE') ? '#137333' : '#1A73E8',
                        fontWeight: 600,
                      }}
                    >
                      {m.executionMode}
                    </span>
                  </div>
                )}

                {/* Observed Facts Accordion */}
                {m.facts && m.facts.length > 0 && (
                  <details style={{ marginTop: 8, fontSize: 13, background: 'var(--surface)', padding: '6px 10px', borderRadius: 4, border: '1px solid var(--border)' }}>
                    <summary style={{ cursor: 'pointer', fontWeight: 600 }}>
                      觀測事實清單 ({m.facts.length} 項)
                    </summary>
                    <ul style={{ margin: '6px 0 0 16px', padding: 0 }}>
                      {m.facts.map((f, idx) => (
                        <li key={idx} style={{ marginBottom: 4 }}>
                          <b>[{f.sensor}]</b> {f.metric}: <code>{f.value}</code> — {f.statement}
                          <br />
                          <small style={{ color: 'var(--text-3)' }}>Evidence: {f.evidenceIds.join(', ')}</small>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}

                {/* Tool Trace Accordion */}
                {m.toolTrace && m.toolTrace.length > 0 && (
                  <details style={{ marginTop: 6, fontSize: 12, background: 'var(--surface)', padding: '6px 10px', borderRadius: 4, border: '1px solid var(--border)' }}>
                    <summary style={{ cursor: 'pointer', fontWeight: 600 }}>
                      Tool Calling 追蹤紀錄 ({m.toolTrace.length} 步驟)
                    </summary>
                    <div style={{ marginTop: 4, display: 'flex', flexDirection: 'column', gap: 3 }}>
                      {m.toolTrace.map((tr, idx) => (
                        <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--f-mono)', fontSize: 11 }}>
                          <span>{tr.tool}</span>
                          <span style={{ color: tr.status === 'complete' ? '#137333' : '#D93025' }}>
                            {tr.status} {tr.duration_ms ? `(${tr.duration_ms.toFixed(1)}ms)` : ''}
                          </span>
                        </div>
                      ))}
                    </div>
                  </details>
                )}

                {/* Evidence Citations */}
                {m.evidenceIds && m.evidenceIds.length > 0 && (
                  <div className="cites">
                    {m.evidenceIds.map((eid) => (
                      <span key={eid} style={{ fontFamily: 'var(--f-mono)' }}>
                        [{eid}]
                      </span>
                    ))}
                  </div>
                )}

                {/* Traditional Citations for opening summary */}
                {m.role === 'bot' && !m.evidenceIds && !m.sources && (
                  <div className="cites">
                    {CITATIONS.map((c, k) => (
                      <span key={c.title.zh}>
                        [{k + 1}] {t(c.title)}
                      </span>
                    ))}
                  </div>
                )}
                {m.sources && (
                  <div className="cites">
                    {m.sources.length ? (
                      m.sources.map((id) => {
                        const src = describeSource(id);
                        return src.url ? (
                          <a key={id} href={src.url} target="_blank" rel="noreferrer">
                            {t(src.title)}
                          </a>
                        ) : (
                          <span key={id}>{t(src.title)}</span>
                        );
                      })
                    ) : (
                      <span className="none">{t('這段回答沒有引用條文', 'No article cited for this reply')}</span>
                    )}
                  </div>
                )}
              </div>
            ),
          )}
        </div>

        <div className="suggest">
          {SUGGESTED_QUESTIONS.map((q) => (
            <button key={q.key} disabled={busy} onClick={() => ask(t(q.text), q.text.zh)}>
              {t(q.text)}
            </button>
          ))}
        </div>

        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            ask(draft);
            setDraft('');
          }}
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={
              activeScope === 'tw05'
                ? t('向 Agent 詢問此坵塊雷達、光學與救助判定…', 'Ask Agent about radar, optical QA and relief…')
                : t('現金救助的門檻是多少？', 'What is the threshold for cash relief?')
            }
            autoComplete="off"
            aria-label={t('輸入問題', 'Your question')}
          />
          <button className="send" aria-label={t('送出', 'Send')} disabled={!draft.trim() || busy}>
            <Icon name="send" />
          </button>
        </form>
      </div>

      <aside className="panel">
        <div className="panel-head">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="eyebrow">{activeScope === 'tw05' ? 'Statutory Relief Engine' : 'Estimate'}</div>
            <span className="stamp outline">{t('試算 · 非核定', 'ESTIMATE · NOT APPROVED')}</span>
          </div>
          <h2 className="h3">{t('救助參考試算', 'Relief estimate')}</h2>
        </div>

        {activeScope === 'taixi' ? (
          /* Taixi Demo Receipt (Preserves exact DOM shape and values for App.test.tsx) */
          <div className="receipt">
            <div className="line">
              <span>{t('田區', 'Field')}</span>
              <span>
                {field.id} {t(field.town)}
              </span>
            </div>
            {farmer?.cadastral && (
              <div className="line">
                <span>{t('土地地籍', 'Land parcel no.')}</span>
                <span>{farmer.cadastral}</span>
              </div>
            )}
            <div className="line">
              <span>{t('作物', 'Crop')}</span>
              <span>{farmer ? `${cropName(farmer, lang)}${t('（農民登記）', ' (farmer)')}` : t('待驗證', 'Unverified')}</span>
            </div>
            <div className="line">
              <span>{t('田區面積', 'Field area')}</span>
              <span>{field.areaHa.toFixed(4)} ha</span>
            </div>
            <div className="line">
              <span>{t('核認受損面積', 'Confirmed damaged area')}</span>
              <span>{t('待現場勘查', 'Pending inspection')}</span>
            </div>
            <div className="line">
              <span>{t('救助單價', 'Rate')}</span>
              <span>{RELIEF_RATE_PER_HA.toLocaleString()} /ha</span>
            </div>
            <hr />
            <div className="total">
              <span className="cap">{t('試算上限', 'Estimated ceiling')}</span>
              <b>NT$ {ceiling.toLocaleString()}</b>
            </div>
            <div className="line">
              <span>{t('救助資格', 'Eligibility')}</span>
              <span>{t('待主管機關認定', 'Decided by the authority')}</span>
            </div>
            <div className="official">
              <span className="eyebrow">
                {t('官方災損 · 農業部', 'OFFICIAL LOSS · MOA')} {OFFICIAL_LOSS.date}
              </span>
              <span>
                {t('雲林縣', 'Yunlin')} <b>NT$ {bigNtd(OFFICIAL_LOSS.yunlinNtd, lang)}</b> · {t('全國', 'Taiwan')} NT$ {bigNtd(OFFICIAL_LOSS.taiwanNtd, lang)}
              </span>
            </div>
          </div>
        ) : (
          /* TW-07.2 Live Statutory Relief Estimator */
          <div className="receipt">
            <div style={{ background: '#FFF8E1', border: '1px solid #FFE082', padding: '6px 10px', borderRadius: 4, fontSize: 11, color: '#B78103' }}>
              ⚠️ <b>CONDITIONAL ESTIMATE / NOT OFFICIAL</b>: 金額為使用者明示假設下之法定試算，實際核定以公所現勘為準。
            </div>

            <div className="line" style={{ marginTop: 4 }}>
              <span>{t('坵塊編號', 'Parcel ID')}</span>
              <span>#{tw05ParcelId}</span>
            </div>

            {/* Statutory Crop Selection */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 12, color: 'var(--text-2)' }}>{t('作物品項（法定公告附表二）', 'Crop item (MOA Sched. II)')}</span>
              <select
                aria-label="選擇法定救助作物"
                value={selectedCrop}
                onChange={(e) => setSelectedCrop(e.target.value)}
                style={{ padding: '6px 8px', fontSize: 12, borderRadius: 4, border: '1px solid var(--border-strong)' }}
              >
                {catalog?.items
                  .filter((it) => it.rate_twd_per_ha)
                  .map((it) => (
                    <option key={it.item_id} value={it.item_id}>
                      {it.display_name} (NT$ {it.rate_twd_per_ha?.toLocaleString()}/ha)
                    </option>
                  ))}
              </select>
            </div>

            {/* Assumed Area Input */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 12, color: 'var(--text-2)' }}>{t('假設核認面積 (ha)', 'Assumed area (ha)')}</span>
                <span style={{ fontSize: 10, color: 'var(--text-3)' }}>未預先四捨五入</span>
              </div>
              <input
                type="number"
                step="0.000001"
                min="0.001"
                aria-label="假設核認面積"
                value={assumedAreaHa}
                onChange={(e) => setAssumedAreaHa(e.target.value)}
                style={{ padding: '6px 8px', fontSize: 13, borderRadius: 4, border: '1px solid var(--border-strong)' }}
              />
            </div>

            {/* Loss Threshold Condition */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 12, color: 'var(--text-2)' }}>{t('損害率情境假設', 'Loss threshold assumption')}</span>
              <select
                aria-label="損害率門檻"
                value={lossThreshold}
                onChange={(e) =>
                  setLossThreshold(
                    e.target.value as 'unverified' | 'below_20_percent' | 'meets_20_percent' | 'article_12_simplified_exception',
                  )
                }
                style={{ padding: '6px 8px', fontSize: 12, borderRadius: 4, border: '1px solid var(--border-strong)' }}
              >
                <option value="meets_20_percent">損害率達 20% 以上（符合法定一般門檻）</option>
                <option value="article_12_simplified_exception">第 12 條簡化程序例外情境（使用者情境假設）</option>
                <option value="below_20_percent">未達 20% 門檻（法定不予救助）</option>
                <option value="unverified">未確認損害率（阻擋試算金額）</option>
              </select>
            </div>

            <hr />

            {/* Calculated Result */}
            <div className="total">
              <span className="cap">{t('條件式參考救助額', 'Conditional estimate')}</span>
              <b>
                {estimating
                  ? '計算中…'
                  : estimateResult?.calculation_allowed && estimateResult.conditional_reference_amount_twd != null
                  ? `NT$ ${estimateResult.conditional_reference_amount_twd.toLocaleString()}`
                  : 'NT$ 0'}
              </b>
            </div>

            {estimateResult?.formula_display && (
              <div style={{ fontSize: 12, fontFamily: 'var(--f-mono)', color: 'var(--text-2)', background: 'var(--surface-3)', padding: '4px 8px', borderRadius: 3 }}>
                {estimateResult.formula_display}
              </div>
            )}

            {estimateResult?.blocked_reason && (
              <div style={{ fontSize: 12, color: '#D93025', background: '#FCE8E6', padding: '6px 10px', borderRadius: 4 }}>
                🛑 {estimateResult.blocked_reason}
              </div>
            )}

            <div className="line">
              <span>{t('救助資格認定', 'Official status')}</span>
              <span style={{ color: '#E37400' }}>待主管機關現勘核認</span>
            </div>
          </div>
        )}

        <div className="eyebrow" style={{ padding: '8px 20px 4px' }}>
          {t('References 引用來源', 'References')}
        </div>
        {CITATIONS.map((c, k) => (
          <div key={c.title.zh} className="src">
            <span className="mono">[{k + 1}]</span>
            <span>
              {c.url ? (
                <a className="link" href={c.url} target="_blank" rel="noreferrer">
                  {t(c.title)}
                </a>
              ) : (
                t(c.title)
              )}
            </span>
          </div>
        ))}

        <div style={{ flex: 1 }} />
        <div className="panel-foot">
          <button className="btn btn-line btn-block" onClick={() => go('compare')}>
            {t('← 回到田區比對', '← Back to field compare')}
          </button>
        </div>
      </aside>
    </>
  );
}
