# train_long_models.py

import requests
import os
import config
from data_manager import get_all_tickers
from ml_model import train_long_models_for_ticker
from joblib import Parallel, delayed

N_JOBS = 6  # под i5-12400

session = requests.Session()
tickers = get_all_tickers(session)
print(f'Найдено {len(tickers)} тикеров.')
print(f'Параллельное обучение долгосрочных моделей (n_jobs={N_JOBS})...\n')

os.makedirs(config.ML_LONG_DIR, exist_ok=True)


def train_one(ticker):
    buy_path = os.path.join(config.ML_LONG_DIR, f'{ticker}_buy_model.json')
    sell_path = os.path.join(config.ML_LONG_DIR, f'{ticker}_sell_model.json')
    if os.path.exists(buy_path) and os.path.exists(sell_path):
        return f'{ticker}: уже обучен'
    try:
        ok = train_long_models_for_ticker(ticker, years=5)
        return f'{ticker}: {"OK" if ok else "SKIP"}'
    except Exception as e:
        return f'{ticker}: ERROR {e}'


results = Parallel(n_jobs=N_JOBS, verbose=10)(
    delayed(train_one)(t) for t in tickers
)

print('\nОбучение завершено!')