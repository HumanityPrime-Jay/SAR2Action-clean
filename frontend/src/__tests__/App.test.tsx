import React, { forwardRef, useImperativeHandle } from 'react';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from '../App';
import { CompareScreen } from '../screens/CompareScreen';
import { AssistScreen } from '../screens/AssistScreen';

// jsdom has no WebGL: stand in for the MapLibre globe, recording fly-to calls.
const flyToTaiwan = vi.fn(() => Promise.resolve());
vi.mock('../ui/Globe', () => ({
  default: forwardRef(function GlobeStub(_props: { borders: boolean }, ref) {
    useImperativeHandle(ref, () => ({ flyToTaiwan }));
    return <div data-testid="globe" />;
  }),
}));

class ResizeObserverStub {
  observe() {}
  disconnect() {}
}

/** Open the damage map and choose 中部 → 薔琵颱風. */
function openChampiMap() {
  fireEvent.click(screen.getByRole('button', { name: '受災地圖' }));
  const map = screen.getByRole('region', { name: '受災地圖' });
  fireEvent.change(within(map).getByRole('combobox', { name: /地區/ }), { target: { value: 'central' } });
  fireEvent.change(within(map).getByRole('combobox', { name: /災害事件/ }), { target: { value: 'champi-2026-yunlin' } });
  fireEvent.click(within(map).getByRole('checkbox', { name: /我是農民/ }));
  fireEvent.change(within(map).getByRole('combobox', { name: /這塊田種的作物/ }), { target: { value: 'garlic' } });
  fireEvent.click(within(map).getByRole('button', { name: /進入受災地圖/ }));
  return map;
}

const ARTICLE_12 = '農業天然災害現金救助除第十二條之二規定情形外，其作業程序及辦理期限如下：';

/** An authority-mode reply shaped like `POST /api/agent/chat`, trimmed to what the assistant reads. */
function authorityReply() {
  return {
    mode: 'AUTHORITY',
    field_id: 'YL-CAND-01',
    summary: '【科學觀測】YL-CAND-01 於警報前至警報期間之 Sentinel-1 VH 中位數變化為 +4.019 dB（狀態：OBSERVED）。',
    scientific_evidence: {
      crop_damage_confirmed: false,
      vh_change: { status: 'OBSERVED', median_change_db: 4.01907, pre_median_db: -29.77, warning_median_db: -25.76, post_median_db: -29.26 },
      sar_quality: { qa_passed: true, valid_pixels: 60, valid_coverage_ratio: 1 },
      spatial_reference_matching: { matched_fields: [{ field_id: 'YL-CAND-02' }], excluded_fields: [{ field_id: 'YL-CAND-05' }] },
    },
    legal_authority: {
      status: 'ANSWERED',
      applicable_law_version: { version: '2026-06-29' },
      citations: [
        {
          law_name: '農業天然災害救助辦法',
          article: '第12條',
          version: '2026-06-29',
          official_url: 'https://law.moj.gov.tw/LawClass/LawSingle.aspx?pcode=M0090019&flno=12',
          exact_source_text: ARTICLE_12,
          source_id: 'M0090019-ARTICLE-12',
        },
      ],
      rule_evaluations: {
        overall_status: 'INSUFFICIENT_FACTS_FOR_ELIGIBILITY_DETERMINATION',
        rule_evaluations: [
          { rule_id: '1_disaster_type', rule_name: 'Disaster Type', state: 'TRUE', citation_id: 'M0090019-ARTICLE-2', reason: '', missing_fields: [] },
          { rule_id: '10_crop_eligibility', rule_name: 'Crop', state: 'UNKNOWN', citation_id: 'M0090019-ARTICLE-6', reason: '', missing_fields: [] },
        ],
        missing_information: ['Relief type'],
      },
    },
    required_follow_up: {
      farmer: ['確認實際耕作作物種類與種植/養殖客觀證明文件'],
      authority: ['核對農業部或地方政府是否已正式公告雲林縣台西鄉為救助地區與品項'],
      field_survey: [],
    },
    limitations: ['DECISION_SUPPORT_ONLY'],
  };
}

/** fetch that answers the relief agent with `reply`; every other request (e.g. the relief catalog) fails. */
function agentFetch(reply: unknown) {
  return vi.fn((url: string) =>
    url.endsWith('/api/agent/chat') ? Promise.resolve(new Response(JSON.stringify(reply), { status: 200 })) : Promise.reject(new TypeError('offline')),
  );
}

/** The body sent to the relief agent. */
const agentBody = (fetchMock: ReturnType<typeof agentFetch>) =>
  JSON.parse((fetchMock.mock.calls.find(([url]) => url.endsWith('/api/agent/chat')) as unknown as [string, RequestInit])[1].body as string);

describe('App', () => {
  beforeEach(() => {
    window.location.hash = '';
    localStorage.clear();
    flyToTaiwan.mockClear();
    (globalThis as { ResizeObserver?: unknown }).ResizeObserver = ResizeObserverStub;
  });

  it('opens on the home screen with the four main tabs', () => {
    render(<App />);
    const nav = screen.getByRole('navigation', { name: '主選單' });
    for (const label of ['首頁', '受災地圖', '田區比對', '補助助手']) {
      expect(within(nav).getByRole('button', { name: label })).toBeInTheDocument();
    }
    expect(within(nav).getByRole('button', { name: '首頁' })).toHaveAttribute('aria-current', 'page');
  });

  it('home shows the globe and exactly three entry buttons', async () => {
    render(<App />);
    expect(await screen.findByTestId('globe')).toBeInTheDocument();
    const actions = screen.getByRole('navigation', { name: '開始使用' });
    expect(within(actions).getAllByRole('button')).toHaveLength(3);
  });

  it('an entry button flies to Taiwan, then opens its screen', async () => {
    render(<App />);
    await screen.findByTestId('globe');
    const actions = screen.getByRole('navigation', { name: '開始使用' });
    await act(async () => {
      fireEvent.click(within(actions).getByRole('button', { name: /田區雷達影像比對/ }));
    });
    expect(flyToTaiwan).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('region', { name: '田區比對' })).toHaveClass('active');
    expect(window.location.hash).toBe('#compare');
  });

  it('hidden screens are inert so keyboard focus cannot reach them', () => {
    render(<App />);
    expect(screen.getByRole('region', { name: '首頁' })).not.toHaveAttribute('inert');
    expect(document.querySelector('section[aria-label="受災地圖"]')).toHaveAttribute('inert');
    fireEvent.click(screen.getByRole('button', { name: '受災地圖' }));
    const map = screen.getByRole('region', { name: '受災地圖' });
    expect(map).not.toHaveAttribute('inert');
    expect(map).toHaveFocus();
  });

  it('damage map asks for region, then an event from that region', () => {
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: '受災地圖' }));
    const map = screen.getByRole('region', { name: '受災地圖' });
    const region = within(map).getByRole('combobox', { name: /地區/ });
    const event = within(map).getByRole('combobox', { name: /災害事件/ });
    expect(event).toBeDisabled();
    fireEvent.change(region, { target: { value: 'north' } });
    expect(event).toBeDisabled();
    expect(within(event).getByText('此地區尚無事件')).toBeInTheDocument();
    fireEvent.change(region, { target: { value: 'central' } });
    expect(event).toBeEnabled();
    expect(within(event).getByRole('option', { name: /薔琵颱風/ })).toBeInTheDocument();
    fireEvent.change(event, { target: { value: 'champi-2026-yunlin' } });
    // Not a farmer: no crop needed.
    expect(within(map).queryByRole('combobox', { name: /這塊田種的作物/ })).not.toBeInTheDocument();
    fireEvent.click(within(map).getByRole('button', { name: /進入受災地圖/ }));
    expect(within(map).getByRole('listbox', { name: '候選田區' })).toBeInTheDocument();
    expect(screen.getByRole('banner')).toHaveTextContent('薔琵颱風 · 雲林縣');
  });

  it('farmer card: optional, but once ticked the crop is required; the land parcel number reaches the estimate', () => {
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: '受災地圖' }));
    const map = screen.getByRole('region', { name: '受災地圖' });
    fireEvent.change(within(map).getByRole('combobox', { name: /地區/ }), { target: { value: 'central' } });
    fireEvent.change(within(map).getByRole('combobox', { name: /災害事件/ }), { target: { value: 'champi-2026-yunlin' } });
    fireEvent.click(within(map).getByRole('checkbox', { name: /我是農民/ }));
    fireEvent.click(within(map).getByRole('button', { name: /進入受災地圖/ }));
    expect(within(map).getByRole('alert')).toHaveTextContent('請選擇作物');
    expect(within(map).getByRole('combobox', { name: /這塊田種的作物/ })).toHaveAttribute('aria-invalid', 'true');

    fireEvent.change(within(map).getByRole('textbox', { name: /土地地籍/ }), { target: { value: '海口段 0123 地號' } });
    fireEvent.change(within(map).getByRole('combobox', { name: /這塊田種的作物/ }), { target: { value: 'garlic' } });
    fireEvent.click(within(map).getByRole('button', { name: /進入受災地圖/ }));
    expect(within(map).getByRole('listbox', { name: '候選田區' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '補助助手' }));
    const assist = screen.getByRole('region', { name: '補助助手' });
    expect(within(assist).getByText('海口段 0123 地號')).toBeInTheDocument();
    expect(within(assist).getByText('大蒜（農民登記）')).toBeInTheDocument();
  });

  it('switches the whole interface to English', () => {
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'EN' }));
    const nav = screen.getByRole('navigation', { name: 'Main menu' });
    expect(within(nav).getByRole('button', { name: 'Damage map' })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe('en');
    fireEvent.click(within(nav).getByRole('button', { name: 'Relief assistant' }));
    const assist = screen.getByRole('region', { name: 'Relief assistant' });
    expect(within(assist).getByText('Decided by the authority')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '中' }));
    expect(within(screen.getByRole('navigation', { name: '主選單' })).getByRole('button', { name: '受災地圖' })).toBeInTheDocument();
  });

  it('selecting a parcel on the map list updates the comparison screen', () => {
    render(<App />);
    const map = openChampiMap();
    fireEvent.click(within(map).getByRole('option', { name: /YL-CAND-03/ }));
    fireEvent.click(within(map).getByRole('button', { name: /查看前後比對/ }));
    const compare = screen.getByRole('region', { name: '田區比對' });
    expect(compare).toHaveClass('active');
    expect(within(compare).getByRole('heading', { name: /YL-CAND-03/ })).toBeInTheDocument();
  });

  it('loads the farmland layer only when it is switched on', async () => {
    const square = [[[120.18, 23.72], [120.19, 23.72], [120.19, 23.73], [120.18, 23.72]]];
    const fetchMock = vi.fn((url: string) =>
      url === '/studio/landuse_farmland_taixi.geojson'
        ? Promise.resolve(new Response(JSON.stringify({ features: [{ properties: { class: 'paddy' }, geometry: { type: 'Polygon', coordinates: square } }] })))
        : Promise.reject(new Error('offline')),
    );
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    const map = openChampiMap();
    expect(fetchMock).not.toHaveBeenCalledWith('/studio/landuse_farmland_taixi.geojson');
    fireEvent.click(within(map).getByRole('checkbox', { name: /農地類型/ }));
    expect(fetchMock).toHaveBeenCalledWith('/studio/landuse_farmland_taixi.geojson');
    expect(await within(map).findByText(/5 塊候選田都不在圖層內/)).toBeInTheDocument();
    expect(within(map).getByText('水田')).toBeInTheDocument();
    expect(map.querySelectorAll('.landuse path')).toHaveLength(1);
    vi.unstubAllGlobals();
  });

  it('shows the five real candidate fields and filters them by VH trend', () => {
    render(<App />);
    const map = openChampiMap();
    const list = within(map).getByRole('listbox', { name: '候選田區' });
    expect(within(list).getAllByRole('option')).toHaveLength(5);
    fireEvent.click(within(map).getByRole('button', { name: /VH 下降/ }));
    expect(within(list).getAllByRole('option')).toHaveLength(3);
  });

  it('send is disabled until the question has text', () => {
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: '補助助手' }));
    const assist = screen.getByRole('region', { name: '補助助手' });
    const send = within(assist).getByRole('button', { name: '送出' });
    expect(send).toBeDisabled();
    fireEvent.change(within(assist).getByRole('textbox', { name: '輸入問題' }), { target: { value: '門檻是多少？' } });
    expect(send).toBeEnabled();
  });

  it('relief assistant: a farmer gets plain words, the law stays verbatim, and the switch shows the authority view', async () => {
    const fetchMock = agentFetch(authorityReply());
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    openChampiMap();
    fireEvent.click(screen.getByRole('button', { name: '補助助手' }));
    const assist = screen.getByRole('region', { name: '補助助手' });
    const viewSwitch = within(assist).getByRole('switch', { name: '農政專業模式' });
    expect(viewSwitch).toHaveAttribute('aria-checked', 'false');

    fireEvent.click(within(assist).getByRole('button', { name: '申請需要哪些文件？' }));
    expect(await within(assist).findByText(/回波升高 \+4\.02 dB/)).toBeInTheDocument();
    expect(within(assist).getByText('你登記的作物是大蒜；能不能申請，要看政府有沒有公告這個品項。')).toBeInTheDocument();
    expect(within(assist).getByText('資料不足，還不能判斷是否符合救助資格。')).toBeInTheDocument();
    expect(within(assist).getByText('準備實際種植的作物種類和種植證明文件')).toBeInTheDocument();
    expect(within(assist).getByRole('link', { name: '《農業天然災害救助辦法》第12條' })).toHaveAttribute('href', expect.stringContaining('flno=12'));
    expect(within(assist).getByText(ARTICLE_12)).toBeInTheDocument();
    expect(within(assist).getByText(/公告救助地區的隔天起 10 個工作日內/)).toBeInTheDocument();
    expect(agentBody(fetchMock)).toMatchObject({ mode: 'AUTHORITY', message: '申請需要哪些文件？', field_id: 'YL-CAND-01', crop: '大蒜', lang: 'zh' });

    fireEvent.click(viewSwitch);
    expect(viewSwitch).toHaveAttribute('aria-checked', 'true');
    expect(within(assist).getByText(/【科學觀測】YL-CAND-01 警報前至警報期間，Sentinel-1 VH 中位數變化 \+4\.02 dB/)).toBeInTheDocument();
    expect(within(assist).getByText(/【法規檢核】依《農業天然災害救助辦法》2026-06-29 版/)).toHaveTextContent('資料不足，還不能判斷是否符合救助資格。');
    expect(within(assist).getByText(/符合 1 · 待確認 1/)).toBeInTheDocument();
    expect(within(assist).getByText(ARTICLE_12)).toBeInTheDocument();
    expect(within(assist).queryByText(/公告救助地區的隔天起 10 個工作日內/)).not.toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it('relief assistant says plainly when no article matches, instead of citing nothing', async () => {
    const reply = authorityReply();
    reply.legal_authority.status = 'INSUFFICIENT_LEGAL_BASIS';
    reply.legal_authority.citations = [];
    vi.stubGlobal('fetch', agentFetch(reply));
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: '補助助手' }));
    const assist = screen.getByRole('region', { name: '補助助手' });
    fireEvent.click(within(assist).getByRole('button', { name: '申請需要哪些文件？' }));
    expect(await within(assist).findByText('《農業天然災害救助辦法》裡找不到能完整對應這個問題的條文。')).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it('relief assistant in English: authority view by default, Chinese law text kept as the official wording', async () => {
    const fetchMock = agentFetch(authorityReply());
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'EN' }));
    fireEvent.click(screen.getByRole('button', { name: 'Relief assistant' }));
    const assist = screen.getByRole('region', { name: 'Relief assistant' });
    expect(within(assist).getByRole('switch', { name: 'Authority view' })).toHaveAttribute('aria-checked', 'true');
    fireEvent.click(within(assist).getByRole('button', { name: 'What documents do I need?' }));
    expect(await within(assist).findByText(/\[Observation\] YL-CAND-01/)).toBeInTheDocument();
    expect(within(assist).getByText(ARTICLE_12)).toBeInTheDocument();
    expect(within(assist).getByText('Official text in Chinese.')).toBeInTheDocument();
    expect(agentBody(fetchMock)).toMatchObject({ lang: 'en' });
    vi.unstubAllGlobals();
  });

  it('relief assistant says the agent is unavailable instead of inventing an answer', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))));
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: '補助助手' }));
    const assist = screen.getByRole('region', { name: '補助助手' });
    fireEvent.change(within(assist).getByRole('textbox', { name: '輸入問題' }), { target: { value: '門檻是多少？' } });
    fireEvent.click(within(assist).getByRole('button', { name: '送出' }));
    expect(await within(assist).findByRole('alert')).toHaveTextContent('AGENT 無法使用');
    vi.unstubAllGlobals();
  });

  it('the helpers greet on the home screen and can be hidden', () => {
    render(<App />);
    expect(screen.getByText('嗨！先選一場災害吧。')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '隱藏小幫手' }));
    expect(screen.queryByText('嗨！先選一場災害吧。')).not.toBeInTheDocument();
    expect(localStorage.getItem('sar2action.mascot')).toBe('hidden');
    fireEvent.click(screen.getByRole('button', { name: '顯示小幫手' }));
    expect(screen.getByRole('button', { name: /小幫手：農民和農會人員/ })).toBeInTheDocument();
  });

  it('the helpers apologise when the agent fails', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))));
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: '補助助手' }));
    const assist = screen.getByRole('region', { name: '補助助手' });
    fireEvent.click(within(assist).getByRole('button', { name: '申請需要哪些文件？' }));
    expect(await screen.findByText('抱歉，現在連不上。')).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it('rejects unknown or cross-case parcel IDs instead of falling back to the first parcel', () => {
    const noop = vi.fn();
    const { rerender } = render(
      <CompareScreen selectedId="4183" onSelect={noop} go={noop} eventId="champi-2026-yunlin" onEvent={noop} farmer={null} onFarmer={noop} />,
    );
    expect(screen.getByRole('status')).toHaveTextContent('Taixi field not found');

    rerender(
      <AssistScreen selectedId="4183" onSelect={noop} go={noop} eventId={null} onEvent={noop} farmer={null} onFarmer={noop} />,
    );
    expect(screen.getByRole('status')).toHaveTextContent('Taixi field not found');
  });

  it('the comparison waits for a disaster picked on the damage map', () => {
    render(<App />);
    const compare = screen.getByRole('region', { name: '田區比對' });
    expect(within(compare).getByRole('heading', { name: '先在受災地圖選一場災害' })).toBeInTheDocument();
    fireEvent.click(within(compare).getByRole('button', { name: /到受災地圖/ }));
    expect(screen.getByRole('region', { name: '受災地圖' })).toHaveClass('active');
  });

  it('compare screen notes what the VH series shows, each point numbered on the chart', () => {
    render(<App />);
    openChampiMap();
    const compare = screen.getByRole('region', { name: '田區比對' });
    const notes = within(within(compare).getByRole('region', { name: '看出什麼' })).getAllByRole('listitem');
    expect(notes).toHaveLength(3);
    expect(notes[0]).toHaveTextContent('警報期間回波升高 +4.02 dB');
    expect(notes[1]).toHaveTextContent('颱風後回到接近颱風前');
    expect(notes[2]).toHaveTextContent('去年同期變化');
  });

  it('compare screen shows the team QA, including the failed cross-version NISAR check', () => {
    render(<App />);
    openChampiMap();
    const compare = screen.getByRole('region', { name: '田區比對' });
    fireEvent.click(within(compare).getByRole('button', { name: /5 項檢驗：2 通過、3 未通過/ }));
    const graph = screen.getByRole('dialog', { name: '證據關係圖' });
    expect(within(graph).getByRole('button', { name: /NISAR 前後兩期可直接比較強度/ })).toHaveTextContent('未通過');
  });

  it('compare screen lists the open causes; none is presented as confirmed', () => {
    render(<App />);
    openChampiMap();
    const compare = screen.getByRole('region', { name: '田區比對' });
    const causes = within(compare).getByRole('region', { name: '可能原因' });
    expect(within(causes).getByText('不確定').nextElementSibling).toHaveTextContent('颱風擾動作物或地表、衛星處理版本不同');
    expect(within(causes).getByText('未檢驗').nextElementSibling).toHaveTextContent('收割、整地、土壤濕度變化');
    expect(within(compare).getByText('原因未知')).toBeInTheDocument();
  });

  it('the evidence graph opens only on request and links a cause to its checks', () => {
    render(<App />);
    openChampiMap();
    const compare = screen.getByRole('region', { name: '田區比對' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    const opener = within(compare).getByRole('button', { name: /5 項檢驗/ });
    opener.focus();
    fireEvent.click(opener);
    const dialog = screen.getByRole('dialog', { name: '證據關係圖' });
    expect(within(dialog).getByRole('button', { name: '關閉' })).toHaveFocus();

    fireEvent.click(within(dialog).getByRole('button', { name: '衛星處理版本不同' }));
    expect(within(dialog).getByRole('button', { name: /NISAR 前後兩期可直接比較強度/ })).not.toHaveClass('dim');
    expect(within(dialog).getByRole('button', { name: /官方損失可對應到個別田區/ })).toHaveClass('dim');
    expect(within(dialog).getByRole('button', { name: 'ASF 處理版本紀錄' })).not.toHaveClass('dim');
    expect(dialog).toHaveTextContent('NISAR 前後兩期版本不同');

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });
});
