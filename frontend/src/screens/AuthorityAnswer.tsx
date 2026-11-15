import React, { useState } from 'react';
import type { AuthorityReply, LegalCitation } from '../api/authorityAgent';
import { type FarmerInfo, cropName } from '../data/farmer';
import { ARTICLE_PLAIN, DECIDED_BY, FOLLOW_UP, LEGAL_STATUS, MISSING, OVERALL, RULE_LABEL, RULE_STATE, articleNo, isRepealed, label } from '../data/reliefLaw';
import { formatDb } from '../demo/fields';
import { type Text, useLang, useT } from '../i18n';

export type AnswerView = 'farmer' | 'authority';

/** VH changes smaller than this, in dB, are read as "no clear change" (same threshold as the field comparison). */
const CLEAR_DB = 2;

/** The relief agent's answer: the authority view as returned, or the same facts in plain words for a farmer. */
export function AuthorityAnswer({ reply, view, farmer }: { reply: AuthorityReply; view: AnswerView; farmer: FarmerInfo | null }) {
  return view === 'farmer' ? <FarmerView reply={reply} farmer={farmer} /> : <AuthorityView reply={reply} />;
}

function FarmerView({ reply, farmer }: { reply: AuthorityReply; farmer: FarmerInfo | null }) {
  const t = useT();
  const { lang } = useLang();
  const vh = reply.scientific_evidence.vh_change.median_change_db;
  const rules = reply.legal_authority.rule_evaluations;
  const cropRule = rules.rule_evaluations.find((r) => r.rule_id === '10_crop_eligibility');
  const crop = farmer ? cropName(farmer, lang) : null;

  const radar: Text =
    vh == null
      ? { zh: '這塊田的雷達資料還不夠，看不出變化。', en: 'There is not enough radar data on this field to see a change.' }
      : Math.abs(vh) >= CLEAR_DB
        ? {
            zh: `衛星雷達在颱風警報期間，看到這塊田的回波${vh > 0 ? '升高' : '降低'} ${formatDb(vh)}，表示地面有變化。但這不等於作物受損，也還不能確定是颱風造成的。`,
            en: `During the typhoon warning, satellite radar saw this field's return ${vh > 0 ? 'rise' : 'fall'} by ${formatDb(vh)}, so the ground changed. That is not the same as crop damage, and the typhoon is not confirmed as the cause.`,
          }
        : {
            zh: `衛星雷達在颱風警報期間，沒有看到這塊田有明顯變化（${formatDb(vh)}）。`,
            en: `During the typhoon warning, satellite radar saw no clear change on this field (${formatDb(vh)}).`,
          };
  const cropLine: Text = crop
    ? cropRule?.state === 'TRUE'
      ? { zh: `你登記的作物是${crop}，在公告的救助品項內。`, en: `Your crop, ${crop}, is on the announced relief list.` }
      : { zh: `你登記的作物是${crop}；能不能申請，要看政府有沒有公告這個品項。`, en: `Your crop is ${crop}; whether it qualifies depends on the government announcing it as a relief item.` }
    : { zh: '還不知道你種什麼作物；作物會影響能不能申請。', en: 'Your crop is not known yet; it affects whether you can apply.' };

  return (
    <div className="answer">
      <p>{t(radar)}</p>
      <p>{t(cropLine)}</p>
      <p>
        <b>{t(label(OVERALL, rules.overall_status))}</b> {t(DECIDED_BY)}
      </p>
      {reply.required_follow_up.farmer.length > 0 && (
        <section>
          <h3 className="answer-h">{t('你要準備的', 'What to prepare')}</h3>
          <ul>
            {reply.required_follow_up.farmer.map((x) => (
              <li key={x}>{t(label(FOLLOW_UP, x))}</li>
            ))}
          </ul>
        </section>
      )}
      <LawBlock citations={reply.legal_authority.citations} status={reply.legal_authority.status} plain />
    </div>
  );
}

function AuthorityView({ reply }: { reply: AuthorityReply }) {
  const t = useT();
  const sci = reply.scientific_evidence;
  const vh = sci.vh_change.median_change_db;
  const rules = reply.legal_authority.rule_evaluations;
  const met = rules.rule_evaluations.filter((r) => r.state === 'TRUE').length;
  const failed = rules.rule_evaluations.filter((r) => r.state === 'FALSE').length;
  const open = rules.rule_evaluations.length - met - failed;
  const vhText = vh == null ? t('無資料', 'n/a') : formatDb(vh);
  const version = reply.legal_authority.applicable_law_version.version;

  return (
    <div className="answer">
      <p>
        {t(
          `【科學觀測】${reply.field_id} 警報前至警報期間，Sentinel-1 VH 中位數變化 ${vhText}${sci.vh_change.status === 'OBSERVED' ? '（實際觀測）' : ''}。缺乏地塊級農損真值，雷達訊號變化不等於農損率。`,
          `[Observation] ${reply.field_id}: Sentinel-1 VH median change from pre-warning to the warning window, ${vhText}${sci.vh_change.status === 'OBSERVED' ? ' (observed)' : ''}. There is no parcel-level damage truth, so the radar change is not a loss rate.`,
        )}
      </p>
      <p>
        {t(`【法規檢核】依《農業天然災害救助辦法》${version ?? '未驗證'} 版：`, `[Legal check] Relief Regulations, ${version ?? 'unverified'} version: `)}
        {t(label(OVERALL, rules.overall_status))} {t('僅供決策支援。', 'Decision support only.')}
      </p>
      <dl className="answer-stats">
        <div>
          <dt>{t('VH 警報前→警報中', 'VH pre → warning')}</dt>
          <dd>{vhText}</dd>
        </div>
        <div>
          <dt>{t('影像品質', 'Image QA')}</dt>
          <dd>
            {sci.sar_quality.qa_passed ? t('通過', 'Pass') : t('未通過', 'Fail')} · {sci.sar_quality.valid_pixels} px
          </dd>
        </div>
        <div>
          <dt>{t('鄰近田比對', 'Reference fields')}</dt>
          <dd>
            {sci.spatial_reference_matching.matched_fields.length}
            {t(' 塊', '')}
            {sci.spatial_reference_matching.excluded_fields.length > 0 && t(`（排除 ${sci.spatial_reference_matching.excluded_fields.length}）`, ` (${sci.spatial_reference_matching.excluded_fields.length} excluded)`)}
          </dd>
        </div>
      </dl>
      <details className="answer-more">
        <summary>
          {t('法規檢核', 'Legal check')}：{t(`符合 ${met} · 待確認 ${open}`, `${met} met · ${open} to confirm`)}
          {failed > 0 && t(` · 不符合 ${failed}`, ` · ${failed} not met`)}
        </summary>
        <ul className="rule-list">
          {rules.rule_evaluations.map((r) => (
            <li key={r.rule_id}>
              <span className={`qa-mark ${r.state === 'TRUE' ? 'pass' : r.state === 'FALSE' ? 'fail' : 'open'}`}>{t(RULE_STATE[r.state] ?? { zh: r.state, en: r.state })}</span>
              {t(label(RULE_LABEL, r.rule_id))}
            </li>
          ))}
        </ul>
        {rules.missing_information.length > 0 && (
          <>
            <h3 className="answer-h">{t('缺少的資料', 'Missing information')}</h3>
            <ul>
              {rules.missing_information.map((m) => (
                <li key={m}>{t(label(MISSING, m))}</li>
              ))}
            </ul>
          </>
        )}
      </details>
      <section>
        <h3 className="answer-h">{t('公所與農政待辦', 'For the township office and authority')}</h3>
        <ul>
          {[...reply.required_follow_up.authority, ...reply.required_follow_up.field_survey].map((x) => (
            <li key={x}>{t(label(FOLLOW_UP, x))}</li>
          ))}
        </ul>
      </section>
      <LawBlock citations={reply.legal_authority.citations} status={reply.legal_authority.status} />
      {reply.limitations.length > 0 && (
        <details className="answer-more">
          <summary>{t(`限制（${reply.limitations.length}）`, `Limitations (${reply.limitations.length})`)}</summary>
          <ul>
            {reply.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

/** Articles shown at once, in the agent's ranking; the rest open on request. */
const SHOWN_CITATIONS = 2;

/** The cited articles, verbatim and linked, in both views; `plain` adds a plain-language line under each. */
function LawBlock({ citations, status, plain = false }: { citations: LegalCitation[]; status: string; plain?: boolean }) {
  const t = useT();
  return (
    <section className="law">
      <h3 className="answer-h">{t('法規依據', 'Legal basis')}</h3>
      {!citations.length && <p>{t(LEGAL_STATUS[status] ?? { zh: '這段回答沒有引用條文。', en: 'No article cited for this reply.' })}</p>}
      {citations.slice(0, SHOWN_CITATIONS).map((c) => (
        <Citation key={c.source_id} c={c} plain={plain} />
      ))}
      {citations.length > SHOWN_CITATIONS && (
        <details className="answer-more">
          <summary>{t(`其他相關條文（${citations.length - SHOWN_CITATIONS}）`, `More related articles (${citations.length - SHOWN_CITATIONS})`)}</summary>
          <div className="law">
            {citations.slice(SHOWN_CITATIONS).map((c) => (
              <Citation key={c.source_id} c={c} plain={plain} />
            ))}
          </div>
        </details>
      )}
    </section>
  );
}

function Citation({ c, plain }: { c: LegalCitation; plain: boolean }) {
  const t = useT();
  const [full, setFull] = useState(false);
  const no = articleNo(c.article);
  const repealed = isRepealed(c.exact_source_text);
  const note = repealed ? { zh: '這條已經刪除，沒有效力。', en: 'This article has been repealed and no longer applies.' } : ARTICLE_PLAIN[no];
  const long = c.exact_source_text.length > 120;
  return (
    <article className="cite">
      <a href={c.official_url} target="_blank" rel="noreferrer">
        《{c.law_name}》{c.article}
      </a>
      <span className="cap mono"> {c.version}</span>
      <blockquote lang="zh-Hant">
        <span className={long && !full ? 'clamp' : undefined}>{c.exact_source_text}</span>
      </blockquote>
      <div className="cite-foot">
        {long && (
          <button className="link" aria-expanded={full} onClick={() => setFull(!full)}>
            {full ? t('收合', 'Collapse') : t('展開全文', 'Show full text')}
          </button>
        )}
        {t('', 'Official text in Chinese.')}
      </div>
      {(plain || repealed) && note && (
        <p className="cite-plain">
          <span className="tag">{t('白話', 'In plain words')}</span>
          {t(note)}
        </p>
      )}
    </article>
  );
}
