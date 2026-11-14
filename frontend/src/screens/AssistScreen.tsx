import React, { useEffect, useRef, useState } from 'react';
import { CASE, OFFICIAL_LOSS, type Parcel, parcelById, toYi } from '../data/champi';
import { RELIEF_RATE_PER_HA, SUGGESTED_QUESTIONS, cannedReply, formatDb } from '../demo/fields';
import { Earth, Icon } from '../ui/shared';
import type { ScreenProps } from './types';

interface Message {
  role: 'user' | 'bot';
  text: string;
  pending?: boolean;
}

/** Render "[1]" style citation markers as superscripts. */
function withCitations(text: string) {
  return text.split(/(\[\d+\])/g).map((part, i) => (/^\[\d+\]$/.test(part) ? <sup key={i}>{part}</sup> : part));
}

const CITATIONS = [
  { title: `SAR 調查報告 ${CASE.id}`, kind: '團隊雷達觀測與 QA' },
  { title: `農業部災損統計（${OFFICIAL_LOSS.date}）`, kind: '官方公告', url: OFFICIAL_LOSS.url },
  { title: '農業天然災害救助辦法', kind: '法規資料庫 · RAG' },
];

function initialMessages(parcel: Parcel): Message[] {
  return [
    { role: 'user', text: `${parcel.id} 這次薔琵颱風有受損嗎？可以申請補助嗎？` },
    {
      role: 'bot',
      text: `衛星雷達在颱風前後觀測到田區 ${parcel.id} 的 VH 回波變化 ${formatDb(parcel.preToPost)}，但 2025 年同期也有類似起伏，目前無法確定是颱風造成的受損，作物種類也還沒驗證。[1]\n\n農業部 ${OFFICIAL_LOSS.date} 公布雲林縣農業損失約 ${toYi(OFFICIAL_LOSS.yunlinNtd)} 元，但這是全縣的數字，不能直接對應到這塊田。[2]\n\n能不能申請現金救助，要看公告範圍、作物品項與現場勘查核認的面積，最後由主管機關認定。[3] 右側是假設全區核認時的試算上限。`,
    },
  ];
}

export function AssistScreen({ selectedId, go }: ScreenProps) {
  const field = parcelById(selectedId);
  const [messages, setMessages] = useState<Message[]>(() => initialMessages(field));
  const [draft, setDraft] = useState('');
  const msgsRef = useRef<HTMLDivElement>(null);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    setMessages(initialMessages(field));
  }, [field]);

  useEffect(() => {
    const el = msgsRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const ask = (q: string) => {
    if (!q.trim()) return;
    setMessages((m) => [...m, { role: 'user', text: q }, { role: 'bot', text: '助手撰寫中…', pending: true }]);
    // Demo reply; replace with the agent API (Gemini + regulation RAG).
    timers.current.push(
      window.setTimeout(() => {
        setMessages((m) => [...m.slice(0, -1), { role: 'bot', text: cannedReply(q, field) }]);
      }, 700),
    );
  };

  const ceiling = Math.round(field.areaHa * RELIEF_RATE_PER_HA);

  return (
    <>
      <div className="chat">
        <div className="chat-head">
          <Earth size={34} />
          <div style={{ flex: 1 }}>
            <h1 className="h3">補助與損失估算助手</h1>
            <div className="cap">依農業災害救助相關法規回答，每段附引用來源</div>
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
            ) : (
              <div key={i} className={`msg ${m.role}`}>
                {m.role === 'bot' ? withCitations(m.text) : m.text}
                {m.role === 'bot' && (
                  <div className="cites">
                    {CITATIONS.map((c, k) => (
                      <span key={c.title}>
                        [{k + 1}] {c.title}
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
            <button key={q} onClick={() => ask(q)}>
              {q}
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
          <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="現金救助的門檻是多少？" autoComplete="off" aria-label="輸入問題" />
          <button className="send" aria-label="送出" disabled={!draft.trim()}>
            <Icon name="send" />
          </button>
        </form>
      </div>

      <aside className="panel">
        <div className="panel-head">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="eyebrow">Estimate</div>
            <span className="stamp outline">
              試算 · 非核定
            </span>
          </div>
          <h2 className="h3">救助參考試算</h2>
        </div>
        <div className="receipt">
          <div className="line">
            <span>田區</span>
            <span>
              {field.id} {field.town}
            </span>
          </div>
          <div className="line">
            <span>作物</span>
            <span>待驗證</span>
          </div>
          <div className="line">
            <span>田區面積</span>
            <span>{field.areaHa} ha</span>
          </div>
          <div className="line">
            <span>核認受損面積</span>
            <span>待現場勘查</span>
          </div>
          <div className="line">
            <span>救助單價（示意）</span>
            <span>{RELIEF_RATE_PER_HA.toLocaleString()} /ha</span>
          </div>
          <hr />
          <div className="total">
            <span className="cap">試算上限（若全區核認）</span>
            <b>NT$ {ceiling.toLocaleString()}</b>
          </div>
          <div className="line">
            <span>救助資格</span>
            <span>待主管機關認定</span>
          </div>
          <div className="official">
            <span className="eyebrow">官方災損 · 農業部 {OFFICIAL_LOSS.date}</span>
            <span>
              雲林縣 <b>NT$ {toYi(OFFICIAL_LOSS.yunlinNtd)}</b> · 全國 NT$ {toYi(OFFICIAL_LOSS.taiwanNtd)}
            </span>
            <span className="cap">縣市層級統計，不代表個別田區損失</span>
          </div>
        </div>
        <div className="eyebrow" style={{ padding: '8px 20px 4px' }}>
          References 引用來源
        </div>
        {CITATIONS.map((c, k) => (
          <div key={c.title} className="src">
            <span className="mono">[{k + 1}]</span>
            <span>
              {c.url ? (
                <a className="link" href={c.url} target="_blank" rel="noreferrer">
                  {c.title}
                </a>
              ) : (
                c.title
              )}
              <br />
              <span className="cap" style={{ fontSize: 12 }}>
                {c.kind}
              </span>
            </span>
          </div>
        ))}
        <div style={{ flex: 1 }} />
        <div className="panel-foot">
          <button className="btn btn-primary btn-block" disabled aria-describedby="apply-soon">
            產生申請資料
          </button>
          <p id="apply-soon" className="soon">
            申請資料產生功能即將推出
          </p>
          <button className="btn btn-line btn-block" onClick={() => go('compare')}>
            ← 回到田區比對
          </button>
        </div>
      </aside>
    </>
  );
}
