import numpy as np
import pandas as pd

from config_.series_config import SERIES_CONFIG
from core.standardization import (
    rolling_zscore, smooth_compress, quantile_regime, weighted_nanmean, REGIME_LABELS,
)


class GrowthPillar:

    def __init__(self, country, provider):
        self.country = country
        self.provider = provider
        self.score = float("nan")
        self.score_series = pd.Series(dtype=float)
        self.details = []
        self.growth_level_score = float("nan")
        self.growth_momentum_score = float("nan")

    def run(self):
        country_config = SERIES_CONFIG.get(self.country, {})
        growth_config = country_config.get("growth", {})

        if not growth_config:
            return {"growth_level": float("nan"), "growth_momentum": float("nan")}

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

                # Standardize each indicator before combining: raw levels are on
                # different scales (PMI ~50, sentiment ~70, permits YoY %).
                level_series_list.append(rolling_zscore(level).rename(name))
                momentum_series_list.append(rolling_zscore(momentum.dropna()).rename(name))
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
            return {"growth_level": float("nan"), "growth_momentum": float("nan")}

        level_df = pd.concat(level_series_list, axis=1)
        momentum_df = pd.concat(momentum_series_list, axis=1)

        growth_level_z = smooth_compress(weighted_nanmean(level_df, weights_used))
        growth_momentum_z = smooth_compress(weighted_nanmean(momentum_df, weights_used))

        score_series = (0.5 * growth_level_z + 0.5 * growth_momentum_z).dropna()
        self.score_series = score_series

        if score_series.empty:
            regime_label = "N/A"
        else:
            lv = growth_level_z.dropna()
            mv = growth_momentum_z.dropna()
            self.growth_level_score = float(lv.iloc[-1]) if not lv.empty else float("nan")
            self.growth_momentum_score = float(mv.iloc[-1]) if not mv.empty else float("nan")
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
