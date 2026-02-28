import numpy as np
import pandas as pd


def rolling_zscore(series, window=120):
    rolling_mean = series.rolling(window).mean()
    rolling_std = series.rolling(window).std()
    z = (series - rolling_mean) / rolling_std
    return z


def smooth_compress(z):
    return np.tanh(z / 2)


REGIME_LABELS = {
    -2: "Strongly Bearish",
    -1: "Bearish",
    0: "Neutral",
    1: "Bullish",
    2: "Strongly Bullish",
}


def quantile_regime(series):
    s = series.dropna()
    if s.empty:
        return series.apply(lambda x: np.nan)
    q20 = s.quantile(0.2)
    q40 = s.quantile(0.4)
    q60 = s.quantile(0.6)
    q80 = s.quantile(0.8)

    def map_value(x):
        if pd.isna(x):
            return np.nan
        if x <= q20:
            return -2
        elif x <= q40:
            return -1
        elif x <= q60:
            return 0
        elif x <= q80:
            return 1
        else:
            return 2

    return series.apply(map_value)
