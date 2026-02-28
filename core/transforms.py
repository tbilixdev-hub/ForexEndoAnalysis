def yoy(series):
    return series.pct_change(12) * 100


def three_month_level_change(series):
    return series.diff(3)


def three_month_rolling_mean(series):
    return series.rolling(3).mean()


def three_month_annualized(series):
    return ((series / series.shift(3)) ** 4 - 1) * 100


def six_month_change(series):
    return series.diff(6)


def six_month_percent_change(series):
    return series.pct_change(6) * 100


def percent_of_gdp(numerator, gdp):
    return numerator / gdp