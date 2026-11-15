import React, { useEffect, useRef, useState } from 'react';
import { type AuthorityReply, authorityChat } from '../api/authorityAgent';
import { type TwAgroReliefCatalog, type TwAgroReliefEstimateResponse, estimateRelief, fetchReliefCatalog } from '../api/tw05';
import { CASE, OFFICIAL_LOSS, type Parcel, bigNtd, parcelById } from '../data/champi';
import { type CropKey, type FarmerInfo, cropName } from '../data/farmer';
import { SUGGESTED_QUESTIONS, formatDb } from '../demo/fields';
import { useMascotCue } from '../mascot/Mascot';
import { headGrid, spritePaths } from '../mascot/sprites';
import { type Lang, type Text, useLang, useT } from '../i18n';
import { Earth, Icon } from '../ui/shared';
import { type AnswerView, AuthorityAnswer } from './AuthorityAnswer';
import type { ScreenProps } from './types';

interface Message {
  role: 'user' | 'bot';
  text: string;
  pending?: boolean;
  /** The agent could not answer; nothing is made up in its place. */
  error?: boolean;
  /** Authority-mode reply, shown in the farmer or authority view. */
  authority?: AuthorityReply;
}

/** Pixel head of the farmer or the association officer, cropped to the head. */
const HEAD_BOX = { farmer: { box: '0 0 16 10', w: 22, h: 14 }, officer: { box: '3 1.5 10 9', w: 18, h: 16 } } as const;
const HEADS = { farmer: spritePaths(headGrid('farmer')), officer: spritePaths(headGrid('officer')) };

function ViewHead({ who }: { who: 'farmer' | 'officer' }) {
  return (
    <svg viewBox={HEAD_BOX[who].box} width={HEAD_BOX[who].w} height={HEAD_BOX[who].h} aria-hidden="true" shapeRendering="crispEdges">
      {HEADS[who].map((p) => (
        <path key={p.fill} fill={p.fill} d={p.d} />
      ))}
    </svg>
  );
}

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

/**
 * Relief-schedule item (附表二) for a registered crop. Crops that span several items (corn, vegetables,
 * other) have none: the user picks the item, since each has its own rate.
 */
const CROP_ITEM: Partial<Record<CropKey, string>> = {
  garlic: 'veg_6',
  peanut: 'grains_3_peanut_sweetpotato',
  sweet_potato: 'grains_3_peanut_sweetpotato',
  rice: 'unannounced_other_crop',
};
const UNKNOWN_ITEM = 'unknown_crop';

/** Why the estimate shows no amount. */
const BLOCKED: Record<string, Text> = {
  BLOCKED_UNKNOWN_CROP: { zh: '選擇救助品項後才能試算。', en: 'Pick a relief item to see an estimate.' },
  BLOCKED_UNANNOUNCED_OR_EXCLUDED_ITEM: {
    zh: '這個品項不在本次雲林縣救助公告內，沒有現金救助。',
    en: 'This item is not on this Yunlin relief announcement, so there is no cash relief.',
  },
  BLOCKED_UNVERIFIED_OR_BELOW_20_THRESHOLD: { zh: '損失率未確認或未達 20%。', en: 'Loss rate unconfirmed or below 20%.' },
  BLOCKED_BELOW_MIN_AREA_001_HA: { zh: '面積不到 0.01 公頃，不予救助。', en: 'Under 0.01 ha, which is not eligible.' },
  BLOCKED_INVALID_AREA: { zh: '面積無效。', en: 'Invalid area.' },
};

export function AssistScreen({ selectedId, go, farmer, eventId }: ScreenProps) {
  const field = parcelById(selectedId);
  if (!field) return <p role="status">Taixi field not found</p>;
  return <Assistant key={field.id} field={field} go={go} farmer={farmer} eventId={eventId} />;
}

function Assistant({ field, go, farmer }: Pick<ScreenProps, 'go' | 'farmer' | 'eventId'> & { field: Parcel }) {
  const t = useT();
  const { lang } = useLang();
  const [messages, setMessages] = useState<Message[]>(() => initialMessages(field, lang));
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const cue = useMascotCue();
  const msgsRef = useRef<HTMLDivElement>(null);
  const inflight = useRef<AbortController | null>(null);
  // Authority view by default; someone who said they are a farmer starts in the plain farmer view.
  const [view, setView] = useState<AnswerView>(farmer ? 'farmer' : 'authority');
  useEffect(() => setView(farmer ? 'farmer' : 'authority'), [!!farmer]);

  // Relief estimate from the official schedule (附表二) and the Yunlin announcements.
  const [catalog, setCatalog] = useState<TwAgroReliefCatalog | null>(null);
  const [catalogFailed, setCatalogFailed] = useState(false);
  const [item, setItem] = useState((farmer && CROP_ITEM[farmer.crop]) ?? UNKNOWN_ITEM);
  const [estimate, setEstimate] = useState<TwAgroReliefEstimateResponse | null>(null);
  useEffect(() => setItem((farmer && CROP_ITEM[farmer.crop]) ?? UNKNOWN_ITEM), [farmer]);

  useEffect(() => {
    let live = true;
    fetchReliefCatalog()
      .then((c) => live && setCatalog(c))
      .catch(() => live && setCatalogFailed(true));
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    if (!catalog) return;
    let live = true;
    setEstimate(null);
    // The ceiling assumes the whole field is approved and the 20% loss gate is met; both are stated on screen.
    estimateRelief({ crop_item_id: item, assumed_approved_area_ha: field.areaHa, assumed_loss_threshold: 'meets_20_percent' })
      .then((r) => live && setEstimate(r))
      .catch(() => live && setEstimate(null));
    return () => {
      live = false;
    };
  }, [catalog, item, field]);

  // A new field, crop or language starts a new conversation.
  useEffect(() => {
    inflight.current?.abort();
    setBusy(false);
    setMessages(initialMessages(field, lang));
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
    cue('think');
    setMessages((m) => [...m, { role: 'user', text: shown }, { role: 'bot', text: t('助手查詢法規中…', 'Checking the regulations…'), pending: true }]);
    let answer: Message;
    try {
      const r = await authorityChat({ message: sent, field_id: field.id, crop: farmer ? cropName(farmer, 'zh') : undefined, lang }, ctrl.signal);
      answer = { role: 'bot', text: '', authority: r };
      cue('happy');
    } catch (err) {
      if ((err as Error).name === 'AbortError') return;
      cue('sorry');
      answer = { role: 'bot', error: true, text: t('現在連不上，請稍後再試。', "Can't connect right now. Please try again later.") };
    }
    if (inflight.current !== ctrl) return;
    inflight.current = null;
    setBusy(false);
    setMessages((m) => [...m.slice(0, -1), answer]);
  };

  const rate = catalog?.items.find((i) => i.item_id === item)?.rate_twd_per_ha;
  const amount = estimate?.calculation_allowed ? estimate.conditional_reference_amount_twd : null;
  const deadlines = (catalog?.announcements ?? []).filter((a) => a.expired_as_of_reference_date).map((a) => a.application_end_iso);

  return (
    <>
      <div className="chat">
        <div className="chat-head" style={{ flexWrap: 'wrap', gap: 10 }}>
          <Earth size={34} />
          <h1 className="h3" style={{ margin: 0, flex: 1, minWidth: 160 }}>
            {t('補助與損失估算助手', 'Relief and loss assistant')}
          </h1>
          <span className="event" style={{ padding: '5px 9px' }}>
            <span>FIELD</span>
            <b>{field.id}</b>
          </span>
          <div className="view-switch">
            <span aria-hidden="true" onClick={() => setView('farmer')}>
              {t('農民', 'Farmer')}
            </span>
            <button
              type="button"
              role="switch"
              aria-checked={view === 'authority'}
              aria-label={t('農政專業模式', 'Authority view')}
              onClick={() => setView(view === 'authority' ? 'farmer' : 'authority')}
            >
              <span className="knob">
                <ViewHead who={view === 'authority' ? 'officer' : 'farmer'} />
              </span>
            </button>
            <span aria-hidden="true" onClick={() => setView('authority')}>
              {t('農政', 'Authority')}
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
                {m.authority ? <AuthorityAnswer reply={m.authority} view={view} farmer={farmer} /> : m.role === 'bot' ? withCitations(m.text) : m.text}
                {m.role === 'bot' && !m.authority && (
                  <div className="cites">
                    {CITATIONS.map((c, k) => (
                      <span key={c.title.zh}>
                        [{k + 1}] {t(c.title)}
                      </span>
                    ))}
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

        {deadlines.length > 0 && (
          <p className="deadline" role="note">
            <b>{t('申請期限已過', 'Applications have closed')}</b>
            {t(`公告受理至 ${deadlines.join('、')}。`, `The announcements took applications until ${deadlines.join(', ')}.`)}
          </p>
        )}

        <div className="receipt">
          <div className="line">
            <span>{t('田區', 'Field')}</span>
            <span>
              {field.id} {t(field.town)}
            </span>
          </div>
          <div className="line">
            <span>{t('作物', 'Crop')}</span>
            <span>{farmer ? `${cropName(farmer, lang)}${t('（農民登記）', ' (farmer)')}` : t('待驗證', 'Unverified')}</span>
          </div>
          <div className="line">
            <span>{t('田區面積', 'Field area')}</span>
            <span>{field.areaHa.toFixed(4)} ha</span>
          </div>
          <label className="item-pick">
            <span>{t('救助品項（附表二）', 'Relief item (Schedule 2)')}</span>
            <select value={item} onChange={(e) => setItem(e.target.value)} disabled={!catalog}>
              {catalog ? (
                catalog.items.map((i) => (
                  <option key={i.item_id} value={i.item_id}>
                    {i.display_name}
                  </option>
                ))
              ) : (
                <option value={item}>{catalogFailed ? t('試算服務連不上', 'Estimate service unavailable') : t('載入中…', 'Loading…')}</option>
              )}
            </select>
          </label>
          <div className="line">
            <span>{t('救助單價', 'Rate')}</span>
            <span>{rate ? `${rate.toLocaleString()} /ha` : '—'}</span>
          </div>
          <hr />
          <div className="total">
            <span className="cap">{t('試算上限', 'Estimated ceiling')}</span>
            <b>{amount != null ? `NT$ ${amount.toLocaleString()}` : '—'}</b>
          </div>
          {amount != null ? (
            <p className="cap">{t('假設整塊田核定、損失率達 20%。', 'Assumes the whole field is approved and the loss rate reaches 20%.')}</p>
          ) : (
            estimate && <p className="cap">{t(BLOCKED[estimate.result_status] ?? { zh: estimate.result_label, en: estimate.result_label })}</p>
          )}
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
