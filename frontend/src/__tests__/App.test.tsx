import React, { forwardRef, useImperativeHandle } from 'react';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from '../App';

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
  fireEvent.click(within(map).getByRole('button', { name: /進入受災地圖/ }));
  return map;
}

describe('App', () => {
  beforeEach(() => {
    window.location.hash = '';
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
      fireEvent.click(within(actions).getByRole('button', { name: /田區比對/ }));
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
    expect(within(map).getByText('這個地區目前還沒有處理好的災害事件。')).toBeInTheDocument();
    fireEvent.change(region, { target: { value: 'central' } });
    expect(event).toBeEnabled();
    expect(within(event).getByRole('option', { name: /薔琵颱風/ })).toBeInTheDocument();
    fireEvent.change(event, { target: { value: 'champi-2026-yunlin' } });
    fireEvent.click(within(map).getByRole('button', { name: /進入受災地圖/ }));
    expect(within(map).getByRole('listbox', { name: '候選田區' })).toBeInTheDocument();
    expect(screen.getByRole('banner')).toHaveTextContent('薔琵颱風 · 雲林縣');
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

  it('relief estimate is a ceiling from field area, with eligibility left to the authority', () => {
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: '補助助手' }));
    const assist = screen.getByRole('region', { name: '補助助手' });
    // YL-CAND-01 is 12.5 ha in the official farmland map.
    expect(within(assist).getByText('NT$ 325,000')).toBeInTheDocument();
    expect(within(assist).getByText('待主管機關認定')).toBeInTheDocument();
  });

  it('compare screen shows the team QA, including the failed cross-version NISAR check', () => {
    render(<App />);
    const compare = screen.getByRole('region', { name: '田區比對' });
    expect(within(compare).getByText('NISAR 前後兩期可直接比較強度')).toBeInTheDocument();
    expect(within(compare).getAllByText('未通過').length).toBeGreaterThan(0);
  });
});
