import numpy as np

try:
    from scipy.stats import skew as _scipy_skew
    from scipy.stats import kurtosis as _scipy_kurtosis
except Exception:
    _scipy_skew = None
    _scipy_kurtosis = None


def _calc_skew(series):
    if _scipy_skew is not None:
        return _scipy_skew(series)
    return series.skew()


def _calc_kurtosis_pearson(series):
    if _scipy_kurtosis is not None:
        return _scipy_kurtosis(series, fisher=False)
    # pandas kurtosis is Fisher (normal == 0), convert to Pearson (normal == 3)
    return series.kurt() + 3


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

    s_skew = _calc_skew(s)
    s_kurt = _calc_kurtosis_pearson(s)

    if abs(s_skew) > 0.5 or s_kurt > 4:
        z = expanding_robust_zscore(series)
    else:
        z = expanding_zscore(series)

    return z.clip(-3, 3) / 3
