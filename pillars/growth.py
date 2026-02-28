from config_.series_config import SERIES_CONFIG
import numpy as np
import pandas as pd

try:
    from scipy.stats import skew as _scipy_skew
    from scipy.stats import kurtosis as _scipy_kurtosis
except Exception:
    _scipy_skew = None
    _scipy_kurtosis = None


def _skew(values):
    if _scipy_skew is not None:
        return float(_scipy_skew(values))
    return float(pd.Series(values).skew())


def _kurtosis_fisher(values):
    if _scipy_kurtosis is not None:
        return float(_scipy_kurtosis(values))
    return float(pd.Series(values).kurt())


class GrowthPillar:

    def __init__(self, country, provider):
        self.country = country
        self.provider = provider
        self.score = 0
        self.details = []

    @staticmethod
    def _safe_std(values):
        std_val = float(np.std(values))
        return std_val if std_val > 0 else None

    @staticmethod
    def _safe_mad(values):
        values = list(values)
        if not values:
            return None
        med = float(np.median(values))
        mad = 1.4826 * float(np.median([abs(v - med) for v in values]))
        return mad if mad > 0 else None

    def _adaptive_zscore(self, current_value, historical_values, change_values):
        hist_array = np.array(historical_values, dtype=float)
        change_array = np.array(change_values, dtype=float)

        mean_level = float(np.mean(hist_array))
        std_level = self._safe_std(hist_array)
        standard_z_level = (
            (float(current_value) - mean_level) / std_level if std_level is not None else 0.0
        )

        if len(hist_array) >= 2:
            level_changes = np.diff(hist_array)
            mad_level = self._safe_mad(level_changes)
            robust_z_level = (
                (float(current_value) - float(hist_array[-2])) / mad_level
                if mad_level is not None else standard_z_level
            )
        else:
            robust_z_level = standard_z_level

        skew_level = _skew(hist_array)
        kurt_level = _kurtosis_fisher(hist_array)
        z_level = robust_z_level if abs(skew_level) > 0.5 or abs(kurt_level) > 4 else standard_z_level

        if len(change_array) == 0:
            z_change = 0.0
            standard_z_change = 0.0
            robust_z_change = 0.0
            skew_change = 0.0
            kurt_change = 0.0
        else:
            mean_change = float(np.mean(change_array))
            std_change = self._safe_std(change_array)
            latest_change = float(change_array[-1])
            standard_z_change = (
                (latest_change - mean_change) / std_change if std_change is not None else 0.0
            )

            mad_change = self._safe_mad(change_array)
            median_change = float(np.median(change_array))
            robust_z_change = (
                (latest_change - median_change) / mad_change
                if mad_change is not None else standard_z_change
            )

            skew_change = _skew(change_array)
            kurt_change = _kurtosis_fisher(change_array)
            z_change = (
                robust_z_change
                if abs(skew_change) > 0.5 or abs(kurt_change) > 4
                else standard_z_change
            )

        z_final = 0.6 * z_level + 0.4 * z_change
        return float(z_final), {
            "z_level": float(z_level),
            "z_change": float(z_change),
            "standard_z_level": float(standard_z_level),
            "robust_z_level": float(robust_z_level),
            "standard_z_change": float(standard_z_change),
            "robust_z_change": float(robust_z_change),
            "skew_level": float(skew_level),
            "kurt_level": float(kurt_level),
            "skew_change": float(skew_change),
            "kurt_change": float(kurt_change),
        }

    @staticmethod
    def _regime_from_zscore(zscore):
        if zscore <= -1.5:
            return "Extremly bearish", -1.0
        if zscore <= -0.9:
            return "Bearish", -0.6
        if zscore <= -0.3:
            return "Mildy bearish", -0.3
        if zscore <= 0.3:
            return "Neutral", 0.0
        if zscore <= 0.9:
            return "Mildly Bullish", 0.3
        if zscore <= 1.5:
            return "Bulish", 0.6
        return "Extremly Bullish", 1.0

    def _build_growth_inputs(self, series, calc_type):
        s = series.dropna().astype(float)
        if len(s) < 4:
            raise ValueError("Not enough history for growth calculation")

        if calc_type == "permits_yoy_3m_change":
            yoy = (s / s.shift(12) - 1) * 100
            yoy = yoy.dropna()
            if yoy.empty:
                raise ValueError("Not enough history for permits YoY")
            change = (yoy - yoy.shift(3)).dropna()
            current_value = yoy.iloc[-1]
            report_change = change.iloc[-1] if not change.empty else 0.0
            return current_value, yoy.values, change.values, report_change

        change = s.diff(3).dropna()
        current_value = s.iloc[-1]
        report_change = current_value - s.iloc[-4]
        return current_value, s.values, change.values, report_change

    def run(self):

        country_config = SERIES_CONFIG.get(self.country, {})
        growth_config = country_config.get("growth", {})

        if not growth_config:
            return 0  # no indicators defined

        weighted_scores = []
        total_weight = 0

        for name, indicator in growth_config.items():
            source = indicator.get("source", "unknown")
            weight = indicator.get("weight", 0)
            calc_type = indicator.get("calc_type", "level_3m_change")

            try:
                series = self.provider.get_series(self.country, indicator)
            except Exception as exc:
                self.details.append({
                    "indicator": name,
                    "source": source,
                    "weight": weight,
                    "status": "skipped",
                    "reason": str(exc)
                })
                continue  # skip missing data

            try:
                current_value, historical_values, change_values, report_change = (
                    self._build_growth_inputs(series, calc_type)
                )
                zscore, z_details = self._adaptive_zscore(
                    current_value=current_value,
                    historical_values=historical_values,
                    change_values=change_values,
                )
                regime, indicator_score = self._regime_from_zscore(zscore)
            except Exception as exc:
                self.details.append({
                    "indicator": name,
                    "source": source,
                    "weight": weight,
                    "status": "skipped",
                    "reason": str(exc)
                })
                continue

            weighted_scores.append(indicator_score * weight)
            total_weight += weight
            self.details.append({
                "indicator": name,
                "source": source,
                "weight": weight,
                "status": "used",
                "value": float(current_value),
                "ma3_change": float(report_change),
                "zscore": float(zscore),
                "regime": regime,
                "score": float(indicator_score),
                "weighted_score": float(indicator_score * weight),
                "z_details": z_details,
            })

        if total_weight == 0:
            return 0

        self.score = sum(weighted_scores) / total_weight

        return self.score
