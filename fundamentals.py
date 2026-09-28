# fundamentals.py

import requests
import time


def get_fundamental_data(ticker, retries=3, delay=1.5):
    """Получить P/E, P/B, дивидендную доходность с MOEX ISS (с повторными попытками)."""
    url = (f'https://iss.moex.com/iss/statistics/engines/stock/markets/shares/'
           f'boards/TQBR/securities/{ticker}.json')

    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            if attempt < retries - 1:
                print(f'  Попытка {attempt + 1} не удалась для {ticker}, ждём {delay} сек...')
                time.sleep(delay)
                continue
            print(f'Ошибка фундаментала {ticker}: {e}')
            return None

    try:
        if not isinstance(data, list) or len(data) < 2:
            return None
        stat_list = data[1].get('statistics')
        if not isinstance(stat_list, list) or len(stat_list) < 2:
            return None
        rows = stat_list[1]
        if not isinstance(rows, list) or not rows:
            return None

        result = {}
        for row in rows:
            if isinstance(row, dict):
                name = row.get('name')
                value = row.get('value')
                if name:
                    result[name] = value

        return {
            'pe': result.get('P/E'),
            'pb': result.get('P/B'),
            'div_yield': result.get('DIVYIELD'),
            'market_cap': result.get('ISSUECAPITALIZATION')
        }
    except Exception as e:
        print(f'Ошибка парсинга фундаментала {ticker}: {e}')
        return None


def fundamental_score(ticker, signal_type):
    data = get_fundamental_data(ticker)
    if not data:
        return None

    pe = data.get('pe')
    div = data.get('div_yield')
    tags = []

    if signal_type == 'BUY':
        try:
            if pe is not None and float(pe) > 0:
                if float(pe) < 10:
                    tags.append('📗 P/E низкий — недооценена')
                elif float(pe) > 50:
                    tags.append('📕 P/E высокий — осторожно')
        except (ValueError, TypeError):
            pass
        try:
            if div is not None and float(div) > 8:
                tags.append(f'💰 Дивдоходность {float(div):.1f}%')
        except (ValueError, TypeError):
            pass

    return tags if tags else None