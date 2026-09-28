# ml_model.py

import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import os
import config
from data_manager import download_full_history, get_stock_history
from analyzer import add_indicators
import ta
import requests

# Признаки (общие для краткосрочных и долгосрочных моделей)
FEATURES = [
    'RSI', 'MACD_diff', 'SMA_dist', 'BB_pos',
    'volatility', 'volume_change', 'ret1', 'ret5'
]

MIN_TRAIN_SAMPLES = 100


# =========================================================
#   КРАТКОСРОЧНЫЕ МОДЕЛИ (5 дней, +1.5%)
# =========================================================

def prepare_features(df):
    """Признаки для краткосрочной модели (5 дней)."""
    df = df.copy()
    df['RSI'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
    macd_indicator = ta.trend.MACD(close=df['close'], window_slow=26, window_fast=12, window_sign=9)
    df['MACD'] = macd_indicator.macd()
    df['MACD_signal'] = macd_indicator.macd_signal()
    df['MACD_diff'] = df['MACD'] - df['MACD_signal']
    df['SMA20'] = ta.trend.SMAIndicator(close=df['close'], window=20).sma_indicator()
    df['SMA_dist'] = (df['close'] - df['SMA20']) / df['SMA20']
    bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['BB_pos'] = (df['close'] - bb.bollinger_lband()) / (bb.bollinger_hband() - bb.bollinger_lband())
    df['ret1'] = df['close'].pct_change(1)
    df['ret5'] = df['close'].pct_change(5)
    df['volatility'] = df['ret1'].rolling(20).std()
    df['volume_change'] = df['volume'].pct_change(5)
    future_close = df['close'].shift(-5)
    df['target'] = ((future_close / df['close']) - 1) > 0.015
    df['target'] = df['target'].astype(int)
    return df.dropna()


def train_model_for_ticker(ticker, years=5):
    """Обучить краткосрочную модель (5 дней) для одного тикера."""
    print(f'Обучение краткосрочной модели для {ticker}...')
    df = download_full_history(ticker, years)
    if df.empty:
        print(f'Нет данных для {ticker}')
        return False
    df = prepare_features(df)
    if len(df) < MIN_TRAIN_SAMPLES:
        print(f'Недостаточно данных для {ticker}: {len(df)} строк.')
        return False

    X = df[FEATURES]
    y = df['target']
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    if len(X_test) == 0 or len(X_train) == 0:
        return False

    # Балансировка классов
    pos_count = int(y_train.sum())
    neg_count = len(y_train) - pos_count
    scale_pos_weight = neg_count / pos_count if pos_count > 0 else 1.0

    model = xgb.XGBClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.01,
        subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1,
        scale_pos_weight=scale_pos_weight,
    )
    model.fit(X_train, y_train)
    acc = accuracy_score(y_test, model.predict(X_test))
    print(f'Accuracy: {acc:.3f}')

    os.makedirs(config.MODELS_DIR, exist_ok=True)
    path = os.path.join(config.MODELS_DIR, f'{ticker}_xgb_model.json')
    model.save_model(path)
    print(f'Модель сохранена: {path}\n')
    return True


def predict_ml(ticker):
    """Краткосрочный прогноз (5 дней)."""
    if not config.ML_ENABLED:
        return None
    model_path = os.path.join(config.MODELS_DIR, f'{ticker}_xgb_model.json')
    if not os.path.exists(model_path):
        return None

    model = xgb.XGBClassifier()
    model.load_model(model_path)

    session = requests.Session()
    df = get_stock_history(session, ticker)
    if df.empty:
        return None

    df = add_indicators(df)
    df['MACD_diff'] = df['MACD'] - df['MACD_signal']
    df['SMA_dist'] = (df['close'] - df['SMA']) / df['SMA']
    df['BB_pos'] = (df['close'] - df['BB_lower']) / (df['BB_upper'] - df['BB_lower'])
    df['ret1'] = df['close'].pct_change(1)
    df['ret5'] = df['close'].pct_change(5)
    df['volatility'] = df['ret1'].rolling(20).std()
    df['volume_change'] = df['volume'].pct_change(5)
    df = df.dropna(subset=FEATURES)
    if df.empty:
        return None

    last = df.iloc[-1]
    X = np.array([last[f] for f in FEATURES]).reshape(1, -1)
    proba = model.predict_proba(X)[0]
    return {
        'probability_up': float(proba[1]),
        'prediction': 'BUY' if proba[1] >= config.ML_THRESHOLD else 'NEUTRAL'
    }


# =========================================================
#   ДОЛГОСРОЧНЫЕ МОДЕЛИ (20 дней, ±10%)
# =========================================================

def prepare_long_features(df):
    """Признаки для долгосрочной модели (20 дней)."""
    df = df.copy()
    df['RSI'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
    macd_indicator = ta.trend.MACD(close=df['close'], window_slow=26, window_fast=12, window_sign=9)
    df['MACD'] = macd_indicator.macd()
    df['MACD_signal'] = macd_indicator.macd_signal()
    df['MACD_diff'] = df['MACD'] - df['MACD_signal']
    df['SMA20'] = ta.trend.SMAIndicator(close=df['close'], window=20).sma_indicator()
    df['SMA_dist'] = (df['close'] - df['SMA20']) / df['SMA20']
    bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['BB_pos'] = (df['close'] - bb.bollinger_lband()) / (bb.bollinger_hband() - bb.bollinger_lband())
    df['ret1'] = df['close'].pct_change(1)
    df['ret5'] = df['close'].pct_change(5)
    df['volatility'] = df['ret1'].rolling(20).std()
    df['volume_change'] = df['volume'].pct_change(5)

    horizon = config.ML_LONG_HORIZON
    future_close = df['close'].shift(-horizon)

    df['target_buy'] = ((future_close / df['close']) - 1) >= config.ML_LONG_BUY_THRESHOLD
    df['target_sell'] = ((future_close / df['close']) - 1) <= config.ML_LONG_SELL_THRESHOLD
    df['target_buy'] = df['target_buy'].astype(int)
    df['target_sell'] = df['target_sell'].astype(int)

    return df.dropna(subset=FEATURES + ['target_buy', 'target_sell'])


def train_long_models_for_ticker(ticker, years=5):
    """Обучить 2 долгосрочные модели (BUY + SELL) для одного тикера."""
    print(f'Обучение долгосрочных моделей для {ticker}...')
    df = download_full_history(ticker, years)
    if df.empty:
        print(f'  Нет данных для {ticker}')
        return False

    df = prepare_long_features(df)
    if len(df) < MIN_TRAIN_SAMPLES:
        print(f'  Мало данных: {len(df)} строк')
        return False

    os.makedirs(config.ML_LONG_DIR, exist_ok=True)

    results = {}
    for target_col, model_suffix, threshold in [
        ('target_buy', 'buy', config.ML_LONG_BUY_THRESHOLD),
        ('target_sell', 'sell', config.ML_LONG_SELL_THRESHOLD),
    ]:
        y = df[target_col]

        # Проверяем дисбаланс классов
        pos_count = int(y.sum())
        neg_count = len(y) - pos_count
        if pos_count < 30:
            print(f'  {ticker} {model_suffix}: мало позитивных примеров ({pos_count}), пропускаем.')
            continue

        # ⚠️ Ключевой параметр для дисбаланса
        scale_pos_weight = neg_count / pos_count

        X = df[FEATURES]
        split = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split], X.iloc[split:]
        y_train, y_test = y.iloc[:split], y.iloc[split:]

        if len(X_test) == 0:
            continue

        # Если в тесте нет положительных — расширяем окно
        if y_test.sum() == 0:
            split = max(30, int(len(X) * 0.7))
            X_train, X_test = X.iloc[:split], X.iloc[split:]
            y_train, y_test = y.iloc[:split], y.iloc[split:]

        model = xgb.XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.01,
            subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1,
            scale_pos_weight=scale_pos_weight,  # ← балансировка
        )
        model.fit(X_train, y_train)

        acc_train = accuracy_score(y_train, model.predict(X_train))
        acc_test = accuracy_score(y_test, model.predict(X_test))
        proba_mean = float(model.predict_proba(X_test)[:, 1].mean())

        results[model_suffix] = {
            'acc_train': acc_train,
            'acc_test': acc_test,
            'proba_mean': proba_mean,
            'pos_count': pos_count,
        }

        path = os.path.join(config.ML_LONG_DIR, f'{ticker}_{model_suffix}_model.json')
        model.save_model(path)

    if results:
        for suffix, r in results.items():
            print(f'  {ticker} {suffix}: acc_train={r["acc_train"]:.3f} | '
                  f'acc_test={r["acc_test"]:.3f} | proba_mean={r["proba_mean"]:.3f} | '
                  f'pos={r["pos_count"]}')
        return True
    else:
        print(f'  {ticker}: модели не обучены')
        return False


def predict_long_ml(ticker):
    """Долгосрочный прогноз (20 дней) — вероятность роста и падения."""
    if not config.ML_LONG_ENABLED:
        return None

    buy_path = os.path.join(config.ML_LONG_DIR, f'{ticker}_buy_model.json')
    sell_path = os.path.join(config.ML_LONG_DIR, f'{ticker}_sell_model.json')

    if not os.path.exists(buy_path) and not os.path.exists(sell_path):
        return None

    session = requests.Session()
    df = get_stock_history(session, ticker)
    if df.empty:
        return None

    df = add_indicators(df)
    df['MACD_diff'] = df['MACD'] - df['MACD_signal']
    df['SMA_dist'] = (df['close'] - df['SMA']) / df['SMA']
    df['BB_pos'] = (df['close'] - df['BB_lower']) / (df['BB_upper'] - df['BB_lower'])
    df['ret1'] = df['close'].pct_change(1)
    df['ret5'] = df['close'].pct_change(5)
    df['volatility'] = df['ret1'].rolling(20).std()
    df['volume_change'] = df['volume'].pct_change(5)
    df = df.dropna(subset=FEATURES)
    if df.empty:
        return None

    last = df.iloc[-1]
    X = np.array([last[f] for f in FEATURES]).reshape(1, -1)

    result = {}
    if os.path.exists(buy_path):
        model = xgb.XGBClassifier()
        model.load_model(buy_path)
        result['long_buy'] = float(model.predict_proba(X)[0][1])

    if os.path.exists(sell_path):
        model = xgb.XGBClassifier()
        model.load_model(sell_path)
        result['long_sell'] = float(model.predict_proba(X)[0][1])

    return result if result else None


if __name__ == '__main__':
    import sys
    tkr = sys.argv[1] if len(sys.argv) > 1 else 'SBER'
    train_model_for_ticker(tkr, years=5)
    train_long_models_for_ticker(tkr, years=5)