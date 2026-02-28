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


class LaborPillar:

    def __init__(self, country, provider):
        self.country = country
        self.provider = provider
        self.score = 0
        self.details = []

    @staticmethod
    def _map_labor_regime(score):
        if score <= -0.7:
            return "Deep Recessionary Labor"
        if score <= -0.4:
            return "Deteriorating Labor"
        if score <= -0.15:
            return "Softening Labor"
        if score < 0.15:
            return "Neutral Labor"
        if score < 0.4:
            return "Healthy Expansion"
        if score < 0.7:
            return "Tight Labor Market"
        return "Overheating Labor Market"

    def run(self):
        country_config = SERIES_CONFIG.get(self.country, {})
        labor_config = country_config.get("labor", {})

        if not labor_config:
            return 0

        role_to_indicator = {}
        for name, cfg in labor_config.items():
            role_to_indicator[cfg.get("role", name)] = (name, cfg)

        required_roles = ["nfp", "ahe", "unrate"]
        missing_roles = [r for r in required_roles if r not in role_to_indicator]
        if missing_roles:
            self.details.append({
                "status": "skipped",
                "reason": f"Missing labor roles in config: {', '.join(missing_roles)}",
            })
            return 0

        try:
            nfp_name, nfp_cfg = role_to_indicator["nfp"]
            ahe_name, ahe_cfg = role_to_indicator["ahe"]
            unrate_name, unrate_cfg = role_to_indicator["unrate"]

            nfp = self.provider.get_series(self.country, nfp_cfg)
            ahe = self.provider.get_series(self.country, ahe_cfg)
            unrate = self.provider.get_series(self.country, unrate_cfg)

            nfp_change = nfp.diff()
            nfp_3m_avg = nfp_change.rolling(3).mean()
            nfp_z = _smart_zscore_raw(nfp_3m_avg)

            ahe_yoy = ahe.pct_change(12) * 100
            ahe_3m_ann = ((ahe / ahe.shift(3)) ** 4 - 1) * 100
            ahe_combined = 0.6 * ahe_yoy + 0.4 * ahe_3m_ann
            ahe_z = _smart_zscore_raw(ahe_combined)

            unrate_6m_change = unrate.diff(6)
            unrate_level_inv = -unrate
            unrate_change_inv = -unrate_6m_change
            unrate_combined = 0.6 * unrate_level_inv + 0.4 * unrate_change_inv
            unrate_z = _smart_zscore_raw(unrate_combined)

            df = pd.DataFrame({
                "nfp_z": nfp_z,
                "ahe_z": ahe_z,
                "unrate_z": unrate_z,
            }).dropna()

            if df.empty:
                raise ValueError("No valid values after labor block combination")

            df["labor_raw"] = (
                0.4 * df["nfp_z"] +
                0.3 * df["ahe_z"] +
                0.3 * df["unrate_z"]
            ).clip(-3, 3)
            df["labor_score"] = df["labor_raw"] / 3

            last = df.iloc[-1]
            self.score = float(last["labor_score"])
            regime = self._map_labor_regime(self.score)

            self.details.append({
                "status": "used",
                "score": self.score,
                "regime": regime,
                "nfp_indicator": nfp_name,
                "ahe_indicator": ahe_name,
                "unrate_indicator": unrate_name,
                "nfp_z": float(last["nfp_z"]),
                "ahe_z": float(last["ahe_z"]),
                "unrate_z": float(last["unrate_z"]),
                "labor_raw": float(last["labor_raw"]),
            })
            return self.score
        except Exception as exc:
            self.details.append({
                "status": "skipped",
                "reason": str(exc),
            })
            return 0
