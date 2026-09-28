# train_all_models.py

import requests
from data_manager import get_all_tickers
from ml_model import train_model_for_ticker
import config
import os
from joblib import Parallel, delayed

# Под i5-12400 (6 P-ядер / 12 потоков) ставим 6 параллельных задач
N_JOBS = 6

session = requests.Session()
tickers = get_all_tickers(session)
print(f'Найдено {len(tickers)} тикеров. Начинаем параллельное обучение (n_jobs={N_JOBS})...')

def train_one(ticker):
    model_path = os.path.join(config.MODELS_DIR, f'{ticker}_xgb_model.json')
    if os.path.exists(model_path):
        print(f'Модель для {ticker} уже существует, пропускаем.')
        return True
    success = train_model_for_ticker(ticker, years=5)
    return success

results = Parallel(n_jobs=N_JOBS, verbose=10)(
    delayed(train_one)(ticker) for ticker in tickers
)

print('\nОбучение завершено!')