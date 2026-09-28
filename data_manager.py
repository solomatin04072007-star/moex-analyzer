# data_manager.py

import apimoex
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MIN_ROWS_FOR_INDICATORS = 30

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Connection': 'keep-alive',
}

# Ключевые слова надёжных эмитентов
TRUSTED_KEYWORDS = [
    'ОФЗ', 'Газпром', 'Лукойл', 'Роснефть', 'Татнефть', 'НОВАТЭК',
    'Сургутнефтегаз', 'Транснефть', 'Сбер', 'ВТБ', 'Россельхозбанк',
    'ВЭБ', 'ДОМ.РФ', 'РЖД', 'РусГидро', 'Россети', 'Интер РАО',
    'Норникель', 'Полюс', 'Северсталь', 'ММК', 'НЛМК', 'АЛРОСА',
    'ФосАгро', 'МТС', 'Ростелеком', 'Мегафон', 'X5', 'Магнит', 'Аэрофлот',
    'Мосэнерго', 'Правительство Москвы',
]


# =========================================================
#   ОБЩАЯ ФУНКЦИЯ ЗАГРУЗКИ С MOEX ISS
# =========================================================

def _load_iss_data(url, params, retries=3, delay=1.0):
    all_rows = []
    start = 0
    total = None
    key = None

    while True:
        p = params.copy()
        p['start'] = start

        data_raw = None
        for attempt in range(retries):
            try:
                resp = requests.get(url, params=p, headers=HEADERS,
                                    timeout=30, verify=False)
                resp.raise_for_status()
                data_raw = resp.json()
                break
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(delay)
                    continue
                print(f'  Ошибка запроса: {e}')
                data_raw = None

        if data_raw is None:
            break

        if not isinstance(data_raw, list) or len(data_raw) < 2:
            break

        rows = []
        for k in ('history', 'securities'):
            block_list = data_raw[1].get(k)
            if isinstance(block_list, list) and len(block_list) >= 2:
                rows = block_list[1]
                if isinstance(rows, list):
                    all_rows.extend(rows)
                key = k
                break
        else:
            break

        cursor_key = f'{key}.cursor'
        cursor_list = data_raw[1].get(cursor_key)
        if isinstance(cursor_list, list) and len(cursor_list) >= 2:
            cursor_data = cursor_list[1]
            if isinstance(cursor_data, list) and cursor_data:
                total = cursor_data[0].get('TOTAL')

        if len(rows) < p.get('limit', 100):
            break
        start += len(rows)
        if total and start >= total:
            break

    return all_rows


# =========================================================
#   АКЦИИ
# =========================================================

def _load_history(ticker, years=0.25):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)
    url = (f'https://iss.moex.com/iss/history/engines/stock/markets/shares/'
           f'boards/TQBR/securities/{ticker}.json')
    params = {
        'iss.json': 'extended',
        'limit': 100,
        'from': start_date.strftime('%Y-%m-%d'),
        'till': end_date.strftime('%Y-%m-%d'),
    }
    rows = _load_iss_data(url, params)
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    keep = ['TRADEDATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME']
    df = df[[c for c in keep if c in df.columns]]
    df = df.rename(columns={
        'TRADEDATE': 'date', 'OPEN': 'open', 'HIGH': 'high',
        'LOW': 'low', 'CLOSE': 'close', 'VOLUME': 'volume'
    })
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()

    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df.dropna(subset=['open', 'high', 'low', 'close', 'volume'])

    if len(df) < MIN_ROWS_FOR_INDICATORS:
        return pd.DataFrame()

    return df


def get_stock_history(session, ticker, board='TQBR'):
    return _load_history(ticker, years=0.25)


def download_full_history(ticker, years=5):
    print(f'  Подключение к MOEX ISS для {ticker}...')
    df = _load_history(ticker, years=years)
    if df.empty:
        print(f'  ИТОГО: 0 записей для {ticker}')
    else:
        print(f'  ИТОГО: {len(df)} свечей после очистки для {ticker}')
    return df


def get_all_tickers(session):
    try:
        data = apimoex.get_board_securities(session, board='TQBR')
        tickers = [item['SECID'] for item in data if 'SECID' in item]
        print(f'  Найдено {len(tickers)} акций на MOEX')
        return tickers
    except Exception as e:
        print(f'  Ошибка получения списка акций: {e}')
        return []


def get_ticker_sectors(session):
    url = 'https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities.json'
    params = {
        'iss.meta': 'off',
        'iss.only': 'securities',
        'securities.columns': 'SECID,SECTOR',
        'limit': 100
    }
    rows = _load_iss_data(url, params)
    result = {}
    for row in rows:
        if isinstance(row, dict) and 'SECID' in row:
            result[row['SECID']] = row.get('SECTOR') or 'Прочее'
    return result


def get_all_stocks_data(tickers):
    session = requests.Session()

    if tickers == ['ALL']:
        tickers = get_all_tickers(session)
        if not tickers:
            return {}

    from analyzer import add_indicators, get_last_signal
    results = {}
    skipped = 0

    for ticker in tickers:
        df = get_stock_history(session, ticker)
        if df.empty:
            skipped += 1
            continue
        try:
            df = add_indicators(df)
            signal = get_last_signal(df)
        except Exception as e:
            print(f'  Пропускаем {ticker}: {e}')
            skipped += 1
            continue

        results[ticker] = {
            'last_close': float(df['close'].iloc[-1]),
            'rsi': float(df['RSI'].iloc[-1]),
            'macd': float(df['MACD'].iloc[-1]),
            'macd_signal': float(df['MACD_signal'].iloc[-1]),
            'atr': float(df['ATR'].iloc[-1]) if 'ATR' in df.columns and pd.notna(df['ATR'].iloc[-1]) else None,
            'signal': signal
        }

    if skipped > 0:
        print(f'  Пропущено тикеров: {skipped}')

    return results


# =========================================================
#   ОБЛИГАЦИИ
# =========================================================

def _mark_bond_accessibility(df: pd.DataFrame) -> pd.DataFrame:
    """
    Проставляет флаг 'unqualified_allowed' (True/False) и 'access_reason'
    на основе эвристических правил.
    """
    df = df.copy()

    def check_access(row):
        # 1. Если рейтинг есть и он ниже A+, то недоступно
        rating = row.get('CREDIT_RATING')
        if rating and rating != 'trusted':
            rating_upper = str(rating).upper().replace('RU', '')
            # Простая проверка: если рейтинг не начинается с AAA, AA, A+
            if not any(rating_upper.startswith(prefix) for prefix in ['AAA', 'AA', 'A+']):
                return False, f'Рейтинг {rating} ниже A+'

        # 2. Структурные облигации
        bond_type = str(row.get('BONDTYPE', '')).lower()
        bond_subtype = str(row.get('BONDSUBTYPE', '')).lower()
        if 'структурн' in bond_type or 'структурн' in bond_subtype:
            return False, 'Структурная облигация'

        # 3. Облигации с залоговым обеспечением (кроме ипотечных)
        if 'залог' in bond_type or 'залог' in bond_subtype:
            if 'ипотеч' not in bond_type and 'ипотеч' not in bond_subtype:
                return False, 'Обеспечена залогом'

        # 4. Иностранные эмитенты с низким рейтингом (если SECID не RU/SU)
        secid = str(row.get('SECID', ''))
        if not secid.startswith(('RU', 'SU')):
            return False, 'Иностранный эмитент'

        # 5. Если всё ок
        return True, 'OK'

    results = df.apply(check_access, axis=1)
    df['unqualified_allowed'] = [r[0] for r in results]
    df['access_reason'] = [r[1] for r in results]

    return df


def _load_bond_volumes(days_back=7):
    """Загружает объёмы торгов (VALUE, NUMTRADES) за последний день."""
    cache_path = 'bond_volumes_cache.csv'
    cache_meta_path = 'bond_volumes_cache.meta'

    if os.path.exists(cache_path) and os.path.exists(cache_meta_path):
        try:
            with open(cache_meta_path, 'r') as f:
                cache_time = datetime.fromisoformat(f.read().strip())
            age_hours = (datetime.now() - cache_time).total_seconds() / 3600
            if age_hours < 6:
                df = pd.read_csv(cache_path)
                print(f'  📦 Объёмы торгов из кэша ({len(df)} шт.)')
                return dict(zip(df['SECID'], df[['VALUE', 'NUMTRADES']].to_dict('records')))
        except Exception:
            pass

    for days in range(0, days_back):
        date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        url = ('https://iss.moex.com/iss/history/engines/stock/markets/bonds/'
               'boards/TQCB/securities.json')
        params = {
            'iss.meta': 'off',
            'iss.only': 'history',
            'date': date,
            'limit': 100,
        }
        all_rows = _load_iss_data(url, params)
        if not all_rows:
            continue

        result = {}
        for row in all_rows:
            if not isinstance(row, dict):
                continue
            secid = row.get('SECID')
            if not secid:
                continue
            try:
                value = float(row.get('VALUE') or 0)
            except (ValueError, TypeError):
                value = 0
            try:
                numtrades = int(row.get('NUMTRADES') or 0)
            except (ValueError, TypeError):
                numtrades = 0
            result[secid] = {'VALUE': value, 'NUMTRADES': numtrades}

        if result:
            print(f'  📊 Объёмы торгов за {date}: {len(result)} шт.')
            try:
                cache_df = pd.DataFrame([
                    {'SECID': k, 'VALUE': v['VALUE'], 'NUMTRADES': v['NUMTRADES']}
                    for k, v in result.items()
                ])
                cache_df.to_csv(cache_path, index=False)
                with open(cache_meta_path, 'w') as f:
                    f.write(datetime.now().isoformat())
            except Exception:
                pass
            return result

    print('  ⚠️ Не удалось загрузить объёмы торгов.')
    return {}


def get_bonds_data(session, board='TQCB', force_refresh=False,
                   cache_ttl_hours=24, max_bonds=5000,
                   min_daily_volume=5_000_000,
                   min_num_trades=10,
                   min_price_pct=80.0,
                   max_price_pct=120.0,
                   max_yield=50.0,
                   only_trusted=True,
                   only_unqualified_allowed=True):
    """
    Загружает облигации с MOEX и проставляет флаг доступности
    для неквалифицированных инвесторов.
    """
    cache_path = 'bonds_cache.csv'
    cache_meta_path = 'bonds_cache.meta'

    if not force_refresh and os.path.exists(cache_path) and os.path.exists(cache_meta_path):
        try:
            with open(cache_meta_path, 'r') as f:
                cache_time = datetime.fromisoformat(f.read().strip())
            age_hours = (datetime.now() - cache_time).total_seconds() / 3600
            if age_hours < cache_ttl_hours:
                df = pd.read_csv(cache_path)
                for col in ['MATDATE', 'OFFERDATE', 'NEXTCOUPON']:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                print(f'  📦 Облигации из кэша ({len(df)} шт., возраст {age_hours:.1f} ч.)')
                return df
        except Exception as e:
            print(f'  Кэш повреждён: {e}')

    print(f'  🌐 Загрузка облигаций с MOEX...')
    url = f'https://iss.moex.com/iss/engines/stock/markets/bonds/boards/{board}/securities.json'
    params = {'iss.meta': 'off', 'iss.only': 'securities,marketdata'}

    data_raw = None
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=HEADERS,
                                timeout=30, verify=False)
            resp.raise_for_status()
            data_raw = resp.json()
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
                continue
            print(f'  ❌ Ошибка загрузки: {e}')
            data_raw = None

    if data_raw is None:
        return pd.DataFrame()

    sec_block = data_raw.get('securities')
    if not isinstance(sec_block, dict):
        print('  ❌ Нет блока securities.')
        return pd.DataFrame()

    sec_cols = sec_block.get('columns', [])
    sec_rows = sec_block.get('data', [])
    if not sec_rows or not sec_cols:
        print('  ❌ Нет данных в securities.')
        return pd.DataFrame()

    print(f'  ✅ Получено бумаг: {len(sec_rows)}')
    df = pd.DataFrame(sec_rows, columns=sec_cols)

    # marketdata
    md_block = data_raw.get('marketdata')
    if isinstance(md_block, dict):
        md_cols = md_block.get('columns', [])
        md_rows = md_block.get('data', [])
        if md_rows and md_cols:
            md_df = pd.DataFrame(md_rows, columns=md_cols)
            md_keep = ['SECID'] + [c for c in ['VALTODAY', 'VOLTODAY', 'NUMTRADES'] if c in md_df.columns]
            md_df = md_df[md_keep]
            df = df.merge(md_df, on='SECID', how='left')

    # Дедупликация
    if 'SECID' in df.columns:
        before = len(df)
        df = df.drop_duplicates(subset=['SECID'], keep='first').reset_index(drop=True)
        if before != len(df):
            print(f'  🔄 Удалено дубликатов: {before - len(df)}')

    # Переименование
    df = df.rename(columns={
        'YIELDATPREVWAPRICE': 'YIELD',
        'PREVPRICE': 'PRICE',
        'VALTODAY': 'DAILY_VOLUME',
        'NUMTRADES': 'NUM_TRADES',
    })

    # Числа
    for col in ['YIELD', 'PRICE', 'DAILY_VOLUME', 'NUM_TRADES',
                'COUPONVALUE', 'ACCRUEDINT', 'LOTVALUE', 'FACEVALUE',
                'COUPONPERCENT', 'COUPONPERIOD']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Даты
    for col in ['MATDATE', 'OFFERDATE', 'NEXTCOUPON']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    if 'YIELD' not in df.columns:
        return pd.DataFrame()

    # Фильтры
    df = df[df['YIELD'].notna() & (df['YIELD'] > 0)]
    before = len(df)
    df = df[df['YIELD'] <= max_yield]
    if before - len(df) > 0:
        print(f'  🗑️ Удалено по YTM (>{max_yield}%): {before - len(df)}')

    if 'PRICE' in df.columns:
        before = len(df)
        df = df[(df['PRICE'].notna()) & (df['PRICE'] >= min_price_pct) & (df['PRICE'] <= max_price_pct)]
        if before - len(df) > 0:
            print(f'  🗑️ Удалено по цене ({min_price_pct}–{max_price_pct}%): {before - len(df)}')

    if 'SECID' in df.columns:
        df = df[df['SECID'].str.startswith(('RU', 'SU'), na=False)].copy()
        df['is_russian'] = True

    volumes = _load_bond_volumes()
    if volumes:
        df['DAILY_VOLUME'] = df['SECID'].map(lambda s: volumes.get(s, {}).get('VALUE', 0))
        df['NUM_TRADES'] = df['SECID'].map(lambda s: volumes.get(s, {}).get('NUMTRADES', 0))
        before = len(df)
        df = df[df['DAILY_VOLUME'] >= min_daily_volume]
        if before - len(df) > 0:
            print(f'  🗑️ Удалено неликвидных (< {min_daily_volume:,.0f} ₽): {before - len(df)}')
        before = len(df)
        df = df[df['NUM_TRADES'] >= min_num_trades]
        if before - len(df) > 0:
            print(f'  🗑️ Удалено по числу сделок (< {min_num_trades}): {before - len(df)}')
    else:
        df['DAILY_VOLUME'] = None
        df['NUM_TRADES'] = None

    # Ручной фильтр надёжных
    if only_trusted and 'SHORTNAME' in df.columns:
        before = len(df)
        def is_trusted(sn):
            if pd.isna(sn): return False
            sn_lower = str(sn).lower()
            return any(kw.lower() in sn_lower for kw in TRUSTED_KEYWORDS)
        df = df[df['SHORTNAME'].apply(is_trusted)]
        if before - len(df) > 0:
            print(f'  🛡️ Удалено ненадёжных (не в списке): {before - len(df)}')
        df['CREDIT_RATING'] = 'trusted'
    else:
        df['CREDIT_RATING'] = None

    # Дюрация
    if 'MATDATE' in df.columns:
        today = pd.Timestamp.now()
        df['DURATION'] = (df['MATDATE'] - today).dt.days
        df.loc[df['DURATION'] < 0, 'DURATION'] = None
        df['DURATION'] = df['DURATION'].fillna(9999)
    else:
        df['DURATION'] = 9999

    # Купон
    if 'COUPONPERCENT' in df.columns:
        df['coupon_rate'] = df['COUPONPERCENT']
    elif 'COUPONVALUE' in df.columns and 'COUPONPERIOD' in df.columns and 'FACEVALUE' in df.columns:
        df['coupon_rate'] = (df['COUPONVALUE'] / df['FACEVALUE'] * (365 / df['COUPONPERIOD']) * 100)
    else:
        df['coupon_rate'] = None

    # === Маркировка доступности ===
    df = _mark_bond_accessibility(df)

    # Фильтр "только доступные"
    if only_unqualified_allowed:
        before = len(df)
        df = df[df['unqualified_allowed'] == True]
        if before - len(df) > 0:
            print(f'  🚫 Удалено недоступных для неквал. инвестора: {before - len(df)}')

    # Оставляем нужные колонки
    display_cols = [
        'SECID', 'SHORTNAME', 'YIELD', 'coupon_rate', 'DURATION',
        'MATDATE', 'OFFERDATE', 'NEXTCOUPON', 'COUPONVALUE', 'ACCRUEDINT',
        'LOTVALUE', 'FACEVALUE', 'PRICE', 'DAILY_VOLUME', 'NUM_TRADES',
        'CREDIT_RATING', 'is_russian', 'unqualified_allowed', 'access_reason'
    ]
    display_cols = [c for c in display_cols if c in df.columns]
    df = df[display_cols]

    df = df.sort_values('YIELD', ascending=False).reset_index(drop=True)
    if len(df) > max_bonds:
        df = df.head(max_bonds)

    try:
        df.to_csv(cache_path, index=False)
        with open(cache_meta_path, 'w') as f:
            f.write(datetime.now().isoformat())
        print(f'  💾 Кэш сохранён ({len(df)} шт.): {cache_path}')
    except Exception as e:
        print(f'  Не удалось сохранить кэш: {e}')

    return df