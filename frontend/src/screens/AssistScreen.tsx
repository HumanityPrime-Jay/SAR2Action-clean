import React, { useEffect, useRef, useState } from 'react';
import { describeSource, farmerChat, replySources } from '../api/farmerAgent';
import { CASE, OFFICIAL_LOSS, type Parcel, bigNtd, parcelById } from '../data/champi';
import { type FarmerInfo, cropName } from '../data/farmer';
import { RELIEF_RATE_PER_HA, SUGGESTED_QUESTIONS, formatDb } from '../demo/fields';
import { type Lang, type Text, useLang, useT } from '../i18n';
import { Earth, Icon } from '../ui/shared';
import type { ScreenProps } from './types';

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
}

const newSessionId = () => `assist-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

/** Render "[1]" style citation markers as superscripts. */
function withCitations(text: string) {
  return text.split(/(\[\d+\])/g).map((part, i) => (/^\[\d+\]$/.test(part) ? <sup key={i}>{part}</sup> : part));
}

const CITATIONS: { title: Text; kind: Text; url?: string }[] = [
  { title: { zh: `SAR 調查報告 ${CASE.id}`, en: `SAR investigation ${CASE.id}` }, kind: { zh: '團隊雷達觀測與 QA', en: 'Team radar observations and QA' } },
  {
    title: { zh: `農業部災損統計（${OFFICIAL_LOSS.date}）`, en: `MOA loss report (${OFFICIAL_LOSS.date})` },
    kind: { zh: '官方公告', en: 'Official release' },
    url: OFFICIAL_LOSS.url,
  },
  { title: { zh: '農業天然災害救助辦法', en: 'Agricultural Natural Disaster Relief Regulations' }, kind: { zh: '法規資料庫 · RAG', en: 'Law database · RAG' } },
];

function initialMessages(parcel: Parcel, farmer: FarmerInfo | null, lang: Lang): Message[] {
  const yunlin = bigNtd(OFFICIAL_LOSS.yunlinNtd, lang);
  if (lang === 'en') {
    const crop = farmer ? `You reported ${cropName(farmer, lang).toLowerCase()}; that still needs verification.` : 'The crop type is not verified yet.';
    return [
      { role: 'user', text: `Was ${parcel.id} damaged by Typhoon Champi? Can I apply for relief?` },
      {
        role: 'bot',
        text: `Satellite radar saw a VH change of ${formatDb(parcel.preToPost)} on field ${parcel.id} across the typhoon, but a similar swing happened in 2025, so typhoon damage cannot be confirmed. ${crop}[1]\n\nThe Ministry of Agriculture reported about NT$ ${yunlin} of farm losses in Yunlin on ${OFFICIAL_LOSS.date}, but that is a county total and does not map to this field.[2]\n\nCash relief depends on the announced areas, eligible crops and the area confirmed by an on-site inspection; the authority makes the final decision.[3] The panel on the right shows the ceiling if the whole field were confirmed.`,
      },
    ];
  }
  const crop = farmer ? `您登記的作物是${cropName(farmer, lang)}，仍需查證。` : '作物種類也還沒驗證。';
  return [
    { role: 'user', text: `${parcel.id} 這次薔琵颱風有受損嗎？可以申請補助嗎？` },
    {
      role: 'bot',
      text: `衛星雷達在颱風前後觀測到田區 ${parcel.id} 的 VH 回波變化 ${formatDb(parcel.preToPost)}，但 2025 年同期也有類似起伏，目前無法確定是颱風造成的受損。${crop}[1]\n\n農業部 ${OFFICIAL_LOSS.date} 公布雲林縣農業損失約 ${yunlin} 元，但這是全縣的數字，不能直接對應到這塊田。[2]\n\n能不能申請現金救助，要看公告範圍、作物品項與現場勘查核認的面積，最後由主管機關認定。[3] 右側是假設全區核認時的試算上限。`,
    },
  ];
}

export function AssistScreen({ selectedId, go, farmer, eventId }: ScreenProps) {
  const t = useT();
  const { lang } = useLang();
  const field = parcelById(selectedId);
  const [messages, setMessages] = useState<Message[]>(() => initialMessages(field, farmer, lang));
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const msgsRef = useRef<HTMLDivElement>(null);
  const session = useRef(newSessionId());
  const inflight = useRef<AbortController | null>(null);

  // A new field, crop or language starts a new conversation with the agent.
  useEffect(() => {
    inflight.current?.abort();
    session.current = newSessionId();
    setBusy(false);
    setMessages(initialMessages(field, farmer, lang));
  }, [field, farmer, lang]);

  useEffect(() => {
    const el = msgsRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  useEffect(() => () => inflight.current?.abort(), []);

  /** `shown` is what the chat displays; `sent` is what the agent receives (Chinese skips a translation step). */
  const ask = async (shown: string, sent = shown) => {
    if (!shown.trim() || busy) return;
    const ctrl = new AbortController();
    inflight.current = ctrl;
    setBusy(true);
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
    } catch (err) {
      if ((err as Error).name === 'AbortError') return;
      answer = {
        role: 'bot',
        error: true,
        text: t(
          'Agent 目前無法使用：後端沒有回應或 AI 金鑰無效，所以這題沒有回答。請稍後再試，或直接洽詢鄉鎮公所。',
          'The agent is unavailable: the backend did not respond or the AI key is invalid, so this question has no answer. Try again later, or ask your township office.',
        ),
      };
    }
    if (inflight.current !== ctrl) return;
    inflight.current = null;
    setBusy(false);
    setMessages((m) => [...m.slice(0, -1), answer]);
  };

  const ceiling = Math.round(field.areaHa * RELIEF_RATE_PER_HA);

  return (
    <>
      <div className="chat">
        <div className="chat-head">
          <Earth size={34} />
          <div style={{ flex: 1 }}>
            <h1 className="h3">{t('補助與損失估算助手', 'Relief and loss assistant')}</h1>
            <div className="cap">
              {t('依農業災害救助相關法規回答，並附上依據的條文', 'Answers from the agricultural relief regulations, with the articles they rely on')}
            </div>
          </div>
          <span className="event" style={{ padding: '5px 9px' }}>
            <span>FIELD</span>
            <b>{field.id}</b>
          </span>
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
                {m.untranslated && <span className="eyebrow note">Shown in Chinese: English translation is unavailable right now</span>}
                {m.role === 'bot' && !m.sources ? withCitations(m.text) : m.text}
                {m.role === 'bot' && !m.sources && (
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
            placeholder={t('現金救助的門檻是多少？', 'What is the threshold for cash relief?')}
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
            <div className="eyebrow">Estimate</div>
            <span className="stamp outline">{t('試算 · 非核定', 'ESTIMATE · NOT APPROVED')}</span>
          </div>
          <h2 className="h3">{t('救助參考試算', 'Relief estimate')}</h2>
        </div>
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
            <span>{field.areaHa} ha</span>
          </div>
          <div className="line">
            <span>{t('核認受損面積', 'Confirmed damaged area')}</span>
            <span>{t('待現場勘查', 'Pending inspection')}</span>
          </div>
          <div className="line">
            <span>{t('救助單價（示意）', 'Rate (illustrative)')}</span>
            <span>{RELIEF_RATE_PER_HA.toLocaleString()} /ha</span>
          </div>
          <hr />
          <div className="total">
            <span className="cap">{t('試算上限（若全區核認）', 'Ceiling (if the whole field is confirmed)')}</span>
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
            <span className="cap">{t('縣市層級統計，不代表個別田區損失', 'County-level totals, not losses of individual fields')}</span>
          </div>
        </div>
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
              <br />
              <span className="cap" style={{ fontSize: 12 }}>
                {t(c.kind)}
              </span>
            </span>
          </div>
        ))}
        <div style={{ flex: 1 }} />
        <div className="panel-foot">
          <button className="btn btn-primary btn-block" disabled aria-describedby="apply-soon">
            {t('產生申請資料', 'Prepare application')}
          </button>
          <p id="apply-soon" className="soon">
            {t('申請資料產生功能即將推出', 'Coming soon')}
          </p>
          <button className="btn btn-line btn-block" onClick={() => go('compare')}>
            {t('← 回到田區比對', '← Back to field compare')}
          </button>
        </div>
      </aside>
    </>
  );
}
