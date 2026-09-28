# app.py

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import requests
from datetime import datetime
import config
from data_manager import (
    get_stock_history, get_bonds_data, get_all_tickers,
    get_all_stocks_data, get_ticker_sectors
)
from analyzer import add_indicators, get_last_signal, scan_bonds
from ml_model import (
    predict_ml, predict_long_ml,
    train_model_for_ticker, train_long_models_for_ticker
)
from risk_manager import calculate_position_size
from market_context import get_market_context, train_index_model

# =========================================================
#   НАСТРОЙКА СТРАНИЦЫ
# =========================================================

st.set_page_config(
    page_title='MOEX Анализатор',
    page_icon='📈',
    layout='wide',
    initial_sidebar_state='expanded'
)

# =========================================================
#   КАСТОМНЫЙ CSS — УЛУЧШЕННЫЙ ДИЗАЙН
# =========================================================

st.markdown("""
<style>
    /* ---------- Общий фон и шрифты ---------- */
    .main {
        background: linear-gradient(135deg, #0e1117 0%, #1a1f2e 100%);
    }
    
    /* Убираем "Made with Streamlit" */
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    
    /* ---------- Заголовок с градиентом ---------- */
    .main-title {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(90deg, #00d4ff 0%, #7b2ff7 50%, #ff2d95 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.2rem;
        letter-spacing: -1px;
    }
    
    .main-subtitle {
        color: #8892b0;
        font-size: 0.95rem;
        margin-bottom: 2rem;
        font-weight: 400;
    }
    
    /* ---------- Секции с заголовками ---------- */
    .section-title {
        font-size: 1.4rem;
        font-weight: 700;
        color: #e6f1ff;
        margin-top: 2rem;
        margin-bottom: 1rem;
        padding-left: 0.8rem;
        border-left: 4px solid #00d4ff;
    }
    
    /* ---------- Карточки метрик ---------- */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e2532 0%, #252d3d 100%);
        padding: 1.2rem 1.5rem;
        border-radius: 16px;
        border: 1px solid #2d3748;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        transition: all 0.3s ease;
    }
    
    [data-testid="stMetric"]:hover {
        border-color: #00d4ff;
        box-shadow: 0 8px 30px rgba(0, 212, 255, 0.15);
        transform: translateY(-2px);
    }
    
    [data-testid="stMetricLabel"] {
        color: #8892b0 !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    [data-testid="stMetricValue"] {
        color: #e6f1ff !important;
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }
    
    /* ---------- Кнопки ---------- */
    .stButton > button {
        background: linear-gradient(135deg, #00d4ff 0%, #7b2ff7 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.6rem 1.5rem;
        font-weight: 600;
        font-size: 0.95rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(0, 212, 255, 0.3);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 25px rgba(123, 47, 247, 0.5);
    }
    
    /* ---------- Сайдбар ---------- */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0e1117 0%, #131824 100%);
        border-right: 1px solid #2d3748;
    }
    
    [data-testid="stSidebar"] .stRadio label {
        padding: 0.5rem 0.8rem;
        border-radius: 8px;
        transition: all 0.2s ease;
        cursor: pointer;
    }
    
    [data-testid="stSidebar"] .stRadio label:hover {
        background: rgba(0, 212, 255, 0.1);
    }
    
    /* ---------- Табы / вкладки ---------- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: #1e2532;
        border-radius: 10px;
        padding: 0.6rem 1.2rem;
        color: #8892b0;
        border: 1px solid #2d3748;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #00d4ff 0%, #7b2ff7 100%);
        color: white !important;
        border: none;
    }
    
    /* ---------- DataFrame ---------- */
    [data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #2d3748;
    }
    
    /* ---------- Информационные блоки ---------- */
    .stAlert {
        border-radius: 12px;
        border-left: 4px solid #00d4ff;
    }
    
    /* ---------- Экспандеры ---------- */
    .streamlit-expanderHeader {
        background: #1e2532 !important;
        border-radius: 10px !important;
        color: #e6f1ff !important;
        font-weight: 600 !important;
    }
    
    /* ---------- Слайдеры ---------- */
    [data-testid="stSlider"] > div > div > div > div {
        background: linear-gradient(90deg, #00d4ff 0%, #7b2ff7 100%);
    }
    
    /* ---------- Скроллбар ---------- */
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    
    ::-webkit-scrollbar-track {
        background: #0e1117;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, #00d4ff 0%, #7b2ff7 100%);
        border-radius: 5px;
    }
    
    /* ---------- Карточка сигнала ---------- */
    .signal-card {
        padding: 1.5rem;
        border-radius: 16px;
        margin: 1rem 0;
        border-left: 5px solid;
        background: linear-gradient(135deg, #1e2532 0%, #252d3d 100%);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }
    
    .signal-buy { border-left-color: #00ff88; }
    .signal-sell { border-left-color: #ff2d55; }
    .signal-watch { border-left-color: #ffaa00; }
    .signal-neutral { border-left-color: #8892b0; }
    
    .signal-text {
        color: #e6f1ff;
        font-size: 1.1rem;
        font-weight: 600;
    }
    
    /* ---------- Хедер карточка ---------- */
    .hero-card {
        background: linear-gradient(135deg, rgba(0, 212, 255, 0.1) 0%, rgba(123, 47, 247, 0.1) 100%);
        border: 1px solid rgba(0, 212, 255, 0.3);
        border-radius: 20px;
        padding: 1.5rem 2rem;
        margin-bottom: 2rem;
    }
    
    /* ---------- Бейджи ---------- */
    .badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .badge-green { background: rgba(0, 255, 136, 0.15); color: #00ff88; }
    .badge-red { background: rgba(255, 45, 85, 0.15); color: #ff2d55; }
    .badge-yellow { background: rgba(255, 170, 0, 0.15); color: #ffaa00; }
    .badge-blue { background: rgba(0, 212, 255, 0.15); color: #00d4ff; }
</style>
""", unsafe_allow_html=True)


# =========================================================
#   ЗАГОЛОВОК
# =========================================================

st.markdown('<div class="main-title">📈 MOEX Analyzer</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="main-subtitle">Персональный ИИ-анализатор Московской биржи · '
    '⚠️ Не является инвестиционной рекомендацией</div>',
    unsafe_allow_html=True
)


# =========================================================
#   БОКОВАЯ ПАНЕЛЬ
# =========================================================

st.sidebar.markdown('### 🎛️ Навигация')
tab = st.sidebar.radio(
    'Режим:',
    [
        '📊 Теханализ акции',
        '💼 Мой портфель',
        '📋 Все акции',
        '🔥 Тепловая карта',
        '🧪 Бэктест',
        '💰 Скрининг облигаций',
        '🧠 Обучение ML',
    ],
    label_visibility='collapsed'
)


# =========================================================
#   ФУНКЦИЯ: карточка сигнала
# =========================================================

def render_signal_card(signal_type, message):
    cls = {
        'BUY': 'signal-buy',
        'SELL': 'signal-sell',
        'WATCH_BUY': 'signal-watch',
        'WATCH_SELL': 'signal-watch',
        'NEUTRAL': 'signal-neutral',
    }.get(signal_type, 'signal-neutral')
    st.markdown(
        f'<div class="signal-card {cls}">'
        f'<div class="signal-text">{message}</div>'
        f'</div>',
        unsafe_allow_html=True
    )


# =========================================================
#   1. ТЕХАНАЛИЗ ОДНОЙ АКЦИИ
# =========================================================

if tab == '📊 Теханализ акции':
    ticker = st.sidebar.text_input('Тикер', 'SBER').upper()

    if st.sidebar.button('🚀 Загрузить / Обновить'):
        with st.spinner('Загружаем данные...'):
            session = requests.Session()
            df = get_stock_history(session, ticker)

        if df.empty:
            st.error('Не удалось загрузить данные. Проверьте тикер.')
        else:
            df = add_indicators(df)
            signal = get_last_signal(df)

            try:
                ml_signal = predict_ml(ticker) if config.ML_ENABLED else None
            except Exception:
                ml_signal = None

            try:
                long_ml = predict_long_ml(ticker) if getattr(config, 'ML_LONG_ENABLED', False) else None
            except Exception:
                long_ml = None

            last = df.iloc[-1]

            st.markdown(f'<div class="section-title">📊 {ticker}</div>', unsafe_allow_html=True)
            render_signal_card(signal['type'], signal['message'])

            # ML метрики
            col_a, col_b, col_c = st.columns(3)
            if ml_signal:
                col_a.metric('🤖 ML BUY (5 дней)', f"{ml_signal['probability_up']:.1%}")
            if long_ml:
                if 'long_buy' in long_ml:
                    col_b.metric(
                        f'🔭 LONG BUY (+{int(config.ML_LONG_BUY_THRESHOLD*100)}%)',
                        f"{long_ml['long_buy']:.1%}"
                    )
                if 'long_sell' in long_ml:
                    col_c.metric(
                        f'🔻 LONG SELL ({int(config.ML_LONG_SELL_THRESHOLD*100)}%)',
                        f"{long_ml['long_sell']:.1%}"
                    )

            # Основные метрики
            st.markdown('<div class="section-title">📌 Ключевые показатели</div>', unsafe_allow_html=True)
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric('💰 Цена', f"{last['close']:.2f} ₽")
            c2.metric('📊 RSI (14)', f"{last['RSI']:.1f}")
            c3.metric('📈 MACD', f"{last['MACD']:.4f}")
            c4.metric('📉 Signal', f"{last['MACD_signal']:.4f}")
            c5.metric('⚡ ATR (14)', f"{last['ATR']:.2f}")

            if signal['type'] == 'BUY' and pd.notna(last['ATR']):
                pos = calculate_position_size(
                    float(last['close']), float(last['ATR']),
                    config.PORTFOLIO_SIZE, config.RISK_PER_TRADE, config.STOP_ATR_MULT
                )
                if pos['shares'] > 0:
                    st.info(
                        f"💼 **Рекомендуемая позиция:** {pos['shares']} шт. "
                        f"на сумму ~{pos['position_rub']:.0f} ₽ | "
                        f"Стоп-лосс: {pos['stop_loss']} ₽ | "
                        f"Макс. риск: {pos['risk_rub']:.0f} ₽"
                    )

            # График
            st.markdown('<div class="section-title">📉 График и индикаторы</div>', unsafe_allow_html=True)
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                                row_heights=[0.5, 0.25, 0.25], vertical_spacing=0.05)
            fig.add_trace(go.Candlestick(
                x=df.index, open=df['open'], high=df['high'],
                low=df['low'], close=df['close'], name='Цена',
                increasing_line_color='#00ff88',
                decreasing_line_color='#ff2d55'
            ), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA'], line=dict(color='#ffaa00', width=1.5),
                                     name='SMA20'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['BB_upper'], line=dict(color='#8892b0', width=1,
                                     dash='dot'), name='BB upper'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['BB_lower'], line=dict(color='#8892b0', width=1,
                                     dash='dot'), name='BB lower'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='#7b2ff7', width=1.5),
                                     name='RSI'), row=2, col=1)
            fig.add_hline(y=70, line_dash='dot', line_color='#ff2d55', row=2, col=1)
            fig.add_hline(y=30, line_dash='dot', line_color='#00ff88', row=2, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='#00d4ff', width=1.5),
                                     name='MACD'), row=3, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MACD_signal'], line=dict(color='#ff2d95', width=1.5),
                                     name='Signal'), row=3, col=1)
            fig.update_layout(
                height=800, showlegend=True, xaxis_rangeslider_visible=False,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(30,37,50,0.3)',
                font=dict(color='#e6f1ff'),
                legend=dict(bgcolor='rgba(30,37,50,0.8)')
            )
            st.plotly_chart(fig, use_container_width=True)


# =========================================================
#   2. МОЙ ПОРТФЕЛЬ
# =========================================================

elif tab == '💼 Мой портфель':
    from portfolio_manager import (
        load_portfolio, add_trade, remove_trade,
        calculate_positions, get_portfolio_summary,
        get_sector_concentration, clear_cache
    )

    st.markdown('<div class="section-title">💼 Мой портфель</div>', unsafe_allow_html=True)

    with st.expander('➕ Добавить сделку', expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            new_ticker = st.text_input('Тикер / ISIN', 'SBER').upper()
        with col2:
            new_type = st.selectbox('Тип', ['buy', 'sell'])
        with col3:
            new_qty = st.number_input('Количество', min_value=1.0, value=1.0, step=1.0)
        with col4:
            new_price = st.number_input('Цена, ₽', min_value=0.01, value=300.0, step=0.01)

        new_date = st.date_input('Дата сделки', datetime.now()).strftime('%Y-%m-%d')

        if st.button('➕ Добавить сделку'):
            add_trade(new_ticker, new_type, new_qty, new_price, new_date)
            st.success(f'✅ Добавлено: {new_ticker} {new_type} {new_qty:.0f}× {new_price} ₽')
            st.rerun()

    col_r1, col_r2 = st.columns([3, 1])
    with col_r1:
        st.markdown('<div class="section-title">📊 Сводка</div>', unsafe_allow_html=True)
    with col_r2:
        if st.button('🔄 Обновить цены'):
            clear_cache()
            st.rerun()

    portfolio_df = load_portfolio()

    if portfolio_df.empty:
        st.info('👈 Портфель пуст. Добавьте первую сделку через форму выше.')
    else:
        with st.spinner('Загружаем текущие цены...'):
            positions = calculate_positions(portfolio_df)
            summary = get_portfolio_summary(positions)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric('💼 Стоимость', f"{summary['total_value']:,.0f} ₽")
        c2.metric(
            '📈 P&L (нереализ.)',
            f"{summary['total_unrealized_pnl']:+,.0f} ₽",
            delta=f"{summary['pnl_pct']:+.1f}%"
        )
        c3.metric('💰 P&L (реализ.)', f"{summary['total_realized_pnl']:+,.0f} ₽")
        c4.metric('📋 Позиций', summary['positions_count'])

        st.markdown('<div class="section-title">📋 Открытые позиции</div>', unsafe_allow_html=True)

        active_positions = {t: p for t, p in positions.items() if p['quantity'] > 0}

        if not active_positions:
            st.info('Нет открытых позиций.')
        else:
            type_labels = {
                'stock': '📈 Акция',
                'bond': '📜 Облигация',
                'etf': '🏦 ETF',
                'unknown': '❓ Прочее',
            }
            pos_rows = []
            for ticker, p in active_positions.items():
                pos_rows.append({
                    'Тикер': ticker,
                    'Тип': type_labels.get(p.get('type', 'unknown'), 'Прочее'),
                    'Кол-во': round(p['quantity'], 2),
                    'Ср. цена': round(p['avg_buy_price'], 2),
                    'Тек. цена': round(p['current_price'], 2),
                    'Стоимость': round(p['current_value'], 0),
                    'P&L': round(p['unrealized_pnl'], 0),
                    'P&L %': round(p['pnl_pct'], 2),
                })

            df_pos = pd.DataFrame(pos_rows).sort_values('P&L', ascending=False)

            st.dataframe(
                df_pos,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Стоимость': st.column_config.NumberColumn(format='%.0f ₽'),
                    'P&L': st.column_config.NumberColumn(format='%+.0f ₽'),
                    'P&L %': st.column_config.NumberColumn(format='%+.2f %%'),
                }
            )

        st.markdown('<div class="section-title">🏭 Секторная концентрация</div>', unsafe_allow_html=True)

        with st.spinner('Считаем сектора...'):
            sectors = get_sector_concentration(positions)

        if sectors:
            max_sector = max(sectors.values())
            if max_sector > 50:
                st.warning(f'⚠️ Высокая концентрация: {max_sector:.0f}% в одном секторе.')
            elif max_sector > 35:
                st.info(f'ℹ️ Умеренная концентрация: {max_sector:.0f}%.')

            sector_df = pd.DataFrame([
                {'Сектор': s, 'Доля, %': v}
                for s, v in sorted(sectors.items(), key=lambda x: -x[1])
            ])

            fig = px.pie(
                sector_df, values='Доля, %', names='Сектор',
                title='Распределение по секторам',
                color_discrete_sequence=['#00d4ff', '#7b2ff7', '#ff2d95', '#00ff88',
                                          '#ffaa00', '#ff6b6b', '#4ecdc4', '#c7f464']
            )
            fig.update_layout(
                height=400,
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#e6f1ff')
            )
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(sector_df, use_container_width=True, hide_index=True)
        else:
            st.info('Нет данных по секторам.')

        with st.expander('📜 Все сделки'):
            display_trades = portfolio_df.copy()
            display_trades['date'] = pd.to_datetime(display_trades['date']).dt.strftime('%d.%m.%Y')
            display_trades['type'] = display_trades['type'].map(
                {'buy': '🟢 Покупка', 'sell': '🔴 Продажа'}
            )
            display_trades = display_trades.rename(columns={
                'date': 'Дата', 'ticker': 'Тикер', 'type': 'Тип',
                'quantity': 'Кол-во', 'price': 'Цена, ₽'
            })
            display_trades = display_trades[['Дата', 'Тикер', 'Тип', 'Кол-во', 'Цена, ₽']]
            st.dataframe(display_trades, use_container_width=True, hide_index=True)

            st.markdown('**Удалить сделку** — введите индекс:')
            col_del1, col_del2 = st.columns([3, 1])
            with col_del1:
                del_idx = st.number_input('Индекс', min_value=0, value=0, step=1, key='del_idx')
            with col_del2:
                if st.button('🗑️ Удалить'):
                    if remove_trade(del_idx):
                        st.success('Сделка удалена.')
                        st.rerun()
                    else:
                        st.error('Неверный индекс.')


# =========================================================
#   3. ВСЕ АКЦИИ
# =========================================================

elif tab == '📋 Все акции':
    st.markdown('<div class="section-title">📋 Сигналы по всем акциям</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        filter_signal = st.selectbox(
            'Фильтр по сигналу:',
            ['Все', 'Только BUY', 'Только SELL', 'Только WATCH']
        )
    with col2:
        include_ml = st.checkbox('Показывать ML-вероятность (медленно)', value=False)

    if st.button('🔄 Загрузить / Обновить сводку'):
        with st.spinner('Загружаем данные по всем акциям... Это займёт 2–5 минут.'):
            data_dict = get_all_stocks_data(['ALL'])

        if not data_dict:
            st.warning('Не удалось загрузить данные.')
        else:
            rows = []
            total = len(data_dict)
            progress = st.progress(0)

            for i, (ticker, d) in enumerate(data_dict.items()):
                sig = d['signal']
                signal_type = sig['type']

                ml_prob = None
                if include_ml and config.ML_ENABLED:
                    try:
                        ml = predict_ml(ticker)
                        if ml:
                            ml_prob = ml['probability_up']
                    except Exception:
                        pass

                row = {
                    'Тикер': ticker,
                    'Цена': round(d['last_close'], 2),
                    'RSI': round(d['rsi'], 1),
                    'Тип': signal_type,
                    'Сообщение': sig['message'],
                }
                if include_ml:
                    row['ML BUY'] = f"{ml_prob:.1%}" if ml_prob else '—'
                rows.append(row)
                progress.progress((i + 1) / total)

            df_signals = pd.DataFrame(rows)

            if filter_signal == 'Только BUY':
                df_signals = df_signals[df_signals['Тип'] == 'BUY']
            elif filter_signal == 'Только SELL':
                df_signals = df_signals[df_signals['Тип'] == 'SELL']
            elif filter_signal == 'Только WATCH':
                df_signals = df_signals[df_signals['Тип'].isin(['WATCH_BUY', 'WATCH_SELL'])]

            st.success(f"✅ Найдено: {len(df_signals)} акций (из {len(data_dict)})")
            st.dataframe(df_signals, use_container_width=True, hide_index=True)


# =========================================================
#   4. ТЕПЛОВАЯ КАРТА
# =========================================================

elif tab == '🔥 Тепловая карта':
    st.markdown('<div class="section-title">🔥 Тепловая карта секторов</div>', unsafe_allow_html=True)
    st.caption('Красные сектора — перепроданы, зелёные — перекуплены.')

    if st.button('🗺️ Построить карту'):
        with st.spinner('Загружаем данные по всем акциям...'):
            session = requests.Session()
            sectors = get_ticker_sectors(session)
            data_dict = get_all_stocks_data(['ALL'])

        if not data_dict:
            st.warning('Нет данных.')
        else:
            sector_rsi = {}
            sector_tickers = {}
            sector_signals = {}

            for ticker, d in data_dict.items():
                sector = sectors.get(ticker, 'Прочее')
                sector_rsi.setdefault(sector, []).append(d['rsi'])
                sector_tickers.setdefault(sector, []).append(ticker)
                sig_type = d['signal']['type']
                sector_signals.setdefault(sector, []).append(sig_type)

            rows = []
            for sector_name, rsi_list in sector_rsi.items():
                if not rsi_list:
                    continue
                tickers_list = sector_tickers.get(sector_name, [])
                signals_list = sector_signals.get(sector_name, [])
                tickers_str = ', '.join(sorted(tickers_list)[:5])
                if len(tickers_list) > 5:
                    tickers_str += f'... (+{len(tickers_list) - 5})'

                rows.append({
                    'Сектор': sector_name,
                    'Средний RSI': round(sum(rsi_list) / len(rsi_list), 1),
                    'Мин RSI': round(min(rsi_list), 1),
                    'Макс RSI': round(max(rsi_list), 1),
                    'Кол-во': len(rsi_list),
                    'BUY': signals_list.count('BUY'),
                    'WATCH': signals_list.count('WATCH_BUY'),
                    'SELL': signals_list.count('SELL'),
                    'Примеры акций': tickers_str,
                })

            if not rows:
                st.warning('Нет данных по секторам.')
            else:
                df_sectors = pd.DataFrame(rows).sort_values('Средний RSI')

                rsi_min = float(df_sectors['Средний RSI'].min())
                rsi_max = float(df_sectors['Средний RSI'].max())
                pad = max(5.0, (rsi_max - rsi_min) * 0.3)

                st.info(
                    f"📊 RSI секторов сегодня: от **{rsi_min:.1f}** до **{rsi_max:.1f}** "
                    f"(средний по рынку: **{df_sectors['Средний RSI'].mean():.1f}**)"
                )

                fig = px.treemap(
                    df_sectors, path=['Сектор'], values='Кол-во',
                    color='Средний RSI', color_continuous_scale='RdYlGn_r',
                    range_color=(rsi_min - pad, rsi_max + pad),
                    title='Средний RSI по секторам',
                    hover_data=['Средний RSI', 'Мин RSI', 'Макс RSI', 'Кол-во']
                )
                fig.update_layout(
                    height=600,
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#e6f1ff')
                )
                st.plotly_chart(fig, use_container_width=True)

                st.markdown('<div class="section-title">📊 Сектора по среднему RSI</div>', unsafe_allow_html=True)
                fig_bar = px.bar(
                    df_sectors, x='Средний RSI', y='Сектор', orientation='h',
                    color='Средний RSI', color_continuous_scale='RdYlGn_r',
                    range_color=(rsi_min - pad, rsi_max + pad),
                    text='Средний RSI'
                )
                fig_bar.update_traces(texttemplate='%{text:.1f}', textposition='outside')
                fig_bar.add_vline(x=30, line_dash='dash', line_color='#00ff88')
                fig_bar.add_vline(x=70, line_dash='dash', line_color='#ff2d55')
                fig_bar.update_layout(
                    height=max(400, len(df_sectors) * 25), showlegend=False,
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(30,37,50,0.3)',
                    font=dict(color='#e6f1ff')
                )
                st.plotly_chart(fig_bar, use_container_width=True)

                oversold = df_sectors[df_sectors['Средний RSI'] < 40]
                overbought = df_sectors[df_sectors['Средний RSI'] > 60]

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown('### 🔴 Перепроданные')
                    if not oversold.empty:
                        st.dataframe(
                            oversold[['Сектор', 'Средний RSI', 'BUY', 'WATCH', 'Кол-во']],
                            use_container_width=True, hide_index=True
                        )
                    else:
                        st.info('Нет явно перепроданных секторов.')

                with col2:
                    st.markdown('### 🟢 Перекупленные')
                    if not overbought.empty:
                        st.dataframe(
                            overbought[['Сектор', 'Средний RSI', 'SELL', 'Кол-во']],
                            use_container_width=True, hide_index=True
                        )
                    else:
                        st.info('Нет явно перекупленных секторов.')


# =========================================================
#   5. БЭКТЕСТ
# =========================================================

elif tab == '🧪 Бэктест':
    st.markdown('<div class="section-title">🧪 Бэктест стратегии</div>', unsafe_allow_html=True)
    st.caption('Стратегия: RSI < 35 + MACD бычий, размер позиции по ATR.')

    col1, col2, col3 = st.columns(3)
    with col1:
        bt_ticker = st.text_input('Тикер', 'SBER').upper()
    with col2:
        bt_years = st.slider('Лет истории', 1, 10, 5)
    with col3:
        bt_cash = st.number_input('Начальный капитал, ₽', 100000, 10000000, 500000, 50000)

    if st.button('▶️ Запустить бэктест'):
        with st.spinner(f'Идёт бэктест {bt_ticker}... 30–60 секунд.'):
            try:
                from backtest import run_backtest
                result = run_backtest(bt_ticker, bt_years, bt_cash)

                if result:
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric('📈 Доходность', f"{result['total_return_percent']:.2f}%",
                              delta=f"{result['end_value'] - result['start_value']:.0f} ₽")
                    c2.metric('📊 Шарп', f"{result['sharpe']:.2f}")
                    c3.metric('📉 Макс. просадка', f"{result['max_drawdown_percent']:.2f}%")
                    c4.metric('🔢 Сделок', result['total_trades'])
                    st.metric('🎯 Win rate', f"{result['win_rate']:.1f}%")

                    if result['total_trades'] == 0:
                        st.info('⚠️ Стратегия не нашла точек входа за период.')
                    elif result['total_return_percent'] > 0:
                        st.success(f"✅ Заработала бы {result['end_value'] - result['start_value']:.0f} ₽")
                    else:
                        st.error(f"❌ Потеряла бы {result['start_value'] - result['end_value']:.0f} ₽")
                else:
                    st.error('Недостаточно данных.')
            except Exception as e:
                st.error(f'Ошибка: {e}')


# =========================================================
#   6. СКРИНИНГ ОБЛИГАЦИЙ
# =========================================================

elif tab == '💰 Скрининг облигаций':
    st.markdown('<div class="section-title">💰 Скрининг облигаций</div>', unsafe_allow_html=True)

    st.sidebar.markdown('### 🎯 Фильтры')
    min_yield = st.sidebar.slider('Мин. YTM, %', 0.0, 40.0, 12.0, 0.5)
    max_dur = st.sidebar.slider('Макс. дюрация, дни', 30, 5000, 3650, 30)
    top_n = st.sidebar.slider('Сколько показать', 10, 100, 20, 5)
    min_volume_mln = st.sidebar.slider('Мин. объём, млн ₽', 0.0, 100.0, 5.0, 0.5)
    min_volume = min_volume_mln * 1_000_000
    only_trusted = st.sidebar.checkbox('🛡️ Только надёжные', value=True)
    sort_by = st.sidebar.selectbox(
        'Сортировка:', ['YTM', 'Дюрация', 'Купон %', 'Объём торгов']
    )

    col_refresh, col_force = st.sidebar.columns(2)
    refresh_clicked = col_refresh.button('🔄 Кэш')
    force_clicked = col_force.button('⚡ С MOEX')

    if refresh_clicked or force_clicked:
        with st.spinner('Загружаем облигации...'):
            session = requests.Session()
            bonds_df = get_bonds_data(
                session, force_refresh=force_clicked,
                min_daily_volume=min_volume, only_trusted=only_trusted
            )
        if bonds_df is None or bonds_df.empty:
            st.error('Не удалось загрузить.')
        else:
            st.session_state['bonds_df'] = bonds_df
            st.success(f'✅ Загружено {len(bonds_df)}')

    if 'bonds_df' in st.session_state:
        bonds_df = st.session_state['bonds_df'].copy()
        if 'YIELD' in bonds_df.columns:
            mask = (bonds_df['YIELD'] >= min_yield) & (bonds_df['DURATION'] <= max_dur)
            filtered = bonds_df[mask].copy()

            if sort_by == 'YTM':
                filtered = filtered.sort_values('YIELD', ascending=False)
            elif sort_by == 'Дюрация':
                filtered = filtered.sort_values('DURATION', ascending=True)
            elif sort_by == 'Купон %' and 'coupon_rate' in filtered.columns:
                filtered = filtered.sort_values('coupon_rate', ascending=False)
            elif sort_by == 'Объём торгов' and 'DAILY_VOLUME' in filtered.columns:
                filtered = filtered.sort_values('DAILY_VOLUME', ascending=False)

            top_bonds = filtered.head(top_n)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric('Всего', len(bonds_df))
            col2.metric('Прошли фильтр', len(filtered))
            if not filtered.empty:
                col3.metric('Макс. YTM', f"{filtered['YIELD'].max():.2f}%")
                col4.metric('Средняя YTM', f"{filtered['YIELD'].mean():.2f}%")

            display_df = top_bonds.copy()
            if 'YIELD' in display_df.columns:
                display_df['YIELD'] = display_df['YIELD'].round(2)
            for date_col in ['MATDATE', 'OFFERDATE', 'NEXTCOUPON']:
                if date_col in display_df.columns:
                    display_df[date_col] = display_df[date_col].dt.strftime('%d.%m.%Y')

            display_df = display_df.rename(columns={
                'SECID': 'Тикер', 'SHORTNAME': 'Название', 'YIELD': 'YTM %',
                'coupon_rate': 'Купон %', 'DURATION': 'Дюрация',
                'MATDATE': 'Погашение', 'PRICE': 'Цена',
            })
            cols_to_show = [c for c in ['Тикер', 'Название', 'YTM %', 'Купон %',
                                        'Дюрация', 'Погашение', 'Цена']
                           if c in display_df.columns]
            st.dataframe(display_df[cols_to_show], use_container_width=True, hide_index=True)
        else:
            st.error('Нет данных. Обновите.')


# =========================================================
#   7. ОБУЧЕНИЕ ML
# =========================================================

elif tab == '🧠 Обучение ML':
    st.markdown('<div class="section-title">🧠 Обучение ML-моделей</div>', unsafe_allow_html=True)

    st.markdown('### 1. Краткосрочная модель (5 дней, +1.5%)')
    col1, col2 = st.columns(2)
    with col1:
        train_ticker = st.text_input('Тикер', 'SBER').upper()
    with col2:
        train_years = st.slider('Лет истории', 1, 10, 5)

    if st.button('🎯 Обучить краткосрочную'):
        with st.spinner(f'Обучаем на {train_ticker}...'):
            try:
                train_model_for_ticker(train_ticker, train_years)
                st.success(f'✅ Модель для {train_ticker} сохранена.')
            except Exception as e:
                st.error(f'Ошибка: {e}')

    st.divider()

    st.markdown('### 2. Долгосрочные модели (20 дней, ±10%)')
    long_ticker = st.text_input('Тикер для долгосрочных моделей', 'SBER').upper()
    if st.button('🔭 Обучить долгосрочные'):
        with st.spinner(f'Обучаем LONG BUY/SELL для {long_ticker}...'):
            try:
                train_long_models_for_ticker(long_ticker, 5)
                st.success(f'✅ Долгосрочные модели для {long_ticker} обучены.')
            except Exception as e:
                st.error(f'Ошибка: {e}')

    st.divider()

    st.markdown('### 3. Модель индекса IMOEX')
    col_bt1, col_bt2 = st.columns(2)
    with col_bt1:
        if st.button('🌐 Обучить IMOEX'):
            with st.spinner('Обучаем модель индекса...'):
                try:
                    ok = train_index_model(5)
                    if ok:
                        st.success('✅ Модель IMOEX обучена.')
                    else:
                        st.warning('Не удалось загрузить данные IMOEX.')
                except Exception as e:
                    st.error(f'Ошибка: {e}')
    with col_bt2:
        if st.button('📊 Прогноз IMOEX'):
            try:
                ctx = get_market_context()
                if ctx:
                    st.info(ctx)
                else:
                    st.warning('Модель IMOEX ещё не обучена.')
            except Exception as e:
                st.error(f'Ошибка: {e}')


# =========================================================
#   ФУТЕР
# =========================================================

st.sidebar.divider()
st.sidebar.markdown(
    '<div style="color: #8892b0; font-size: 0.75rem; text-align: center; padding: 1rem 0;">'
    '⚠️ Не является инвестиционной рекомендацией<br>'
    'Сделано с ❤️ для личного использования'
    '</div>',
    unsafe_allow_html=True
)