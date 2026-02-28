import numpy as np
import pandas as pd

from config_.series_config import SERIES_CONFIG
from core.standardization import rolling_zscore, smooth_compress, quantile_regime, REGIME_LABELS


def _weighted_nanmean(df, weights):
    weights_arr = np.array(weights, dtype=float)
    values = df.values.astype(float)
    mask = ~np.isnan(values)
    weighted_sum = np.where(mask, values * weights_arr, 0.0).sum(axis=1)
    weight_sum = (mask * weights_arr).sum(axis=1)
    weight_sum = np.where(weight_sum == 0, np.nan, weight_sum)
    return pd.Series(weighted_sum / weight_sum, index=df.index)


class GrowthPillar:

    def __init__(self, country, provider):
        self.country = country
        self.provider = provider
        self.score = 0.0
        self.score_series = pd.Series(dtype=float)
        self.details = []
        self.growth_level_score = 0.0
        self.growth_momentum_score = 0.0

    def run(self):
        country_config = SERIES_CONFIG.get(self.country, {})
        growth_config = country_config.get("growth", {})

        if not growth_config:
            return {"growth_level": 0.0, "growth_momentum": 0.0}

        level_series_list = []
        momentum_series_list = []
        weights_used = []

        for name, indicator in growth_config.items():
            source = indicator.get("source", "unknown")
            weight = indicator.get("weight", 0)
            calc_type = indicator.get("calc_type", "level_3m_change")

            try:
                raw = self.provider.get_series(self.country, indicator)
                s = raw.dropna().astype(float).resample("ME").last()

                if calc_type == "permits_yoy_3m_change":
                    level = (s / s.shift(12) - 1) * 100
                    level = level.dropna()
                    momentum = level.diff(3)
                else:
                    level = s
                    momentum = s.diff(3)

                level_series_list.append(level.rename(name))
                momentum_series_list.append(momentum.rename(name))
                weights_used.append(weight)

                self.details.append({
                    "indicator": name,
                    "source": source,
                    "weight": weight,
                    "status": "used",
                    "calc_type": calc_type,
                    "latest_level": float(level.dropna().iloc[-1]) if not level.dropna().empty else None,
                    "latest_momentum": float(momentum.dropna().iloc[-1]) if not momentum.dropna().empty else None,
                })

            except Exception as exc:
                self.details.append({
                    "indicator": name,
                    "source": source,
                    "weight": weight,
                    "status": "skipped",
                    "reason": str(exc),
                })

        if not level_series_list:
            return {"growth_level": 0.0, "growth_momentum": 0.0}

        level_df = pd.concat(level_series_list, axis=1)
        momentum_df = pd.concat(momentum_series_list, axis=1)

        growth_level_composite = _weighted_nanmean(level_df, weights_used)
        growth_momentum_composite = _weighted_nanmean(momentum_df, weights_used)

        growth_level_z = smooth_compress(rolling_zscore(growth_level_composite))
        growth_momentum_z = smooth_compress(rolling_zscore(growth_momentum_composite))

        score_series = (0.5 * growth_level_z + 0.5 * growth_momentum_z).dropna()
        self.score_series = score_series

        if score_series.empty:
            self.growth_level_score = 0.0
            self.growth_momentum_score = 0.0
            self.score = 0.0
            regime_label = "Neutral"
        else:
            lv = growth_level_z.dropna()
            mv = growth_momentum_z.dropna()
            self.growth_level_score = float(lv.iloc[-1]) if not lv.empty else 0.0
            self.growth_momentum_score = float(mv.iloc[-1]) if not mv.empty else 0.0
            self.score = 0.5 * self.growth_level_score + 0.5 * self.growth_momentum_score
            regime_series = quantile_regime(score_series)
            rv = regime_series.dropna()
            current_regime = rv.iloc[-1] if not rv.empty else 0
            regime_label = REGIME_LABELS.get(
                int(current_regime) if not pd.isna(current_regime) else 0, "Neutral"
            )

        for d in self.details:
            if d["status"] == "used":
                d["score"] = self.score
                d["zscore"] = self.score
                d["regime"] = regime_label

        return {
            "growth_level": self.growth_level_score,
            "growth_momentum": self.growth_momentum_score,
        }
