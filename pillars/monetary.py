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


class MonetaryPillar:

    def __init__(self, country, provider):
        self.country = country
        self.provider = provider
        self.score = 0
        self.details = []

    @staticmethod
    def _map_regime(score):
        if score > 0.5:
            return "Aggressively Accommodative"
        if score > 0:
            return "Accommodative"
        if score > -0.5:
            return "Restrictive"
        return "Aggressively Tight"

    def run(self):
        country_config = SERIES_CONFIG.get(self.country, {})
        monetary_config = country_config.get("monetary", {})

        if not monetary_config:
            return 0

        role_to_indicator = {}
        for name, cfg in monetary_config.items():
            role_to_indicator[cfg.get("role", name)] = (name, cfg)

        required_roles = ["fed_rate", "cpi_core", "fed_assets", "gdp", "m2"]
        missing_roles = [r for r in required_roles if r not in role_to_indicator]
        if missing_roles:
            self.details.append({
                "status": "skipped",
                "reason": f"Missing monetary roles in config: {', '.join(missing_roles)}",
            })
            return 0

        try:
            fed_rate_name, fed_rate_cfg = role_to_indicator["fed_rate"]
            cpi_name, cpi_cfg = role_to_indicator["cpi_core"]
            assets_name, assets_cfg = role_to_indicator["fed_assets"]
            gdp_name, gdp_cfg = role_to_indicator["gdp"]
            m2_name, m2_cfg = role_to_indicator["m2"]

            fed_rate = self.provider.get_series(self.country, fed_rate_cfg)
            cpi = self.provider.get_series(self.country, cpi_cfg)
            fed_assets = self.provider.get_series(self.country, assets_cfg)
            gdp = self.provider.get_series(self.country, gdp_cfg)
            m2 = self.provider.get_series(self.country, m2_cfg)

            fed_rate_m = fed_rate.resample("ME").last()
            cpi_m = cpi.resample("ME").last()
            fed_assets_m = fed_assets.resample("ME").last()
            m2_m = m2.resample("ME").last()
            gdp_monthly = gdp.resample("ME").ffill()

            cpi_yoy = cpi_m.pct_change(12, fill_method=None) * 100
            real_rate = fed_rate_m - cpi_yoy
            rate_6m_change = fed_rate_m.diff(6)
            rate_combined = 0.6 * real_rate + 0.4 * rate_6m_change
            rate_z = -_smart_zscore_raw(rate_combined)

            bs_pct_gdp = fed_assets_m / gdp_monthly
            bs_6m_change = bs_pct_gdp.pct_change(6, fill_method=None)
            bs_z = _smart_zscore_raw(bs_6m_change)

            m2_yoy = m2_m.pct_change(12, fill_method=None) * 100
            m2_6m_ann = ((m2_m / m2_m.shift(6)) ** 2 - 1) * 100
            m2_combined = 0.6 * m2_yoy + 0.4 * m2_6m_ann
            m2_z = _smart_zscore_raw(m2_combined)

            df = pd.DataFrame({
                "real_rate_z": rate_z,
                "balance_sheet_z": bs_z,
                "m2_z": m2_z,
            }).dropna()

            if df.empty:
                raise ValueError("No overlapping monthly observations after monetary transforms")

            df["policy_raw"] = (
                0.4 * df["real_rate_z"] +
                0.3 * df["balance_sheet_z"] +
                0.3 * df["m2_z"]
            ).clip(-3, 3)
            df["policy_score"] = df["policy_raw"] / 3

            last = df.iloc[-1]
            self.score = float(last["policy_score"])
            regime = self._map_regime(self.score)

            self.details.append({
                "status": "used",
                "score": self.score,
                "regime": regime,
                "fed_rate_indicator": fed_rate_name,
                "cpi_indicator": cpi_name,
                "assets_indicator": assets_name,
                "gdp_indicator": gdp_name,
                "m2_indicator": m2_name,
                "real_rate_z": float(last["real_rate_z"]),
                "balance_sheet_z": float(last["balance_sheet_z"]),
                "m2_z": float(last["m2_z"]),
                "policy_raw": float(last["policy_raw"]),
            })
            return self.score
        except Exception as exc:
            self.details.append({
                "status": "skipped",
                "reason": str(exc),
            })
            return 0
