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

  it('relief assistant asks the backend agent and shows the cited article', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            reply: '要帶身分證、印章、土地或耕作證明。',
            intent: 'REQUIRED_DOCUMENTS',
            conversation_state: 'APPLICATION_GUIDANCE_PROVIDED',
            sources: ['M0090019-ARTICLE-12'],
            result_cards: [],
          }),
          { status: 200 },
        ),
      ),
    );
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    openChampiMap();
    fireEvent.click(screen.getByRole('button', { name: '補助助手' }));
    const assist = screen.getByRole('region', { name: '補助助手' });
    fireEvent.click(within(assist).getByRole('button', { name: '申請需要哪些文件？' }));
    expect(await within(assist).findByText('要帶身分證、印章、土地或耕作證明。')).toBeInTheDocument();
    expect(within(assist).getByRole('link', { name: '農業天然災害救助辦法 第 12 條' })).toHaveAttribute('href', expect.stringContaining('flno=12'));
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/api/farmer/chat');
    expect(JSON.parse(init.body as string)).toMatchObject({ message: '申請需要哪些文件？', crop: '大蒜', optional_event_id: 'champi-2026-yunlin' });
    vi.unstubAllGlobals();
  });

  it('relief assistant asks for English and flags a reply that stayed in Chinese', async () => {
    const reply = (text: string, lang: 'zh' | 'en') =>
      new Response(JSON.stringify({ reply: text, intent: 'X', conversation_state: 'X', sources: [], result_cards: [], reply_language: lang }), { status: 200 });
    const fetchMock = vi.fn().mockResolvedValueOnce(reply('Bring your ID.', 'en')).mockResolvedValueOnce(reply('要帶身分證。', 'zh'));
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'EN' }));
    fireEvent.click(screen.getByRole('button', { name: 'Relief assistant' }));
    const assist = screen.getByRole('region', { name: 'Relief assistant' });
    fireEvent.click(within(assist).getByRole('button', { name: 'What documents do I need?' }));
    expect(await within(assist).findByText('Bring your ID.')).toBeInTheDocument();
    expect(JSON.parse((fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].body as string)).toMatchObject({ lang: 'en' });
    expect(within(assist).queryByText(/Shown in Chinese/)).not.toBeInTheDocument();
    fireEvent.click(within(assist).getByRole('button', { name: 'When is the deadline?' }));
    expect(await within(assist).findByText('要帶身分證。')).toBeInTheDocument();
    expect(within(assist).getByText(/Shown in Chinese/)).toBeInTheDocument();
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

  it('relief estimate is a ceiling from field area, with eligibility left to the authority', () => {
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: '補助助手' }));
    const assist = screen.getByRole('region', { name: '補助助手' });
    // The recorded demo uses 12.52471 ha before rounding the illustrative currency.
    expect(within(assist).getByText('NT$ 325,642')).toBeInTheDocument();
    expect(within(assist).getByText('待主管機關認定')).toBeInTheDocument();
  });

  it('rejects unknown or cross-case parcel IDs instead of falling back to the first parcel', () => {
    const noop = vi.fn();
    const { rerender } = render(
      <CompareScreen selectedId="4183" onSelect={noop} go={noop} eventId={null} onEvent={noop} farmer={null} onFarmer={noop} />,
    );
    expect(screen.getByRole('status')).toHaveTextContent('Taixi field not found');

    rerender(
      <AssistScreen selectedId="4183" onSelect={noop} go={noop} eventId={null} onEvent={noop} farmer={null} onFarmer={noop} />,
    );
    expect(screen.getByRole('status')).toHaveTextContent('Taixi field not found');
  });

  it('compare screen shows the team QA, including the failed cross-version NISAR check', () => {
    render(<App />);
    const compare = screen.getByRole('region', { name: '田區比對' });
    expect(within(compare).getByText('NISAR 前後兩期可直接比較強度')).toBeInTheDocument();
    expect(within(compare).getAllByText('未通過').length).toBeGreaterThan(0);
  });

  it('compare screen lists the open causes; none is presented as confirmed', () => {
    render(<App />);
    const compare = screen.getByRole('region', { name: '田區比對' });
    fireEvent.click(within(compare).getByRole('button', { name: /5 個可能原因/ }));
    expect(within(compare).getByRole('tab', { name: '可能原因' })).toHaveAttribute('aria-selected', 'true');
    const causes = within(compare).getByRole('tabpanel');
    expect(within(causes).getByText('颱風擾動作物或地表')).toBeInTheDocument();
    expect(within(causes).getAllByText('未檢驗')).toHaveLength(3);
    expect(within(causes).getAllByText('不確定')).toHaveLength(2);
    expect(within(compare).getByText('原因未知')).toBeInTheDocument();
  });

  it('the evidence graph opens only on request and links a cause to its checks', () => {
    render(<App />);
    const compare = screen.getByRole('region', { name: '田區比對' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    const opener = within(compare).getByRole('button', { name: '證據關係圖' });
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
