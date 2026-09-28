# backtest.py

import backtrader as bt
import pandas as pd
import requests
from data_manager import download_full_history


class SignalStrategy(bt.Strategy):
    params = (('stop_atr_mult', 2.0), ('risk_per_trade', 0.02))

    def __init__(self):
        self.atr = bt.indicators.ATR(self.data, period=14)
        self.rsi = bt.indicators.RSI(self.data.close, period=14)
        macd = bt.indicators.MACD(self.data.close, period_me1=12, period_me2=26, period_signal=9)
        self.macd = macd.macd
        self.macd_signal = macd.signal
        self.sma = bt.indicators.SMA(self.data.close, period=20)
        self.order = None

    def next(self):
        # Если уже есть активный ордер — ждём его исполнения
        if self.order:
            return

        # Более мягкое условие входа: RSI < 35 + MACD бычий
        if (self.rsi[0] < 35 and self.macd[0] > self.macd_signal[0]
                and not self.position):
            price = self.data.close[0]
            atr = self.atr[0]
            risk_rub = self.broker.getvalue() * self.p.risk_per_trade
            shares = int(risk_rub / (atr * self.p.stop_atr_mult)) if atr > 0 else 0
            if shares > 0:
                self.order = self.buy(size=shares)

        # Выход: RSI > 65 или MACD стал медвежьим
        elif ((self.rsi[0] > 65 or self.macd[0] < self.macd_signal[0])
              and self.position):
            self.order = self.close()

    def notify_order(self, order):
        if order.status in [order.Completed]:
            self.order = None


def run_backtest(ticker, years=5, start_cash=500000):
    df = download_full_history(ticker, years)
    if df.empty or len(df) < 100:
        return None

    cerebro = bt.Cerebro()
    cerebro.addstrategy(SignalStrategy)
    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data)
    cerebro.broker.setcash(start_cash)
    cerebro.broker.setcommission(commission=0.0005)

    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

    start_value = cerebro.broker.getvalue()
    results = cerebro.run()
    end_value = cerebro.broker.getvalue()

    strat = results[0]
    sharpe = strat.analyzers.sharpe.get_analysis()
    dd = strat.analyzers.drawdown.get_analysis()
    trades = strat.analyzers.trades.get_analysis()

    return {
        'ticker': ticker,
        'start_value': start_value,
        'end_value': end_value,
        'total_return_percent': (end_value / start_value - 1) * 100,
        'sharpe': sharpe.get('sharperatio') or 0,
        'max_drawdown_percent': dd.get('max', {}).get('drawdown', 0),
        'total_trades': trades.get('total', {}).get('total', 0),
        'win_rate': (trades.get('won', {}).get('total', 0) /
                     max(trades.get('total', {}).get('total', 1), 1) * 100)
    }