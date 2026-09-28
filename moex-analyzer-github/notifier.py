# notifier.py

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import requests
import schedule
import time
from datetime import datetime
import pandas as pd
import config
from data_manager import get_all_stocks_data, get_bonds_data
from ml_model import predict_ml, predict_long_ml
from risk_manager import calculate_position_size
from market_context import get_market_context
import requests as req


# =========================================================
#   EMAIL
# =========================================================

def send_email(subject, body):
    """Отправка письма через SMTP."""
    if not config.EMAIL_ENABLED:
        return
    try:
        msg = MIMEMultipart()
        msg['From'] = config.SENDER_EMAIL
        msg['To'] = config.RECEIVER_EMAIL
        msg['Subject'] = Header(subject, 'utf-8')
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        with smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.login(config.SENDER_EMAIL, config.SENDER_PASSWORD)
            server.send_message(msg)

        print(f'[{datetime.now()}] ✅ Email отправлен: {subject}')
    except Exception as e:
        print(f'[{datetime.now()}] ❌ Ошибка Email: {e}')


# =========================================================
#   NTFY
# =========================================================

def send_ntfy(subject, body):
    """Отправка push через Ntfy. Заголовок должен быть ASCII."""
    if not config.NTFY_ENABLED:
        return
    try:
        url = f'{config.NTFY_URL}/{config.NTFY_TOPIC}'
        safe_title = subject.encode('ascii', 'ignore').decode('ascii') or 'MOEX Signal'
        headers = {
            'Title': safe_title,
            'Priority': 'default',
            'Tags': 'chart_with_upwards_trend',
        }
        resp = requests.post(url, data=body.encode('utf-8'),
                             headers=headers, timeout=10)
        if resp.status_code == 200:
            print(f'[{datetime.now()}] ✅ Ntfy отправлен')
        else:
            print(f'[{datetime.now()}] ⚠️ Ntfy {resp.status_code}: {resp.text[:200]}')
    except Exception as e:
        print(f'[{datetime.now()}] ❌ Ошибка Ntfy: {e}')


def notify(subject, body):
    """Отправка во все включённые каналы."""
    send_email(subject, body)
    send_ntfy(subject, body)


# =========================================================
#   ЕЖЕДНЕВНАЯ СВОДКА
# =========================================================

def job():
    print(f'\n{"=" * 50}')
    print(f'[{datetime.now()}] Ежедневная проверка...')

    today = datetime.now().strftime('%d.%m.%Y')
    messages = []

    # --- КОНТЕКСТ РЫНКА (IMOEX) ---
    try:
        market_ctx = get_market_context()
        if market_ctx:
            messages.append(market_ctx)
    except Exception as e:
        print(f'Ошибка прогноза рынка: {e}')

    # --- АКЦИИ ---
    print('Загрузка данных по акциям...')
    stock_results = get_all_stocks_data(config.STOCK_TICKERS)

    strong = []
    ml_signals = []
    ml_long_signals = []

    for ticker, data in stock_results.items():
        s = data['signal']

        # Сильные сигналы от правил
        if s['type'] in ('BUY', 'SELL'):
            line = f"{ticker}: {s['message']}"

            if s['type'] == 'BUY' and data.get('atr'):
                try:
                    pos = calculate_position_size(
                        data['last_close'], data['atr'],
                        config.PORTFOLIO_SIZE, config.RISK_PER_TRADE, config.STOP_ATR_MULT
                    )
                    if pos['shares'] > 0:
                        line += (f"\n    └ Объём: {pos['shares']} шт. | "
                                 f"Стоп: {pos['stop_loss']} ₽ | Риск: {pos['risk_rub']} ₽")
                except Exception:
                    pass

            strong.append(line)

        # Краткосрочный ML
        if config.ML_ENABLED:
            try:
                ml = predict_ml(ticker)
                if ml and ml.get('prediction') == 'BUY':
                    ml_signals.append(
                        f"  🤖 {ticker}: ML BUY 5д (вер. {ml['probability_up']:.1%})"
                    )
                    if s['type'] == 'BUY':
                        strong[-1] += f" + ML ({ml['probability_up']:.1%})"
            except Exception:
                pass

        # Долгосрочный ML
        if config.ML_ENABLED and getattr(config, 'ML_LONG_ENABLED', False):
            try:
                long_ml = predict_long_ml(ticker)
                if long_ml:
                    if long_ml.get('long_buy', 0) >= config.ML_LONG_MIN_PROB:
                        ml_long_signals.append(
                            f"  🔭 {ticker}: LONG BUY (вер. {long_ml['long_buy']:.1%}, "
                            f"цель +{int(config.ML_LONG_BUY_THRESHOLD*100)}% за мес.)"
                        )
                    if long_ml.get('long_sell', 0) >= config.ML_LONG_MIN_PROB:
                        ml_long_signals.append(
                            f"  🔻 {ticker}: LONG SELL (вер. {long_ml['long_sell']:.1%}, "
                            f"цель {int(config.ML_LONG_SELL_THRESHOLD*100)}% за мес.)"
                        )
            except Exception:
                pass

    if strong:
        messages.append('\n🔔 СИЛЬНЫЕ СИГНАЛЫ (акции):')
        messages.extend(strong)

    if ml_signals and not strong:
        messages.append('\n🤖 КРАТКОСРОЧНЫЕ ML-СИГНАЛЫ (5 дней):')
        messages.extend(ml_signals[:15])

    if ml_long_signals:
        messages.append('\n🔭 ДОЛГОСРОЧНЫЕ ML-СИГНАЛЫ (20 дней):')
        messages.extend(ml_long_signals[:10])

    if not strong and not ml_signals and not ml_long_signals:
        messages.append('\nАкции: по всем тикерам нейтрально.')

    # --- ПОРТФЕЛЬ ---
    print('Загрузка портфеля...')
    try:
        from portfolio_manager import (
            calculate_positions, get_current_price,
            format_positions_for_notifier
        )

        positions = calculate_positions(update_prices=False)

        if positions:
            active = {t: p for t, p in positions.items() if p['quantity'] > 0}

            if active:
                # Обновляем цены и пересчитываем P&L для активных позиций
                for t in active.keys():
                    price = get_current_price(t)
                    if price:
                        active[t]['current_price'] = price
                        active[t]['unrealized_pnl'] = active[t]['quantity'] * (
                            price - active[t]['avg_buy_price']
                        )
                        active[t]['current_value'] = active[t]['quantity'] * price
                        cost_basis = active[t]['quantity'] * active[t]['avg_buy_price']
                        if cost_basis > 0:
                            active[t]['pnl_pct'] = round(
                                (active[t]['unrealized_pnl'] / cost_basis) * 100, 2
                            )

                pos_lines = format_positions_for_notifier(positions)

                if pos_lines:
                    total_val = sum(p['current_value'] for p in active.values())
                    total_cost = sum(p['cost_basis'] for p in active.values())
                    total_pnl = sum(p['unrealized_pnl'] for p in active.values())
                    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

                    emoji = '📈' if total_pnl > 0 else ('📉' if total_pnl < 0 else '➖')
                    messages.append(
                        f'\n💼 МОЙ ПОРТФЕЛЬ ({len(active)} позиций)\n'
                        f'  {emoji} Стоимость: {total_val:,.0f} ₽ | '
                        f'P&L: {total_pnl:+,.0f} ₽ ({total_pnl_pct:+.1f}%)'
                    )
                    messages.extend(pos_lines)
    except Exception as e:
        print(f'Ошибка портфеля: {e}')

    # --- ОБЛИГАЦИИ ---
    print('Загрузка данных по облигациям...')
    try:
        session = req.Session()
        bonds_df = get_bonds_data(session)

        if bonds_df is not None and not bonds_df.empty and 'YIELD' in bonds_df.columns:
            top_bonds = bonds_df.sort_values('YIELD', ascending=False).head(
                getattr(config, 'BONDS_NOTIFIER_TOP_N', 5)
            )
            messages.append(f'\n💰 ТОП-{len(top_bonds)} ОБЛИГАЦИЙ ПО YTM:')
            for _, row in top_bonds.iterrows():
                mat_date = ''
                if pd.notna(row.get('MATDATE')):
                    mat_date = row['MATDATE'].strftime('%d.%m.%Y')

                line = f"  • {row['SECID']} {row['SHORTNAME']}: YTM={row['YIELD']:.2f}%"
                if pd.notna(row.get('DURATION')) and row['DURATION'] < 9999:
                    line += f", дюрация={row['DURATION']:.0f} дн."
                if mat_date:
                    line += f", погашение {mat_date}"
                messages.append(line)
        else:
            messages.append('\n💰 Облигации: не удалось загрузить данные.')
    except Exception as e:
        print(f'Ошибка загрузки облигаций: {e}')
        messages.append(f'\n💰 Облигации: ошибка загрузки ({e}).')

    # --- ИТОГ ---
    body = f'📊 СВОДКА НА {today}\n' + '\n'.join(messages)
    body += '\n\n---\n⚠️ Не является инвестиционной рекомендацией.'

    print(body)
    notify(f'MOEX Анализатор — {today}', body)
    print(f'[{datetime.now()}] Проверка завершена.\n')


# =========================================================
#   ЗАПУСК
# =========================================================

if __name__ == '__main__':
    print('MOEX AI Анализатор запущен.')
    print(f'Проверка ежедневно в {config.CHECK_HOUR}:{config.CHECK_MINUTE:02d} МСК')
    print(f'Email: {"вкл" if config.EMAIL_ENABLED else "выкл"} | '
          f'Ntfy: {"вкл" if config.NTFY_ENABLED else "выкл"}')

    # Первый запуск сразу (для проверки)
    job()

    # Планировщик
    schedule.every().day.at(f'{config.CHECK_HOUR}:{config.CHECK_MINUTE:02d}').do(job)
    while True:
        schedule.run_pending()
        time.sleep(60)