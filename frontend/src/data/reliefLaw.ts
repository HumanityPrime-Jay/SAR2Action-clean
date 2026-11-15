/**
 * Wording for the authority-mode relief agent. The law text itself is never rewritten: these are
 * plain-language notes shown under the verbatim article, and labels for the agent's fixed rule ids
 * and checklists. Anything without an entry here is shown as the agent returned it.
 */
import type { RuleState } from '../api/authorityAgent';
import type { Text } from '../i18n';

/** One-line plain reading of each article of 農業天然災害救助辦法 (M0090019), keyed by article number. */
export const ARTICLE_PLAIN: Record<string, Text> = {
  '1': { zh: '這個辦法是依《農業發展條例》第 60 條第 2 項訂定的。', en: 'These regulations are made under Article 60(2) of the Agricultural Development Act.' },
  '2': {
    zh: '主管機關：中央是農業部，直轄市是市政府，縣市是縣市政府。',
    en: 'The competent authority is the Ministry of Agriculture nationally, and the city or county government locally.',
  },
  '3': { zh: '「救助」包括現金救助、補助和低利貸款。', en: '"Relief" means cash relief, subsidies or low-interest loans.' },
  '4': {
    zh: '颱風、焚風、龍捲風、豪雨、霪雨、冰雹、寒流、旱災或地震造成的災害才算；其他災害要由農業部專案認定。',
    en: 'Typhoons, foehn winds, tornadoes, heavy or prolonged rain, hail, cold waves, drought and earthquakes count; other disasters need a special ruling by the Ministry.',
  },
  '5': {
    zh: '救助對象是實際從事農林漁牧生產的個人。應登記而沒登記、用地或設施不合法、農產每筆土地申請面積不到 0.01 公頃等情形，不給現金救助。短期作物同一產季只救助一次。',
    en: 'Relief goes to individuals who actually farm. No cash relief if required registration is missing, land or facilities are unlawful, or a farm plot claim is under 0.01 ha. Short-term crops get relief once per season.',
  },
  '6': {
    zh: '縣市政府要在災後 7 天內，把救助地區和品項報請農業部公告（災情晚顯現的可延到 3 個月，依作物特性可到 6 個月）。有公告，才辦現金救助和低利貸款。',
    en: 'Within 7 days of the disaster the county reports the relief areas and items to the Ministry for announcement (up to 3 months for late-showing damage, 6 for some crops). Cash relief and loans follow that announcement.',
  },
  '6-2': {
    zh: '經公告為連續災害時，已申請過的不用重複申請，現金救助以一次為限（短期作物已復耕、屬不同產季的除外）。',
    en: 'For announced consecutive disasters, an earlier application covers later ones, and cash relief is paid once (unless a short-term crop was replanted in a new season).',
  },
  '6-3': {
    zh: '一年一收的長期作物，同一塊地同一作物前一年或今年同產季已獲救助，又在防汛期因颱風或豪雨嚴重受損並經公告，可以再領一次額外現金救助。',
    en: 'A once-a-year perennial crop already relieved last year or this season on the same land can get one extra cash payment if a typhoon or heavy rain badly damages it again in flood season and this is announced.',
  },
  '6-4': {
    zh: '一年一收的長期作物因同一場嚴重災害、損害延續到下一年或下一產季時，農業部可以公告辦理救助。',
    en: 'If one severe disaster keeps damaging a once-a-year perennial crop into the next year or season, the Ministry may announce relief.',
  },
  '9': {
    zh: '規定損失金額怎麼估算。例如短期作物還能復耕或轉作且可收穫的，以生產總費用的 50% 計算；不能復耕或轉作的，以生產總費用扣除採收工資計算。',
    en: 'Sets how losses are valued. For example, a short-term crop that can still be replanted and harvested is valued at 50% of total production cost; otherwise at total production cost minus harvest labour.',
  },
  '12': {
    zh: '公告救助地區的隔天起 10 個工作日內，要填申請表向鄉鎮市區公所申請，逾期不受理（災情嚴重時可公告延長）。公所在 30 天內完成勘查；有種植客觀證明文件的，符合條件時可以免勘查。',
    en: 'Apply to the township office within 10 working days after the relief area is announced; late applications are refused unless an extension is announced. The office inspects within 30 days; documented planting can skip inspection when conditions are met.',
  },
  '12-1': {
    zh: '誤導勘查地點、申報的地沒有實際耕作或項目不符、損失率不到 20%（部分情形例外）的，不予救助；已經撥款的要返還。',
    en: 'No relief, and repayment of any paid relief, if inspectors are misled about the site, the land is not actually farmed or the item differs, or the loss rate is below 20% (with some exceptions).',
  },
  '12-2': {
    zh: '林業保育署出租造林地的救助，要在公告隔天起 10 個工作日內向所屬工作站申請。',
    en: 'For leased Forestry Agency land, apply to the local work station within 10 working days after the announcement.',
  },
  '13': {
    zh: '縣市政府和鄉鎮市區公所要指派專人或成立專案小組辦理救助。',
    en: 'County governments and township offices must assign staff or a task force to handle relief.',
  },
  '14': {
    zh: '投保經農業部公告的農業天然災害保險或農業收入保險，農業部可以補助保費。',
    en: 'The Ministry may subsidise premiums for approved agricultural disaster or income insurance.',
  },
  '18': {
    zh: '低利貸款由農會、漁會信用部等機構承辦，利息差額由救助基金補貼。',
    en: 'Low-interest loans are handled by farmers’ and fishers’ association credit departments and similar lenders; the relief fund covers the interest difference.',
  },
  '19': {
    zh: '要申請低利貸款，先在公告隔天起 10 個工作日內向公所申請受災證明書，核發後 30 個工作日內向貸款機構申請。',
    en: 'For a loan, request a disaster certificate from the township office within 10 working days after the announcement, then apply to the lender within 30 working days of its issue.',
  },
  '20': {
    zh: '低利貸款利率依農業部規定，會隨規定調整。',
    en: 'Loan interest follows the Ministry’s rate and changes with it.',
  },
  '26-1': {
    zh: '現金救助由縣市政府作成決定（林業保育署出租造林地由農業部決定）。',
    en: 'Cash relief decisions are made by the county or city government (by the Ministry for leased Forestry Agency land).',
  },
};

/** Article number from a citation's "第12-1條" label. */
export const articleNo = (article: string) => /第\s*([\d-]+)\s*條/.exec(article)?.[1] ?? '';

/** A repealed article: its whole text is "（刪除）". */
export const isRepealed = (text: string) => text.trim() === '（刪除）';

export const RULE_LABEL: Record<string, Text> = {
  '1_disaster_type': { zh: '災害種類', en: 'Disaster type' },
  '2_relief_type': { zh: '救助種類', en: 'Relief type' },
  '3_applicant_category': { zh: '申請人資格', en: 'Applicant eligibility' },
  '4_declared_relief_area': { zh: '公告救助地區', en: 'Announced relief area' },
  '5_declared_relief_item': { zh: '公告救助品項', en: 'Announced relief item' },
  '6_application_deadline': { zh: '申請期限', en: 'Application deadline' },
  '7_land_area_conditions': { zh: '土地面積', en: 'Land area' },
  '8_loss_rate_conditions': { zh: '損失率', en: 'Loss rate' },
  '9_exceptions': { zh: '例外情形', en: 'Exceptions' },
  '10_crop_eligibility': { zh: '作物是否在救助品項', en: 'Crop eligibility' },
  '11_required_evidence': { zh: '種植或受損證明', en: 'Planting or damage proof' },
  '12_applicable_version': { zh: '適用的法規版本', en: 'Applicable law version' },
};

export const RULE_STATE: Record<RuleState, Text> = {
  TRUE: { zh: '符合', en: 'Met' },
  FALSE: { zh: '不符合', en: 'Not met' },
  UNKNOWN: { zh: '待確認', en: 'To confirm' },
  NOT_APPLICABLE: { zh: '不適用', en: 'N/A' },
};

/** The legal check's overall result; the agent never decides eligibility itself. */
export const OVERALL: Record<string, Text> = {
  INSUFFICIENT_FACTS_FOR_ELIGIBILITY_DETERMINATION: {
    zh: '資料不足，還不能判斷是否符合救助資格。',
    en: 'Not enough information yet to tell whether relief applies.',
  },
  NOT_ELIGIBLE_BASED_ON_GIVEN_FACTS: {
    zh: '依目前資料，有條件不符合救助規定。',
    en: 'On the information given, a relief condition is not met.',
  },
  PRECHECK_CONDITIONS_SATISFIED_DECISION_SUPPORT_ONLY: {
    zh: '依目前資料，預先檢核的條件都符合；仍需公所與主管機關核定。',
    en: 'On the information given, the pre-check conditions are met; the township office and authority still decide.',
  },
};

/** Why the legal search returned no article; ANSWERED needs no note. */
export const LEGAL_STATUS: Record<string, Text> = {
  INSUFFICIENT_LEGAL_BASIS: {
    zh: '《農業天然災害救助辦法》裡找不到能完整對應這個問題的條文。',
    en: 'No article of the Agricultural Natural Disaster Relief Regulations fully matches this question.',
  },
  OUT_OF_SCOPE: { zh: '這個問題不在救助辦法的範圍內。', en: 'This question is outside the relief regulations.' },
  VERSION_NOT_VERIFIED: { zh: '無法確認這次災害日期適用的法規版本。', en: 'The law version for this disaster date could not be verified.' },
};

export const DECIDED_BY: Text = {
  zh: '最後由鄉鎮市區公所和主管機關核定，AI 不會自行核定。',
  en: 'The township office and the authority make the final decision; the AI does not.',
};

/** Missing facts named by the legal check. */
export const MISSING: Record<string, Text> = {
  'Relief type': { zh: '要申請哪一種救助（現金救助或低利貸款）', en: 'Which relief (cash or low-interest loan)' },
  'Applicant farmer identity': { zh: '申請人的農民身分', en: 'Applicant’s farmer identity' },
  'Actual agricultural production proof': { zh: '實際從事生產的證明', en: 'Proof of actual farming' },
  'Official relief area announcement': { zh: '救助地區的正式公告', en: 'Official relief area announcement' },
  'Official relief item announcement': { zh: '救助品項的正式公告', en: 'Official relief item announcement' },
  'Official announcement date': { zh: '公告日期', en: 'Announcement date' },
  'Official working-day calendar / extension notice': { zh: '工作日計算或延長受理的公告', en: 'Working-day calendar or extension notice' },
  'Ground-verified crop loss rate (%)': { zh: '現場勘查確認的損失率（%）', en: 'Field-verified loss rate (%)' },
  'Applicable exception status': { zh: '是否適用例外規定', en: 'Whether an exception applies' },
  'Crop / product identity': { zh: '作物種類', en: 'Crop type' },
  'Verified appendix crop category': { zh: '作物在附表中的類別（需人工核對）', en: 'Crop category in the appendix (needs manual review)' },
  'Planting/cultivation proof or field inspection': { zh: '種植證明或現場勘查', en: 'Planting proof or field inspection' },
};

/** Fixed follow-up items from the agent. */
export const FOLLOW_UP: Record<string, Text> = {
  '確認實際耕作作物種類與種植/養殖客觀證明文件': { zh: '準備實際種植的作物種類和種植證明文件', en: 'Prepare the crop type and documents proving you planted it' },
  '確認申請人農民資格及實際受損面積/情況（如現勘照片）': {
    zh: '準備農民身分證明，以及受損面積和受損照片',
    en: 'Prepare proof of farmer status, the damaged area and photos of the damage',
  },
  核對農業部或地方政府是否已正式公告雲林縣台西鄉為救助地區與品項: {
    zh: '核對農業部或縣府是否已公告台西鄉為救助地區與品項',
    en: 'Check whether the Ministry or county has announced Taixi as a relief area and item',
  },
  '辦理鄉（鎮、市、區）公所現場勘查或天氣參數/免勘查條件核對': {
    zh: '公所辦理現場勘查，或核對天氣參數、免勘查條件',
    en: 'Township office inspection, or check of weather parameters and inspection-exemption conditions',
  },
  'Geolocated field damage survey or cloud-free optical validation': {
    zh: '有定位的田間受損調查，或無雲光學影像驗證',
    en: 'Geolocated field damage survey or cloud-free optical validation',
  },
  'In-situ or high-resolution rainfall and soil moisture time series': {
    zh: '現地或高解析度的雨量與土壤濕度時序',
    en: 'In-situ or high-resolution rainfall and soil moisture time series',
  },
};

/** A label from one of the tables above, or the agent's own text when there is none. */
export const label = (table: Record<string, Text>, key: string): Text => table[key] ?? { zh: key, en: key };
