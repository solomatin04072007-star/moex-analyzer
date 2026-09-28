# config.py

# ========== СПИСОК ТИКЕРОВ ==========
STOCK_TICKERS = ['ALL']

# ========== УВЕДОМЛЕНИЯ EMAIL ==========
EMAIL_ENABLED = True
SMTP_SERVER = 'smtp.mail.ru'  # Для Яндекс: smtp.yandex.ru, для Gmail: smtp.gmail.com
SMTP_PORT = 465
SENDER_EMAIL = 'your_email@example.com'
SENDER_PASSWORD = 'your_app_password'
RECEIVER_EMAIL = 'your_email@example.com'

# ========== УВЕДОМЛЕНИЯ NTFY ==========
NTFY_ENABLED = False
NTFY_TOPIC = 'moex_signals_example'
NTFY_URL = 'https://ntfy.sh'

# ========== ПАРАМЕТРЫ СТРАТЕГИИ ==========
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
SMA_PERIOD = 20
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ========== ОБЛИГАЦИИ (новые параметры) ==========
# Никаких жёстких фильтров по умолчанию — показываем всё
BONDS_DEFAULT_MIN_YIELD = 0.0        # минимальная YTM по умолчанию
BONDS_DEFAULT_MAX_DURATION = 3650    # макс. дюрация по умолчанию (10 лет)
BONDS_TOP_N = 20                      # сколько облигаций показывать в ТОПе
BONDS_NOTIFIER_TOP_N = 5              # сколько облигаций в утренней сводке

# Старые параметры (оставлены для совместимости, но не используются)
BOND_FILTER_BY_PRICE = False
BOND_NOMINAL = 1000
BOND_MAX_PRICE = 1000000
BOND_MIN_COUPON = 0.0

# ========== ML-МОДЕЛЬ ==========
ML_ENABLED = True
ML_THRESHOLD = 0.65
MODELS_DIR = 'models'

# ========== ДОЛГОСРОЧНЫЕ ML-МОДЕЛИ ==========
ML_LONG_ENABLED = True
ML_LONG_HORIZON = 20
ML_LONG_BUY_THRESHOLD = 0.10
ML_LONG_SELL_THRESHOLD = -0.10
ML_LONG_MIN_PROB = 0.65
ML_LONG_DIR = 'models_long'

# ========== РИСК-МЕНЕДЖМЕНТ ==========
PORTFOLIO_SIZE = 500000
RISK_PER_TRADE = 0.02
STOP_ATR_MULT = 2.0

# ========== ВРЕМЯ ПРОВЕРКИ ==========
CHECK_HOUR = 10
CHECK_MINUTE = 45