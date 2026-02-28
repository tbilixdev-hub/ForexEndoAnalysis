import numpy as np
import pandas as pd

from config_.series_config import SERIES_CONFIG

try:
    from scipy.stats import skew as _scipy_skew
    from scipy.stats import kurtosis as _scipy_kurtosis
except Exception:
    _scipy_skew = None
    _scipy_kurtosis = None


def _calc_skew(values):
    if _scipy_skew is not None:
        return float(_scipy_skew(values))
    return float(pd.Series(values).skew())


def _calc_kurtosis_pearson(values):
    if _scipy_kurtosis is not None:
        return float(_scipy_kurtosis(values, fisher=False))
    return float(pd.Series(values).kurt() + 3)


def _expanding_zscore(series):
    mean = series.expanding().mean()
    std = series.expanding().std(ddof=0)
    std = std.replace(0, np.nan)
    return (series - mean) / std


def _expanding_robust_zscore(series):
    med = series.expanding().median()
    mad = (series - med).abs().expanding().median()
    mad = mad.replace(0, np.nan)
    return (series - med) / (1.4826 * mad)


def _smart_zscore_raw(series):
    s = series.dropna()
    if len(s) < 24:
        return _expanding_zscore(series)

    s_skew = _calc_skew(s)
    s_kurt = _calc_kurtosis_pearson(s)
    if abs(s_skew) > 0.5 or abs(s_kurt) > 4:
        return _expanding_robust_zscore(series)
    return _expanding_zscore(series)


class FiscalPillar:

    def __init__(self, country, provider):
        self.country = country
        self.provider = provider
        self.score = 0
        self.details = []

    @staticmethod
    def _map_regime(score):
        if score > 0.5:
            return "Strong Fiscal Position"
        if score > 0:
            return "Stable Fiscal"
        if score > -0.5:
            return "Deteriorating"
        return "Fiscal Stress"

    def run(self):
        country_config = SERIES_CONFIG.get(self.country, {})
        fiscal_config = country_config.get("fiscal", {})

        if not fiscal_config:
            return 0

        role_to_indicator = {}
        for name, cfg in fiscal_config.items():
            role_to_indicator[cfg.get("role", name)] = (name, cfg)

        required_roles = ["debt_gdp", "deficit_gdp", "interest_gdp", "receipts", "yield10"]
        missing_roles = [r for r in required_roles if r not in role_to_indicator]
        if missing_roles:
            self.details.append({
                "status": "skipped",
                "reason": f"Missing fiscal roles in config: {', '.join(missing_roles)}",
            })
            return 0

        try:
            debt_name, debt_cfg = role_to_indicator["debt_gdp"]
            deficit_name, deficit_cfg = role_to_indicator["deficit_gdp"]
            interest_name, interest_cfg = role_to_indicator["interest_gdp"]
            receipts_name, receipts_cfg = role_to_indicator["receipts"]
            yield_name, yield_cfg = role_to_indicator["yield10"]

            debt_gdp = self.provider.get_series(self.country, debt_cfg).resample("ME").ffill()
            deficit_gdp = self.provider.get_series(self.country, deficit_cfg).resample("ME").ffill()
            interest_gdp = self.provider.get_series(self.country, interest_cfg).resample("ME").ffill()
            receipts = self.provider.get_series(self.country, receipts_cfg).resample("ME").ffill()
            yield10 = self.provider.get_series(self.country, yield_cfg)

            debt_z = -_smart_zscore_raw(debt_gdp)
            deficit_z = -_smart_zscore_raw(deficit_gdp)
            interest_z = -_smart_zscore_raw(interest_gdp)
            liquidity_cover = receipts / interest_gdp
            liquidity_z = _smart_zscore_raw(liquidity_cover)
            yield_6m_change = yield10.resample("ME").last().diff(6)
            yield_z = -_smart_zscore_raw(yield_6m_change)

            df = pd.concat(
                [debt_z, deficit_z, interest_z, liquidity_z, yield_z],
                axis=1,
                sort=False,
            )
            df.columns = ["debt_z", "deficit_z", "interest_z", "liquidity_z", "yield_z"]
            df = df.dropna(how="all")
            if df.empty:
                raise ValueError("Fiscal pillar produced no aligned observations")

            component_cols = ["debt_z", "deficit_z", "interest_z", "liquidity_z", "yield_z"]
            df_complete = df.dropna(subset=component_cols).copy()
            if df_complete.empty:
                raise ValueError("No complete fiscal observation available")

            df_complete["fiscal_raw"] = (
                0.25 * df_complete["debt_z"] +
                0.20 * df_complete["deficit_z"] +
                0.20 * df_complete["interest_z"] +
                0.20 * df_complete["liquidity_z"] +
                0.15 * df_complete["yield_z"]
            ).clip(-3, 3)
            df_complete["fiscal_score"] = df_complete["fiscal_raw"] / 3

            last = df_complete.iloc[-1]
            self.score = float(last["fiscal_score"])
            regime = self._map_regime(self.score)

            self.details.append({
                "status": "used",
                "score": self.score,
                "regime": regime,
                "debt_indicator": debt_name,
                "deficit_indicator": deficit_name,
                "interest_indicator": interest_name,
                "receipts_indicator": receipts_name,
                "yield_indicator": yield_name,
                "debt_z": float(last["debt_z"]),
                "deficit_z": float(last["deficit_z"]),
                "interest_z": float(last["interest_z"]),
                "liquidity_z": float(last["liquidity_z"]),
                "yield_z": float(last["yield_z"]),
                "fiscal_raw": float(last["fiscal_raw"]),
            })
            return self.score
        except Exception as exc:
            self.details.append({
                "status": "skipped",
                "reason": str(exc),
            })
            return 0
