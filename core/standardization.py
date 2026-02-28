import numpy as np
from scipy.stats import skew, kurtosis


def expanding_zscore(series):
    mean = series.expanding().mean()
    std = series.expanding().std(ddof=0)
    std = std.replace(0, np.nan)
    return (series - mean) / std


def expanding_robust_zscore(series):
    median = series.expanding().median()
    mad = (series - median).abs().expanding().median()
    mad = mad.replace(0, np.nan)
    return (series - median) / (1.4826 * mad)


def smart_zscore(series):

    s = series.dropna()
    if len(s) < 24:
        return expanding_zscore(series)

    s_skew = skew(s)
    s_kurt = kurtosis(s, fisher=False)

    if abs(s_skew) > 0.5 or s_kurt > 4:
        z = expanding_robust_zscore(series)
    else:
        z = expanding_zscore(series)

    return z.clip(-3, 3) / 3