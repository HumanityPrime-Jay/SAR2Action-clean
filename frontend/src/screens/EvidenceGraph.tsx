import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { CAUSES, EVIDENCE_SOURCES, QA_TESTS, TEST_SOURCES } from '../data/champi';
import { useT } from '../i18n';

type Line = { key: string; from: string; to: string; d: string };

/** Graph edges: source → test (the test cites it) and test → cause (the test bears on it). */
const EDGES: [string, string][] = [
  ...QA_TESTS.flatMap((q) => (TEST_SOURCES[q.id] ?? []).map((s): [string, string] => [`s:${s}`, `t:${q.id}`])),
  ...CAUSES.flatMap((c) => c.testIds.map((id): [string, string] => [`t:${id}`, `c:${c.id}`])),
];

/** Everything linked to a node, following edges left and right (cause → its tests → their sources). */
function linked(node: string): Set<string> {
  const lit = new Set([node]);
  const walk = (id: string, dir: 0 | 1) => {
    for (const edge of EDGES) {
      if (edge[dir] === id && !lit.has(edge[1 - dir])) {
        lit.add(edge[1 - dir]);
        walk(edge[1 - dir], dir);
      }
    }
  };
  walk(node, 0);
  walk(node, 1);
  return lit;
}

/** Which data each recorded test used, and which possible cause it speaks to. Opens on request only. */
export function EvidenceGraph({ onClose }: { onClose: () => void }) {
  const t = useT();
  const [picked, setPicked] = useState<string | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const grid = useRef<HTMLDivElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const lit = useMemo(() => (picked ? linked(picked) : null), [picked]);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  // Focus the close button while open, Escape closes, and focus returns to the opener.
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    close.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onCloseRef.current();
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      opener?.focus();
    };
  }, []);

  // Draw the edges between the node buttons once they are laid out.
  useLayoutEffect(() => {
    const measure = () => {
      const box = grid.current?.getBoundingClientRect();
      if (!box) return;
      const rect = (id: string) => grid.current!.querySelector(`[data-node="${CSS.escape(id)}"]`)?.getBoundingClientRect();
      setLines(
        EDGES.flatMap(([from, to]) => {
          const a = rect(from);
          const b = rect(to);
          if (!a || !b) return [];
          const x1 = a.right - box.left;
          const y1 = a.top + a.height / 2 - box.top;
          const x2 = b.left - box.left;
          const y2 = b.top + b.height / 2 - box.top;
          const mid = (x1 + x2) / 2;
          return [{ key: `${from}>${to}`, from, to, d: `M${x1} ${y1}C${mid} ${y1} ${mid} ${y2} ${x2} ${y2}` }];
        }),
      );
    };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, []);

  const node = (id: string, children: React.ReactNode, extra = '') => (
    <button
      key={id}
      type="button"
      data-node={id}
      className={`graph-node${extra}${lit && !lit.has(id) ? ' dim' : ''}`}
      aria-pressed={picked === id}
      onClick={() => setPicked(picked === id ? null : id)}
    >
      {children}
    </button>
  );

  const detail = picked && describe(picked);

  return (
    <div className="graph-backdrop" onClick={onClose}>
      <div className="graph-dialog" role="dialog" aria-modal="true" aria-labelledby="graph-title" onClick={(e) => e.stopPropagation()}>
        <div className="graph-head">
          <h2 id="graph-title" className="h3">
            {t('證據關係圖', 'Evidence graph')}
          </h2>
          <button ref={close} className="graph-close" aria-label={t('關閉', 'Close')} onClick={onClose}>
            ×
          </button>
        </div>
        <div className="graph-scroll">
          <div className={`graph${lit ? ' has-pick' : ''}`} ref={grid}>
            <svg className="graph-lines" aria-hidden="true">
              {lines.map((l) => (
                <path key={l.key} d={l.d} className={lit ? (lit.has(l.from) && lit.has(l.to) ? 'lit' : 'dim') : undefined} />
              ))}
            </svg>
            <div className="graph-col">
              <div className="eyebrow">{t('資料來源', 'Data')}</div>
              {EVIDENCE_SOURCES.map((s) => node(`s:${s.id}`, t(s.label)))}
            </div>
            <div className="graph-col">
              <div className="eyebrow">{t('檢驗', 'Checks')}</div>
              {QA_TESTS.map((q) =>
                node(
                  `t:${q.id}`,
                  <>
                    <span className={`qa-mark ${q.pass ? 'pass' : 'fail'}`}>{q.pass ? t('通過', 'Pass') : t('未通過', 'Fail')}</span>
                    {t(q.label)}
                  </>,
                ),
              )}
            </div>
            <div className="graph-col">
              <div className="eyebrow">{t('可能原因', 'Possible causes')}</div>
              {CAUSES.map((c) => node(`c:${c.id}`, t(c.label), c.tested ? '' : ' untested'))}
            </div>
          </div>
        </div>
        <p className="graph-detail" aria-live="polite">
          {detail ? (
            <>
              <b>{t(detail.title)}</b> {t(detail.text)}
            </>
          ) : (
            t('點一個方塊，看它連到哪些資料。', 'Click a box to see what it connects to.')
          )}
        </p>
      </div>
    </div>
  );

  function describe(id: string) {
    const [kind, key] = [id.slice(0, 1), id.slice(2)];
    if (kind === 't') {
      const q = QA_TESTS.find((x) => x.id === key)!;
      return { title: q.label, text: q.result };
    }
    if (kind === 'c') {
      const c = CAUSES.find((x) => x.id === key)!;
      return { title: c.label, text: c.check };
    }
    const s = EVIDENCE_SOURCES.find((x) => x.id === key)!;
    return { title: s.label, text: { zh: `證據編號 ${s.id}`, en: `Evidence ID ${s.id}` } };
  }
}
