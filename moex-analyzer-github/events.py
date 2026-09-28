# events.py

import requests
import time
from datetime import datetime, timedelta
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Connection': 'keep-alive',
}


def get_upcoming_events(tickers, days_ahead=90, retries=2):
    """
    Возвращает уже объявленные дивидендные события в ближайшие `days_ahead` дней.
    ⚠️ MOEX ISS содержит только прошедшие и уже объявленные события.
    """
    events = []
    today = datetime.now()
    end = today + timedelta(days=days_ahead)

    for ticker in tickers:
        data = None
        for attempt in range(retries):
            try:
                url = f'https://iss.moex.com/iss/securities/{ticker}/dividends.json?iss.meta=off'
                resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception:
                if attempt < retries - 1:
                    time.sleep(1.0)
                    continue
                data = None

        if not isinstance(data, dict):
            continue

        div_block = data.get('dividends')
        if not isinstance(div_block, list) or len(div_block) < 2:
            continue

        rows = div_block[1]
        if not isinstance(rows, list):
            continue

        for row in rows:
            if not isinstance(row, dict):
                continue
            reg_date_str = row.get('registryclosedate')
            if not reg_date_str:
                continue
            try:
                reg_date = datetime.strptime(reg_date_str, '%Y-%m-%d')
            except ValueError:
                continue
            if today <= reg_date <= end:
                amount = row.get('value')
                events.append(
                    f"📅 {ticker}: дивиденд {amount} ₽, отсечка {reg_date.strftime('%d.%m.%Y')}"
                )

    return events