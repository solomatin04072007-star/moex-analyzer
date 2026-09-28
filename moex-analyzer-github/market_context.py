# market_context.py

import requests
import pandas as pd
import numpy as np
import xgboost as xgb
import os
import time
from datetime import datetime, timedelta
import config
from analyzer import add_indicators
import ta
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Connection': 'keep-alive',
}

INDEX_MODEL_PATH = os.path.join(config.MODELS_DIR, 'IMOEX_xgb_model.json')

FEATURES = ['RSI', 'MACD_diff', 'SMA_dist', 'BB_pos',
            'volatility', 'volume_change', 'ret1', 'ret5']


def _try_url(url, params, retries=3):
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=HEADERS,
                                timeout=30, verify=False)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1.5)
                continue
            print(f'  Ошибка запроса ({attempt + 1}/{retries}): {e}')
    return None


def _load_imoex(years=5):
    """Загрузка истории индекса IMOEX."""
    start_date = (datetime.now() - timedelta(days=years * 365)).strftime('%Y-%m-%d')
    url = ('https://iss.moex.com/iss/history/engines/stock/markets/index/'
           'boards/SNDX/securities/IMOEX.json')

    all_rows = []
    start = 0

    while True:
        params = {
            'iss.json': 'extended',
            'limit': 100,
            'from': start_date,
            'start': start,
        }
        data = _try_url(url, params)
        if data is None:
            break

        if not isinstance(data, list) or len(data) < 2:
            break

        hist = data[1].get('history')
        if not isinstance(hist, list) or len(hist) < 2:
            break

        rows = hist[1]
        if not isinstance(rows, list) or not rows:
            break

        all_rows.extend(rows)
        if len(rows) < 100:
            break
        start += len(rows)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)

    # ⚠️ Оставляем ТОЛЬКО нужные колонки — убираем мусор с NaN
    keep_cols = ['TRADEDATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME']
    keep_cols = [c for c in keep_cols if c in df.columns]
    df = df[keep_cols]

    df = df.rename(columns={
        'TRADEDATE': 'date', 'OPEN': 'open', 'HIGH': 'high',
        'LOW': 'low', 'CLOSE': 'close', 'VOLUME': 'volume'
    })

    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()

    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    if 'volume' not in df.columns or df['volume'].isna().all():
        df['volume'] = 1

    # ⚠️ dropna только по нужным колонкам
    df = df.dropna(subset=['open', 'high', 'low', 'close'])
    return df


def _prepare_index_features(df):
    df = df.copy()
    df['RSI'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()

    macd = ta.trend.MACD(close=df['close'], window_slow=26,
                          window_fast=12, window_sign=9)
    df['MACD'] = macd.macd()
    df['MACD_signal'] = macd.macd_signal()
    df['MACD_diff'] = df['MACD'] - df['MACD_signal']

    df['SMA20'] = ta.trend.SMAIndicator(close=df['close'], window=20).sma_indicator()
    df['SMA_dist'] = (df['close'] - df['SMA20']) / df['SMA20']

    bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    upper = bb.bollinger_hband()
    lower = bb.bollinger_lband()
    df['BB_pos'] = (df['close'] - lower) / (upper - lower)

    df['ret1'] = df['close'].pct_change(1)
    df['ret5'] = df['close'].pct_change(5)
    df['volatility'] = df['ret1'].rolling(20).std()
    df['volume_change'] = df['volume'].pct_change(5).fillna(0)

    future_close = df['close'].shift(-5)
    df['target'] = ((future_close / df['close']) - 1) > 0.015
    df['target'] = df['target'].astype(int)

    # ⚠️ dropna только по колонкам признаков (не по всем!)
    return df.dropna(subset=FEATURES + ['target'])


def train_index_model(years=5):
    print('Обучение модели IMOEX...')
    df = _load_imoex(years)

    if df.empty:
        print('❌ Не удалось загрузить данные IMOEX.')
        return False

    print(f'Загружено {len(df)} свечей IMOEX.')
    df = _prepare_index_features(df)

    if len(df) < 200:
        print(f'Мало данных после подготовки признаков: {len(df)}')
        return False

    print(f'Признаков подготовлено: {len(df)} строк.')

    X = df[FEATURES]
    y = df['target']
    split = int(len(X) * 0.8)
    X_tr, X_te = X.iloc[:split], X.iloc[split:]
    y_tr, y_te = y.iloc[:split], y.iloc[split:]

    if len(X_te) == 0:
        print('Пустая тестовая выборка.')
        return False

    model = xgb.XGBClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.01,
        subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1
    )
    model.fit(X_tr, y_tr)

    from sklearn.metrics import accuracy_score
    acc = accuracy_score(y_te, model.predict(X_te))
    print(f'IMOEX Accuracy: {acc:.3f}')

    os.makedirs(config.MODELS_DIR, exist_ok=True)
    model.save_model(INDEX_MODEL_PATH)
    print(f'✅ Модель IMOEX сохранена: {INDEX_MODEL_PATH}')
    return True


def get_market_context():
    if not os.path.exists(INDEX_MODEL_PATH):
        return None

    model = xgb.XGBClassifier()
    model.load_model(INDEX_MODEL_PATH)

    df = _load_imoex(years=1)
    if df.empty or len(df) < 30:
        return None

    df = add_indicators(df)
    df['MACD_diff'] = df['MACD'] - df['MACD_signal']
    df['SMA_dist'] = (df['close'] - df['SMA']) / df['SMA']
    df['BB_pos'] = (df['close'] - df['BB_lower']) / (df['BB_upper'] - df['BB_lower'])
    df['ret1'] = df['close'].pct_change(1)
    df['ret5'] = df['close'].pct_change(5)
    df['volatility'] = df['ret1'].rolling(20).std()
    df['volume_change'] = df['volume'].pct_change(5).fillna(0)
    df = df.dropna(subset=FEATURES)

    if df.empty:
        return None

    last = df.iloc[-1]
    X = np.array([last[f] for f in FEATURES]).reshape(1, -1)
    proba = model.predict_proba(X)[0][1]

    if proba >= 0.65:
        sentiment = 'роста'
        emoji = '📈'
    elif proba <= 0.35:
        sentiment = 'падения'
        emoji = '📉'
    else:
        sentiment = 'нейтральный'
        emoji = '➡️'

    return f"{emoji} Прогноз рынка (IMOEX): вероятность {sentiment} — {proba:.1%}"


if __name__ == '__main__':
    ok = train_index_model(years=5)
    if ok:
        print(get_market_context())