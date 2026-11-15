"""Draws architecture.svg (中文) and architecture.en.svg from one layout, in the app's visual style.

Usage: python docs/readme-assets/architecture.py
Every text line carries data-max, the right edge it must stay inside, so a browser check can catch overflow.
"""
from html import escape
from pathlib import Path

W, H = 1280, 728
COL_X, COL_W, TOP = (40, 350, 660, 970), 270, 124
INK, TEXT2, TEXT3, BLUE, RED = '#0A0A0A', '#3D4350', '#5F6672', '#0B3D91', '#D7322A'

# 24 x 24 line icons; the four screen icons are the app's own (frontend/src/ui/shared.tsx).
ICONS = {
    'satellite': '<path d="M7 10 10 7l7 7-3 3z"/><path d="M3 6l3-3 3 3-3 3zM15 18l3-3 3 3-3 3zM14 21a7 7 0 0 0 7-7"/>',
    'radar': '<path d="M12 13v8M8 21h8"/><path d="M8.5 9.5a5 5 0 0 1 7 0M5.5 6.5a9 9 0 0 1 13 0"/><circle cx="12" cy="13" r="1.3"/>',
    'parcels': '<rect x="3.5" y="3.5" width="17" height="17"/><path d="M3.5 10.5h9v-7M12.5 10.5v10M12.5 15h8"/>',
    'report': '<path d="M6 3h9l4 4v14H6z"/><path d="M15 3v4h4M9 12h7M9 16h7"/>',
    'law': '<path d="M12 4v16M7 20h10M5 7h14"/><path d="M5 7l-2.5 6h5zM19 7l-2.5 6h5z"/>',
    'border': '<path d="M4 7l6-3 10 4-2 10-9 2-5-6z" stroke-dasharray="3 2.5"/>',
    'chart': '<path d="M3.5 19.5h17"/><path d="M5 15l4-5 4 3 6-7"/>',
    'calendar': '<rect x="3.5" y="5" width="17" height="15"/><path d="M3.5 9.5h17M8 3v4M16 3v4M9 15h6"/>',
    'area': '<rect x="4" y="4" width="16" height="16" stroke-dasharray="3 2.2"/><path d="M8 16 16 8M8 11l3-3M13 16l3-3"/>',
    'coin': '<circle cx="12" cy="12" r="8.5"/><path d="M14.6 9.4c-.6-.8-1.5-1.2-2.6-1.2-1.5 0-2.6.8-2.6 1.9s1.1 1.6 2.6 1.9 2.6.8 2.6 1.9-1.1 1.9-2.6 1.9c-1.1 0-2-.4-2.6-1.2M12 6.5v11"/>',
    'calculator': '<rect x="5" y="3" width="14" height="18"/><path d="M8 7h8M8 12h1M11.5 12h1M15 12h1M8 16h1M11.5 16h1M15 16h1"/>',
    'book': '<path d="M4 5.5C6 4 9 4 12 6c3-2 6-2 8-.5V19c-2-1.5-5-1.5-8 .5-3-2-6-2-8-.5z"/><path d="M12 6v13.5"/>',
    'sparkle': '<path d="M12 3c.6 4.5 4.5 8.4 9 9-4.5.6-8.4 4.5-9 9-.6-4.5-4.5-8.4-9-9 4.5-.6 8.4-4.5 9-9z"/>',
    'user': '<circle cx="12" cy="8" r="4"/><path d="M4.5 20.5c1-4 4-6 7.5-6s6.5 2 7.5 6"/>',
    'cloud': '<path d="M7 18.5h10.5a4 4 0 0 0 .5-8 6 6 0 0 0-11.5 1.5A3.3 3.3 0 0 0 7 18.5z"/>',
    'formula': '<path d="M14 4c-2 0-3 1-3.4 3L8 18c-.4 2-1.4 3-3.4 3M6.5 10H14"/><path d="M15 13l5 6M20 13l-5 6"/>',
    'farmer': '<path d="M3 12.5h18M6 12.5c0-4 2.5-7 6-7s6 3 6 7"/><path d="M8 12.5v2a4 4 0 0 0 8 0v-2"/>',
    'office': '<path d="M3 21h18M4 9h16L12 3.5z"/><path d="M6.5 9v9M10.5 9v9M13.5 9v9M17.5 9v9"/>',
    'home': '<path d="M3.5 10.8 12 3.8l8.6 7v9.2h-5.6v-6h-6v6H3.5z"/>',
    'map': '<path d="M9 4.2 3.2 6.1v13.8L9 18l6 2 5.8-1.9V4.3L15 6.1z"/><path d="M9 4.2V18M15 6.1v13.8"/>',
    'compare': '<rect x="3.2" y="4.2" width="17.6" height="15.6"/><path d="M12 4.2v15.6"/>',
    'assist': '<path d="M4 5h16v11H9l-5 4z"/><path d="M8 9.5h8M8 12.5h5"/>',
}

TEXT = {
    'zh': {
        'file': 'architecture.svg', 'lang': 'zh-Hant',
        'font': "'Noto Sans TC','PingFang TC','Microsoft JhengHei',sans-serif",
        'title': 'SAR2Action 架構：衛星與官方資料 → 逐田計算 → FastAPI 後端 → 四個畫面',
        'bar': 'ARCHITECTURE · 系統架構', 'stamp': 'PROTOTYPE · 研究原型',
        'cols': ['01 · DATA · 資料來源', '02 · COMPUTE · 逐田計算', '03 · BACKEND · FastAPI', '04 · SCREENS · 畫面'],
        'data': [('satellite', 'NISAR L2 GCOV', 'L 波段 HH/HV · 上升、下降軌道'),
                 ('radar', 'Sentinel-1 RTC', 'C 波段 VV/VH · 每 12 天'),
                 ('parcels', '國土利用現況調查', '雲林 71,514 塊農地'),
                 ('report', '農業部災情報告', '縣市損失金額 · 全台受害面積'),
                 ('law', '農業天然災害救助辦法', '救助品項與單價（附表）'),
                 ('border', 'NLSC 鄉鎮界線', '雲林 20 個鄉鎮')],
        'compute': [('chart', '每塊田的雷達變化', '颱風前後中位數，單位 dB'),
                    ('calendar', '扣掉「平常 12 天」', '同軌道、颱風前的對照期'),
                    ('area', '受影響面積', '多出來的變化 × 農地面積'),
                    ('coin', '損失金額', '面積 × 全台每公頃損失')],
        'badge': ('NO TRAINED MODEL', '公式計算，不訓練模型', '每個參數都能追到來源'),
        'backend': [('calculator', '救助試算', '伺服器端重算，依法規版本'),
                    ('book', '法規檢索', '固定規則，不交給 AI 判斷'),
                    ('sparkle', 'Gemini', '對話與英文翻譯'),
                    ('user', 'Google 登入', '存下作物、問答、試算')],
        'cloud': ('GOOGLE CLOUD', 'Cloud Run · Cloud SQL', 'Secret Manager 保管金鑰'),
        'screens': [('home', '首頁', '3D 地球 · 颱風雲圖與雨量'),
                    ('map', '受災地圖', '全縣受損面積 · 金額 · 候選田區'),
                    ('compare', '田區比對', 'NISAR 颱風前後 · VH 時序'),
                    ('assist', '補助助手', '能不能申請 · 文件 · 期限 · 試算')],
        'users_label': 'WHO USES IT · 使用者',
        'users': [('farmer', '農民', '我的田有沒有受損？能申請多少救助？要準備什麼、何時截止？'),
                  ('office', '農政人員', '全縣大概損失多少面積與金額？先去哪幾塊田現場勘查？')],
    },
    'en': {
        'file': 'architecture.en.svg', 'lang': 'en',
        'font': "Inter,'Segoe UI',Helvetica,Arial,sans-serif",
        'title': 'SAR2Action architecture: satellite and official data → per-field math → FastAPI backend → four screens',
        'bar': 'ARCHITECTURE', 'stamp': 'PROTOTYPE',
        'cols': ['01 · DATA', '02 · COMPUTE', '03 · BACKEND · FastAPI', '04 · SCREENS'],
        'data': [('satellite', 'NISAR L2 GCOV', 'L-band HH/HV · asc + desc'),
                 ('radar', 'Sentinel-1 RTC', 'C-band VV/VH · every 12 days'),
                 ('parcels', 'Land-use survey', '71,514 farm parcels in Yunlin'),
                 ('report', 'MOA damage report', 'County loss · national area'),
                 ('law', 'Disaster relief rules', 'Crops and NT$ per hectare'),
                 ('border', 'Township borders', '20 townships (NLSC)')],
        'compute': [('chart', 'Radar change per field', 'Median before vs after, dB'),
                    ('calendar', 'Minus a normal 12 days', 'Same orbit, before the storm'),
                    ('area', 'Affected area', 'Extra change × farmland'),
                    ('coin', 'Loss in NT$', 'Area × national loss per ha')],
        'badge': ('NO TRAINED MODEL', 'Plain formulas', 'Every number has a source'),
        'backend': [('calculator', 'Relief estimate', 'Recomputed on the server'),
                    ('book', 'Rule lookup', 'Fixed rules, not the AI'),
                    ('sparkle', 'Gemini', 'Chat and translation'),
                    ('user', 'Google sign-in', 'Saves crop, chat, estimates')],
        'cloud': ('GOOGLE CLOUD', 'Cloud Run · Cloud SQL', 'Keys in Secret Manager'),
        'screens': [('home', 'Home', '3D globe · clouds and rain'),
                    ('map', 'Damage map', 'County area · NT$ · fields'),
                    ('compare', 'Field compare', 'NISAR before/after · VH'),
                    ('assist', 'Relief assistant', 'Eligible? Papers? Deadline?')],
        'users_label': 'WHO USES IT',
        'users': [('farmer', 'Farmers', 'Was my field hit? How much relief can I get? What do I file, and by when?'),
                  ('office', 'Agriculture officers', 'How much area and money did the county lose? Which fields first?')],
    },
}


def icon(name: str, x: float, y: float, size: float = 24, color: str = INK) -> str:
    s = size / 24
    return (f'<g transform="translate({x},{y}) scale({s})" fill="none" stroke="{color}" stroke-width="1.7" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</g>')


def text(x, y, s, cls, right, anchor='start', fill=None) -> str:
    f = f' style="fill:{fill}"' if fill else ''  # inline, so it wins over the class colour
    return f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}" data-max="{right}"{f}>{escape(s)}</text>'


def column(x: int, items, gap: int = 62) -> list[str]:
    out = []
    for i, (ic, title, sub) in enumerate(items):
        y = TOP + 50 + i * gap
        out.append(icon(ic, x + 18, y - 18, 24, BLUE))
        out.append(text(x + 54, y, title, 'item', x + COL_W - 10))
        out.append(text(x + 54, y + 20, sub, 'sub', x + COL_W - 10))
    return out


def card(x, y, w, h, eyebrow, title, sub, dark: bool, ic: str) -> list[str]:
    fill, stroke = (BLUE, 'none') if dark else ('#F6F7F9', 'rgba(0,0,0,.14)')
    c1, c2, c3 = ('#C9D6F5', '#FFFFFF', '#DCE4F7') if dark else (TEXT3, INK, TEXT2)
    return [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}"/>',
            icon(ic, x + w - 40, y + 14, 22, c2),
            text(x + 16, y + 28, eyebrow, 'mono badge', x + w - 46, fill=c1),
            text(x + 16, y + 56, title, 'cardtitle', x + w - 10, fill=c2),
            text(x + 16, y + 79, sub, 'sub', x + w - 10, fill=c3)]


def draw(t: dict) -> str:
    box_h = 410
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{t["font"]}" lang="{t["lang"]}">',
         f'<title>{escape(t["title"])}</title>',
         '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">'
         f'<path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker>'
         "<style>.mono{font-family:'IBM Plex Mono',ui-monospace,Menlo,Consolas,monospace}"
         f'.eyebrow{{font-size:12px;letter-spacing:1.6px;fill:{TEXT3}}}.badge{{font-size:12px;letter-spacing:1.4px}}'
         f'.item{{font-size:15px;font-weight:700;fill:{INK}}}.sub{{font-size:13px;fill:{TEXT2}}}'
         f'.cardtitle{{font-size:16px;font-weight:700}}.screen{{font-size:18px;font-weight:800}}'
         f'.flow{{stroke:{INK};stroke-width:2;fill:none}}</style></defs>',
         f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>',
         # top bar, as in the app
         f'<rect width="{W}" height="64" fill="#000"/>',
         f'<circle cx="40" cy="32" r="13" fill="{BLUE}"/><path d="M33,28 q6,-6 12,0 q-2,6 -8,8 z" fill="#3FA34D"/>',
         '<text x="64" y="40" font-size="22" font-weight="800" fill="#FFF">SAR2Action</text>',
         f'<text x="222" y="39" class="mono" font-size="13" letter-spacing="1.6" fill="#C3C8D1">{escape(t["bar"])}</text>',
         f'<rect x="{W - 224}" y="18" width="184" height="28" fill="{RED}"/>',
         f'<text x="{W - 132}" y="37" text-anchor="middle" class="mono" font-size="12" font-weight="600" letter-spacing="1" fill="#FFF" data-max="{W - 40}">{escape(t["stamp"])}</text>']

    for x, label in zip(COL_X, t['cols']):
        p.append(text(x, TOP - 12, label, 'mono eyebrow', x + COL_W))
    for x in COL_X[:3]:
        p.append(f'<rect x="{x}" y="{TOP}" width="{COL_W}" height="{box_h}" fill="#FFF" stroke="rgba(0,0,0,.55)" stroke-width="1.5"/>')
    p += column(COL_X[0], t['data'])
    p += column(COL_X[1], t['compute'])
    p += column(COL_X[2], t['backend'])
    inner_x, inner_w, inner_y = 20, COL_W - 40, TOP + box_h - 116
    p += card(COL_X[1] + inner_x, inner_y, inner_w, 96, *t['badge'], dark=True, ic='formula')
    p += card(COL_X[2] + inner_x, inner_y, inner_w, 96, *t['cloud'], dark=False, ic='cloud')

    # screens
    sx, sh, sgap = COL_X[3], 92, 14
    for i, (ic, title, sub) in enumerate(t['screens']):
        y = TOP + i * (sh + sgap)
        first = i == 0
        fill = RED if first else '#FFF'
        stroke = 'none' if first else 'rgba(0,0,0,.55)'
        c1, c2, c3 = ('#FFE1DE', '#FFFFFF', '#FFE1DE') if first else (TEXT3, INK, TEXT2)
        p.append(f'<rect x="{sx}" y="{y}" width="{COL_W}" height="{sh}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        p.append(icon(ic, sx + COL_W - 44, y + 16, 26, c2))
        p.append(text(sx + 18, y + 27, f'0{i + 1}', 'mono badge', sx + 60, fill=c1))
        p.append(text(sx + 18, y + 56, title, 'screen', sx + COL_W - 54, fill=c2))
        p.append(text(sx + 18, y + 77, sub, 'sub', sx + COL_W - 10, fill=c3))

    # flow
    mid = TOP + box_h / 2
    for a, b in ((COL_X[0] + COL_W, COL_X[1]), (COL_X[1] + COL_W, COL_X[2])):
        p.append(f'<path d="M{a},{mid} H{b - 4}" class="flow" marker-end="url(#arrow)"/>')
    bx = COL_X[2] + COL_W + 20
    ys = [TOP + i * (sh + sgap) + sh / 2 for i in range(4)]
    p.append(f'<path d="M{COL_X[2] + COL_W},{mid} H{bx} M{bx},{ys[0]} V{ys[-1]}" class="flow"/>')
    for y in ys:
        p.append(f'<path d="M{bx},{y} H{sx - 4}" class="flow" marker-end="url(#arrow)"/>')

    # users
    uy = TOP + box_h + 70
    p.append(text(40, uy - 14, t['users_label'], 'mono eyebrow', 400))
    half = (W - 80 - 10) / 2
    for i, ((ic, who, need), accent) in enumerate(zip(t['users'], (BLUE, RED))):
        x = 40 + i * (half + 10)
        p.append(f'<rect x="{x}" y="{uy}" width="{half}" height="92" fill="#F6F7F9" stroke="rgba(0,0,0,.14)"/>')
        p.append(f'<rect x="{x}" y="{uy}" width="5" height="92" fill="{accent}"/>')
        p.append(icon(ic, x + 24, uy + 18, 26, accent))
        p.append(text(x + 62, uy + 38, who, 'cardtitle', x + half - 16, fill=INK))
        p.append(text(x + 24, uy + 70, need, 'sub', x + half - 16))
    p.append('</svg>')
    return '\n'.join(p) + '\n'


if __name__ == '__main__':
    here = Path(__file__).resolve().parent
    for t in TEXT.values():
        (here / t['file']).write_text(draw(t), encoding='utf-8')
        print('wrote', t['file'])
