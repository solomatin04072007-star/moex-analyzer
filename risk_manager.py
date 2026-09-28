# risk_manager.py

import pandas as pd
import ta
import config

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Средний истинный диапазон (ATR) — мера волатильности."""
    atr = ta.volatility.AverageTrueRange(
        high=df['high'], low=df['low'], close=df['close'], window=period
    )
    return atr.average_true_range()

def calculate_position_size(price: float, atr: float, portfolio_size: float,
                            risk_per_trade: float = 0.02, stop_atr_mult: float = 2.0) -> dict:
    """
    Рассчитывает размер позиции по методу ATR.
    
    price            — текущая цена акции
    atr              — значение ATR
    portfolio_size   — размер портфеля в рублях
    risk_per_trade   — доля портфеля, которой можно рискнуть (по умолчанию 2%)
    stop_atr_mult    — на сколько ATR ставим стоп-лосс (по умолчанию 2 ATR)
    """
    if atr <= 0 or price <= 0 or portfolio_size <= 0:
        return {'shares': 0, 'stop_loss': 0, 'risk_rub': 0, 'position_rub': 0}

    # Риск в рублях
    risk_rub = portfolio_size * risk_per_trade
    # Размер стоп-лосса в рублях за одну акцию
    stop_distance = atr * stop_atr_mult
    # Сколько акций купить, чтобы риск не превышал risk_rub
    shares = int(risk_rub / stop_distance) if stop_distance > 0 else 0
    # Стоп-лосс — цена на 2 ATR ниже текущей
    stop_loss = price - stop_distance
    position_rub = shares * price

    return {
        'shares': shares,
        'stop_loss': round(stop_loss, 2),
        'stop_distance': round(stop_distance, 2),
        'risk_rub': round(risk_rub, 2),
        'position_rub': round(position_rub, 2),
        'atr': round(atr, 2),
        'risk_percent': risk_per_trade * 100
    }