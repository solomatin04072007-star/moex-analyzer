# import_portfolio.py

import pandas as pd
import re
import requests
import os
import sys
import urllib3
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REPORT_FILE = 'reportc02d24f6-cc26-19b6-cc79-bf06a1d2aa0e.xlsx'
PORTFOLIO_FILE = 'portfolio.csv'

NAME_TO_TICKER = {
    'Газпром': 'GAZP',
    'ЛУКОЙЛ': 'LKOH',
    'НОВАТЭК': 'NVTK',
    'Роснефть': 'ROSN',
    'Сбербанк': 'SBER',
    'Т-Технологии': 'T',
    'Самолет': 'SMLT',
    'ВТБ': 'VTBR',
    'МТС': 'MTSS',
    'Магнит': 'MGNT',
    'Сургутнефтегаз': 'SNGS',
    'Татнефть': 'TATN',
    'Норникель': 'GMKN',
    'LQDT': 'LQDT',
}

_ISIN_CACHE = {}


def find_ticker_by_isin(isin):
    """Пробует найти SECID облигации/акции по ISIN через MOEX."""
    if isin in _ISIN_CACHE:
        return _ISIN_CACHE[isin]

    try:
        url = f'https://iss.moex.com/iss/securities/{isin}.json'
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        if resp.status_code != 200:
            _ISIN_CACHE[isin] = None
            return None

        data = resp.json()
        if not isinstance(data, dict) or 'securities' not in data:
            _ISIN_CACHE[isin] = None
            return None

        block = data['securities']
        cols = block.get('columns', [])
        rows = block.get('data', [])

        if 'SECID' not in cols or not rows:
            _ISIN_CACHE[isin] = None
            return None

        secid_idx = cols.index('SECID')
        board_idx = cols.index('BOARDID') if 'BOARDID' in cols else None
        primary_idx = cols.index('IS_PRIMARY') if 'IS_PRIMARY' in cols else None

        # Приоритет 1: TQBR (акции) или TQCB (облигации)
        if board_idx is not None:
            for row in rows:
                if row[board_idx] in ('TQBR', 'TQCB', 'TQTF', 'TQIF', 'TQOD'):
                    ticker = row[secid_idx]
                    _ISIN_CACHE[isin] = ticker
                    return ticker

        # Приоритет 2: IS_PRIMARY=1
        if primary_idx is not None:
            for row in rows:
                if row[primary_idx] == 1:
                    ticker = row[secid_idx]
                    _ISIN_CACHE[isin] = ticker
                    return ticker

        # Fallback: первый SECID
        ticker = rows[0][secid_idx]
        _ISIN_CACHE[isin] = ticker
        return ticker

    except Exception as e:
        print(f'  ⚠️ Ошибка поиска {isin}: {e}')
        _ISIN_CACHE[isin] = None
        return None


def find_ticker(name):
    """Извлекает тикер из названия бумаги."""
    if pd.isna(name):
        return None
    name = str(name).strip()

    # 1. По ключевым словам в названии
    for key, ticker in NAME_TO_TICKER.items():
        if key.lower() in name.lower():
            return ticker

    # 2. По ISIN через MOEX
    isin_match = re.search(r'\b(RU[A-Z0-9]{10})\b', name)
    if isin_match:
        isin = isin_match.group(1)
        ticker = find_ticker_by_isin(isin)
        if ticker:
            return ticker
        # Fallback: используем сам ISIN
        _ISIN_CACHE[isin] = isin
        return isin

    return None


def parse_report(filepath):
    """Читает отчёт ВТБ и возвращает список сделок."""
    print(f'📂 Читаем {filepath}...')

    try:
        import openpyxl
    except ImportError:
        print('❌ Установите openpyxl: pip install openpyxl')
        sys.exit(1)

    df = pd.read_excel(filepath, sheet_name=0, header=None)
    print(f'  Строк в файле: {len(df)}')

    # Ищем последнюю секцию "Завершенные в отчетном периоде сделки"
    section_start = None
    for i in range(len(df) - 1, -1, -1):
        row = df.iloc[i]
        for col_idx in range(min(5, len(row))):
            cell = str(row[col_idx]) if pd.notna(row[col_idx]) else ''
            if 'Завершенные в отчетном периоде сделки' in cell:
                section_start = i
                break
        if section_start is not None:
            break

    if section_start is None:
        print('❌ Не найдена секция "Завершенные сделки"')
        return []

    print(f'  Секция найдена на строке {section_start + 1}')

    # Ищем заголовок
    header_row = None
    for i in range(section_start, min(section_start + 10, len(df))):
        row = df.iloc[i]
        for col_idx in range(min(3, len(row))):
            cell = str(row[col_idx]) if pd.notna(row[col_idx]) else ''
            if 'Наименование' in cell:
                header_row = i
                break
        if header_row is not None:
            break

    if header_row is None:
        print('❌ Не найдена строка заголовков')
        return []

    print(f'  Заголовки на строке {header_row + 1}')

    # Индексы колонок
    NAME_IDX = 1
    DATE_IDX = 2
    TYPE_IDX = 5
    QTY_IDX = 7
    SUM_IDX = 11

    trades = []
    skipped = 0
    skipped_names = []

    for i in range(header_row + 1, len(df)):
        row = df.iloc[i]

        name = row[NAME_IDX] if NAME_IDX < len(row) else None
        if pd.isna(name) or str(name).strip() == '':
            break

        name = str(name).strip()
        if name.startswith('Итого') or name.startswith('ИТОГО'):
            break

        date_val = row[DATE_IDX] if DATE_IDX < len(row) else None
        if pd.isna(date_val):
            continue

        trade_type = row[TYPE_IDX] if TYPE_IDX < len(row) else None
        if pd.isna(trade_type):
            continue
        trade_type = str(trade_type).strip().lower()

        if trade_type not in ('покупка', 'продажа'):
            continue

        qty = row[QTY_IDX] if QTY_IDX < len(row) else None
        if pd.isna(qty):
            continue

        sum_rub = row[SUM_IDX] if SUM_IDX < len(row) else None
        if pd.isna(sum_rub):
            continue

        try:
            qty = int(qty)
            sum_rub = float(sum_rub)
        except (ValueError, TypeError):
            continue

        if qty <= 0:
            continue

        price = sum_rub / qty

        ticker = find_ticker(name)
        if ticker is None:
            skipped += 1
            skipped_names.append(name[:80])
            continue

        date_str = pd.to_datetime(date_val).strftime('%Y-%m-%d')

        trades.append({
            'date': date_str,
            'ticker': ticker,
            'type': 'buy' if trade_type == 'покупка' else 'sell',
            'quantity': qty,
            'price': round(price, 4),
        })

    print(f'\n✅ Распознано сделок: {len(trades)}')
    if skipped:
        print(f'⚠️ Пропущено: {skipped}')
        print('\nПропущенные бумаги:')
        for n in skipped_names[:15]:
            print(f'  • {n}')
        if len(skipped_names) > 15:
            print(f'  ... и ещё {len(skipped_names) - 15}')

    return trades


def import_to_portfolio(trades):
    """Добавляет сделки в portfolio.csv, пропуская дубли."""
    if not trades:
        print('Нет сделок для импорта.')
        return

    if os.path.exists(PORTFOLIO_FILE):
        existing = pd.read_csv(PORTFOLIO_FILE)
        existing['date'] = existing['date'].astype(str)
        existing_keys = set(
            existing.apply(
                lambda r: f"{r['date']}|{r['ticker']}|{r['type']}|{r['quantity']}|{r['price']}",
                axis=1
            )
        )
    else:
        existing = pd.DataFrame(columns=['date', 'ticker', 'type', 'quantity', 'price'])
        existing_keys = set()

    added = 0
    skipped = 0
    new_rows = []

    for t in trades:
        key = f"{t['date']}|{t['ticker']}|{t['type']}|{t['quantity']}|{t['price']}"
        if key in existing_keys:
            skipped += 1
            continue

        new_rows.append({
            'date': t['date'],
            'ticker': t['ticker'],
            'type': t['type'],
            'quantity': t['quantity'],
            'price': t['price'],
        })
        existing_keys.add(key)
        added += 1

    if not new_rows:
        print(f'Все сделки уже есть в портфеле (пропущено {skipped}).')
        return

    df_new = pd.DataFrame(new_rows)
    df_all = pd.concat([existing, df_new], ignore_index=True)
    df_all['date'] = pd.to_datetime(df_all['date'])
    df_all = df_all.sort_values('date').reset_index(drop=True)
    df_all['date'] = df_all['date'].dt.strftime('%Y-%m-%d')
    df_all.to_csv(PORTFOLIO_FILE, index=False)

    print(f'\n📊 Импорт завершён:')
    print(f'  Добавлено: {added}')
    print(f'  Пропущено дублей: {skipped}')
    print(f'  Всего в портфеле: {len(df_all)}')


if __name__ == '__main__':
    if not os.path.exists(REPORT_FILE):
        print(f'❌ Файл {REPORT_FILE} не найден.')
        sys.exit(1)

    trades = parse_report(REPORT_FILE)

    if trades:
        print('\n📋 Первые 15 распознанных сделок:')
        for t in trades[:15]:
            print(f"  {t['date']} | {t['ticker']:15s} | {t['type']:5s} | "
                  f"{t['quantity']:5d} шт. | {t['price']:.2f} ₽")

        print(f'\n📝 Импортировать в {PORTFOLIO_FILE}? (y/n): ', end='')
        answer = input().strip().lower()
        if answer == 'y':
            import_to_portfolio(trades)
        else:
            print('Импорт отменён.')