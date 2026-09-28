# portfolio_manager.py

import os
import re
import pandas as pd
import requests
import urllib3
from datetime import datetime, timedelta
import config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PORTFOLIO_PATH = 'portfolio.csv'
COLUMNS = ['date', 'ticker', 'type', 'quantity', 'price']

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
}

_PRICE_CACHE = {}
_BOND_INFO_CACHE = {}


# =========================================================
#   КАРТА СЕКТОРОВ
# =========================================================

STOCK_SECTORS = {
    # Финансы
    'SBER': 'Финансы', 'SBERP': 'Финансы', 'VTBR': 'Финансы',
    'T': 'Финансы', 'TCSG': 'Финансы', 'MOEX': 'Финансы',
    'SFIN': 'Финансы', 'BSPB': 'Финансы', 'CBOM': 'Финансы',

    # Нефть и газ
    'GAZP': 'Нефть и газ', 'LKOH': 'Нефть и газ', 'ROSN': 'Нефть и газ',
    'NVTK': 'Нефть и газ', 'SNGS': 'Нефть и газ', 'SNGSP': 'Нефть и газ',
    'TATN': 'Нефть и газ', 'TATNP': 'Нефть и газ', 'TRNFP': 'Нефть и газ',
    'SIBN': 'Нефть и газ', 'RNFT': 'Нефть и газ',

    # Металлы и добыча
    'GMKN': 'Металлы и добыча', 'PLZL': 'Металлы и добыча',
    'CHMF': 'Металлы и добыча', 'NLMK': 'Металлы и добыча',
    'MAGN': 'Металлы и добыча', 'ALRS': 'Металлы и добыча',
    'RUAL': 'Металлы и добыча', 'VSMO': 'Металлы и добыча',
    'TRMK': 'Металлы и добыча', 'MTLR': 'Металлы и добыча',
    'MTLRP': 'Металлы и добыча',

    # Телеком
    'MTSS': 'Телеком', 'RTKM': 'Телеком', 'RTKMP': 'Телеком',
    'MGTS': 'Телеком', 'MGTSP': 'Телеком',

    # IT
    'YDEX': 'IT', 'VKCO': 'IT', 'OZON': 'IT', 'POSI': 'IT',
    'DIAS': 'IT', 'SOFL': 'IT', 'DATA': 'IT',

    # Девелопмент
    'SMLT': 'Девелопмент', 'PIKK': 'Девелопмент', 'LSRG': 'Девелопмент',
    'ETLN': 'Девелопмент', 'LENT': 'Девелопмент',

    # Ритейл
    'MGNT': 'Ритейл', 'FIVE': 'Ритейл', 'OKEY': 'Ритейл',
    'MVID': 'Ритейл', 'FIXR': 'Ритейл',

    # Транспорт
    'AFLT': 'Транспорт', 'NMTP': 'Транспорт', 'FLOT': 'Транспорт',

    # Энергетика
    'HYDR': 'Энергетика', 'IRAO': 'Энергетика', 'UPRO': 'Энергетика',
    'FEES': 'Энергетика', 'MSNG': 'Энергетика', 'TGKA': 'Энергетика',
    'TGKB': 'Энергетика', 'TGKN': 'Энергетика', 'LSNG': 'Энергетика',

    # Химия
    'PHOR': 'Химия', 'AKRN': 'Химия', 'KAZT': 'Химия',
    'NKNC': 'Химия', 'NKNCP': 'Химия',

    # Холдинги
    'AFKS': 'Холдинги', 'SISTEMA': 'Холдинги',
}


# =========================================================
#   РАБОТА С ФАЙЛОМ ПОРТФЕЛЯ
# =========================================================

def load_portfolio():
    if not os.path.exists(PORTFOLIO_PATH):
        df = pd.DataFrame(columns=COLUMNS)
        df.to_csv(PORTFOLIO_PATH, index=False)
        return df

    try:
        df = pd.read_csv(PORTFOLIO_PATH)
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = None
        df = df[COLUMNS]
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce')
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        df['type'] = df['type'].astype(str).str.lower()
        df['ticker'] = df['ticker'].astype(str).str.upper()
        df = df.dropna(subset=['date', 'ticker', 'type', 'quantity', 'price'])
        df = df.sort_values('date').reset_index(drop=True)
        return df
    except Exception as e:
        print(f'Ошибка загрузки портфеля: {e}')
        return pd.DataFrame(columns=COLUMNS)


def save_portfolio(df):
    df.to_csv(PORTFOLIO_PATH, index=False)
    return True


def add_trade(ticker, trade_type, quantity, price, date=None):
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')

    df = load_portfolio()
    new_row = pd.DataFrame([{
        'date': date,
        'ticker': ticker.upper(),
        'type': trade_type.lower(),
        'quantity': float(quantity),
        'price': float(price),
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    df = df.sort_values('date').reset_index(drop=True)
    save_portfolio(df)
    return True


def remove_trade(index):
    df = load_portfolio()
    if index in df.index:
        df = df.drop(index).reset_index(drop=True)
        save_portfolio(df)
        return True
    return False


# =========================================================
#   ОПРЕДЕЛЕНИЕ ТИПА БУМАГИ
# =========================================================

def _is_isin(ticker):
    return bool(re.match(r'^(RU|SU|BY|XS)[A-Z0-9]{9,11}$', str(ticker).upper()))


def _get_security_info(ticker):
    """Определяет информацию о бумаге с несколькими fallback-ами."""
    if ticker in _BOND_INFO_CACHE:
        return _BOND_INFO_CACHE[ticker]

    tk = str(ticker).upper()

    # 1. Явные ETF (по тикеру)
    known_etfs = {'LQDT', 'TMOS', 'SBMX', 'VTBX', 'RUSF', 'AKGD', 'GOLD',
                  'TECH', 'EQMX', 'INFL', 'MUTF', 'AKRT', 'SBGB'}
    if tk in known_etfs:
        info = {'secid': tk, 'board': 'TQTF', 'market': 'shares', 'type': 'etf'}
        _BOND_INFO_CACHE[ticker] = info
        return info

    # 2. ISIN → облигация
    if re.match(r'^(RU|SU|BY|XS)[A-Z0-9]{9,11}$', tk):
        info = {'secid': tk, 'board': 'TQCB', 'market': 'bonds', 'type': 'bond'}
        _BOND_INFO_CACHE[ticker] = info
        return info

    # 3. Пробуем MOEX
    url = f'https://iss.moex.com/iss/securities/{tk}.json'
    info = None

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and 'securities' in data:
                block = data['securities']
                cols = block.get('columns', [])
                rows = block.get('data', [])

                if cols and rows:
                    secid_idx = cols.index('SECID') if 'SECID' in cols else None
                    board_idx = cols.index('BOARDID') if 'BOARDID' in cols else None
                    type_idx = cols.index('TYPE') if 'TYPE' in cols else None

                    primary_boards = ('TQBR', 'TQCB', 'TQOB', 'TQTF', 'TQIF')
                    best = None
                    for row in rows:
                        board = row[board_idx] if board_idx is not None else None
                        if board in primary_boards:
                            best = row
                            break
                    if best is None:
                        best = rows[0]

                    secid = best[secid_idx] if secid_idx is not None else tk
                    board = best[board_idx] if board_idx is not None else None
                    sec_type = str(best[type_idx]) if type_idx is not None else ''

                    if board in ('TQBR', 'TQTF', 'TQIF', 'TQOD', 'TQPI'):
                        market = 'shares'
                    elif board in ('TQCB', 'TQOB', 'TQOY'):
                        market = 'bonds'
                    else:
                        market = 'shares'

                    sec_type_lower = sec_type.lower()
                    if 'облигац' in sec_type_lower or market == 'bonds':
                        kind = 'bond'
                    elif 'пай' in sec_type_lower or board in ('TQTF', 'TQIF'):
                        kind = 'etf'
                    else:
                        kind = 'stock'

                    info = {
                        'secid': secid,
                        'board': board,
                        'market': market,
                        'type': kind,
                    }
    except Exception:
        pass

    # 4. Fallback — считаем акцией TQBR
    if info is None:
        info = {'secid': tk, 'board': 'TQBR', 'market': 'shares', 'type': 'stock'}

    _BOND_INFO_CACHE[ticker] = info
    return info


def get_security_type(ticker):
    """Возвращает тип: 'stock', 'bond', 'etf', или 'unknown'."""
    info = _get_security_info(str(ticker).upper())
    if info:
        return info['type']
    return 'unknown'


# =========================================================
#   ЗАГРУЗКА ТЕКУЩЕЙ ЦЕНЫ
# =========================================================

def _get_price_from_history(secid, board, market, days_back=10):
    """Загружает последнюю цену с MOEX history API."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    url = (
        f'https://iss.moex.com/iss/history/engines/stock/markets/{market}/'
        f'boards/{board}/securities/{secid}.json'
    )
    params = {
        'iss.json': 'extended',
        'limit': 10,
        'from': start_date.strftime('%Y-%m-%d'),
        'till': end_date.strftime('%Y-%m-%d'),
    }

    try:
        resp = requests.get(url, params=params, headers=HEADERS,
                            timeout=15, verify=False)
        if resp.status_code != 200:
            return None

        data = resp.json()
        if not isinstance(data, list) or len(data) < 2:
            return None

        hist = data[1].get('history')
        if not isinstance(hist, list) or len(hist) < 2:
            return None

        rows = hist[1]
        if not isinstance(rows, list) or not rows:
            return None

        last = rows[-1]
        if not isinstance(last, dict):
            return None

        close = last.get('CLOSE')
        face = last.get('FACEVALUE')

        if close is None:
            return None

        close = float(close)

        if market == 'bonds':
            if face is None:
                face = 1000
            face = float(face)
            price_rub = close * face / 100

            accrued = last.get('ACCRUEDINT')
            if accrued is not None:
                try:
                    price_rub += float(accrued)
                except (ValueError, TypeError):
                    pass
            return price_rub
        else:
            return close

    except Exception:
        return None


def get_current_price(ticker):
    """Возвращает текущую цену в рублях за 1 единицу или None."""
    ticker = str(ticker).upper()

    if ticker in _PRICE_CACHE:
        return _PRICE_CACHE[ticker]

    info = _get_security_info(ticker)

    if info:
        price = _get_price_from_history(
            info['secid'], info['board'], info['market']
        )
        if price:
            _PRICE_CACHE[ticker] = price
            return price

    # Fallback через data_manager
    try:
        from data_manager import get_stock_history
        session = requests.Session()
        df = get_stock_history(session, ticker)
        if not df.empty:
            price = float(df['close'].iloc[-1])
            _PRICE_CACHE[ticker] = price
            return price
    except Exception:
        pass

    _PRICE_CACHE[ticker] = None
    return None


# =========================================================
#   РАСЧЁТ ПОЗИЦИЙ
# =========================================================

def calculate_positions(portfolio_df=None, update_prices=True):
    """Считает позиции по каждой бумаге. Возвращает словарь."""
    if portfolio_df is None:
        portfolio_df = load_portfolio()

    if portfolio_df.empty:
        return {}

    positions = {}

    for ticker in portfolio_df['ticker'].unique():
        tkr_df = portfolio_df[portfolio_df['ticker'] == ticker]

        buys = tkr_df[tkr_df['type'] == 'buy']
        sells = tkr_df[tkr_df['type'] == 'sell']

        total_bought_qty = buys['quantity'].sum()
        total_sold_qty = sells['quantity'].sum()
        total_buy_cost = (buys['quantity'] * buys['price']).sum()
        total_sell_revenue = (sells['quantity'] * sells['price']).sum()

        current_qty = total_bought_qty - total_sold_qty
        avg_buy_price = total_buy_cost / total_bought_qty if total_bought_qty > 0 else 0
        realized_pnl = total_sell_revenue - (total_sold_qty * avg_buy_price)

        current_price = None
        if update_prices and current_qty > 0:
            current_price = get_current_price(ticker)

        if current_price is None:
            current_price = avg_buy_price

        unrealized_pnl = current_qty * (current_price - avg_buy_price)
        cost_basis = current_qty * avg_buy_price
        current_value = current_qty * current_price
        total_pnl = realized_pnl + unrealized_pnl
        pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0

        sec_type = get_security_type(ticker)

        positions[ticker] = {
            'ticker': ticker,
            'type': sec_type,
            'quantity': current_qty,
            'avg_buy_price': round(avg_buy_price, 4),
            'current_price': round(current_price, 4) if current_price else None,
            'cost_basis': round(cost_basis, 2),
            'current_value': round(current_value, 2),
            'realized_pnl': round(realized_pnl, 2),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'total_pnl': round(total_pnl, 2),
            'pnl_pct': round(pnl_pct, 2),
            'total_bought': total_bought_qty,
            'total_sold': total_sold_qty,
        }

    return positions


def get_portfolio_summary(positions=None):
    """Общая сводка по портфелю."""
    if positions is None:
        positions = calculate_positions()

    if not positions:
        return {
            'total_value': 0, 'total_cost': 0,
            'total_unrealized_pnl': 0, 'total_realized_pnl': 0,
            'total_pnl': 0, 'pnl_pct': 0, 'positions_count': 0,
        }

    active = {t: p for t, p in positions.items() if p['quantity'] > 0}

    total_value = sum(p['current_value'] for p in active.values())
    total_cost = sum(p['cost_basis'] for p in active.values())
    total_unrealized = sum(p['unrealized_pnl'] for p in active.values())
    total_realized = sum(p['realized_pnl'] for p in positions.values())
    total_pnl = total_unrealized + total_realized
    pnl_pct = (total_unrealized / total_cost * 100) if total_cost > 0 else 0

    return {
        'total_value': round(total_value, 2),
        'total_cost': round(total_cost, 2),
        'total_unrealized_pnl': round(total_unrealized, 2),
        'total_realized_pnl': round(total_realized, 2),
        'total_pnl': round(total_pnl, 2),
        'pnl_pct': round(pnl_pct, 2),
        'positions_count': len(active),
    }


# =========================================================
#   СЕКТОРНАЯ КОНЦЕНТРАЦИЯ
# =========================================================

def get_sector_concentration(positions=None):
    """Возвращает словарь {сектор: процент от портфеля}."""
    if positions is None:
        positions = calculate_positions()

    if not positions:
        return {}

    active = {t: p for t, p in positions.items() if p['quantity'] > 0}
    if not active:
        return {}

    # Пробуем MOEX
    moex_sectors = {}
    try:
        from data_manager import get_ticker_sectors
        session = requests.Session()
        moex_sectors = get_ticker_sectors(session) or {}
    except Exception:
        pass

    total_value = sum(p['current_value'] for p in active.values())
    if total_value == 0:
        return {}

    sector_values = {}
    for ticker, p in active.items():
        sec_type = p.get('type', 'unknown')
        tk = str(ticker).upper()

        if sec_type == 'bond':
            sector = 'Облигации'
        elif sec_type == 'etf':
            sector = 'ETF / Фонды'
        elif sec_type == 'stock':
            sector = STOCK_SECTORS.get(tk)
            if sector is None:
                sector = moex_sectors.get(tk)
            if sector is None or sector == 'Прочее':
                sector = 'Прочие акции'
        else:
            sector = 'Прочее'

        sector_values[sector] = sector_values.get(sector, 0) + p['current_value']

    return {
        s: round((v / total_value) * 100, 1)
        for s, v in sector_values.items()
    }


# =========================================================
#   ФОРМАТИРОВАНИЕ ДЛЯ NOTIFIER
# =========================================================

TYPE_EMOJI = {
    'stock': '📈',
    'bond': '📜',
    'etf': '🏦',
    'unknown': '❓',
}


def format_positions_for_notifier(positions=None, max_positions=10):
    """Форматирует топ позиций для текстового уведомления."""
    if positions is None:
        positions = calculate_positions()

    if not positions:
        return None

    active = {t: p for t, p in positions.items() if p['quantity'] > 0}
    if not active:
        return None

    lines = []
    sorted_positions = sorted(active.items(), key=lambda x: -x[1]['current_value'])

    for ticker, p in sorted_positions[:max_positions]:
        emoji = '📈' if p['pnl_pct'] > 0 else ('📉' if p['pnl_pct'] < 0 else '➖')
        type_icon = TYPE_EMOJI.get(p.get('type', 'unknown'), '')
        lines.append(
            f"  {emoji} {type_icon} {ticker}: {p['quantity']:.0f} шт. "
            f"({p['avg_buy_price']:.2f} → {p['current_price']:.2f} ₽), "
            f"P&L: {p['unrealized_pnl']:+.0f} ₽ ({p['pnl_pct']:+.1f}%)"
        )

    return lines


def clear_cache():
    """Очищает кэш цен и информации о бумагах."""
    global _PRICE_CACHE, _BOND_INFO_CACHE
    _PRICE_CACHE = {}
    _BOND_INFO_CACHE = {}