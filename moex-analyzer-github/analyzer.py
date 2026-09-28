# analyzer.py

import pandas as pd
import ta
import config


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['RSI'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
    macd_indicator = ta.trend.MACD(
        close=df['close'],
        window_slow=config.MACD_SLOW,
        window_fast=config.MACD_FAST,
        window_sign=config.MACD_SIGNAL
    )
    df['MACD'] = macd_indicator.macd()
    df['MACD_signal'] = macd_indicator.macd_signal()
    df['SMA'] = ta.trend.SMAIndicator(close=df['close'], window=config.SMA_PERIOD).sma_indicator()
    bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['BB_upper'] = bb.bollinger_hband()
    df['BB_lower'] = bb.bollinger_lband()
    df['BB_middle'] = bb.bollinger_mavg()
    df['ATR'] = ta.volatility.AverageTrueRange(
        high=df['high'], low=df['low'], close=df['close'], window=14
    ).average_true_range()
    return df


def get_last_signal(df: pd.DataFrame) -> dict:
    last = df.iloc[-1]
    rsi = last['RSI']
    macd = last['MACD']
    macd_signal = last['MACD_signal']
    close = last['close']
    sma = last['SMA']
    signal_type = 'NEUTRAL'
    message = 'Нейтрально. Нет чётких сигналов.'

    if rsi < config.RSI_OVERSOLD and macd > macd_signal and close > sma:
        signal_type = 'BUY'
        message = (f'🟢 ПОКУПКА: RSI={rsi:.1f} (перепроданность), '
                   f'MACD бычий (>{macd_signal:.4f}), цена выше SMA{config.SMA_PERIOD}')
    elif rsi > config.RSI_OVERBOUGHT and macd < macd_signal and close < sma:
        signal_type = 'SELL'
        message = (f'🔴 ПРОДАЖА: RSI={rsi:.1f} (перекупленность), '
                   f'MACD медвежий (<{macd_signal:.4f}), цена ниже SMA{config.SMA_PERIOD}')
    elif rsi < config.RSI_OVERSOLD:
        signal_type = 'WATCH_BUY'
        message = f'🟡 Перепроданность (RSI={rsi:.1f}), но MACD/SMA не подтверждают.'
    elif rsi > config.RSI_OVERBOUGHT:
        signal_type = 'WATCH_SELL'
        message = f'🟡 Перекупленность (RSI={rsi:.1f}), но MACD/SMA не подтверждают.'

    return {
        'type': signal_type,
        'message': message,
        'rsi': float(rsi),
        'macd': float(macd),
        'macd_signal': float(macd_signal),
        'close': float(close),
        'sma': float(sma) if pd.notna(sma) else None
    }


def scan_bonds(df_bonds):
    if df_bonds.empty or 'YIELD' not in df_bonds.columns or 'DURATION' not in df_bonds.columns:
        return pd.DataFrame()
    mask = (
        (df_bonds['YIELD'] >= config.MIN_YIELD) &
        (df_bonds['DURATION'] <= config.MAX_DURATION) &
        (df_bonds['YIELD'] > 0)
    )
    result = df_bonds[mask].sort_values('YIELD', ascending=False)
    cols = ['SECID', 'SHORTNAME', 'YIELD', 'DURATION', 'MATDATE', 'COUPONVALUE', 'ACCRUEDINT']
    return result[[c for c in cols if c in result.columns]]