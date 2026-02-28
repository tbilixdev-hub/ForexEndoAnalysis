import numpy as np
import pandas as pd

from config_.series_config import SERIES_CONFIG
from core.standardization import rolling_zscore, smooth_compress, quantile_regime, REGIME_LABELS


class InflationPillar:

    def __init__(self, country, provider):
        self.country = country
        self.provider = provider
        self.score = 0.0
        self.score_series = pd.Series(dtype=float)
        self.details = []

    def run(self):
        country_config = SERIES_CONFIG.get(self.country, {})
        inflation_config = country_config.get("inflation", {})

        if not inflation_config:
            return 0.0

        raw_series_list = []
        weight_list = []

        for name, indicator in inflation_config.items():
            source = indicator.get("source", "unknown")
            weight = indicator.get("weight", 1.0)
            target = indicator.get("target", 2.0)

            try:
                series = self.provider.get_series(self.country, indicator)
                s = series.dropna().astype(float)

                yoy = s.pct_change(12) * 100
                m3_ann = ((s / s.shift(3)) ** 4 - 1) * 100

                inflation_level = yoy - target
                inflation_momentum = m3_ann
                inflation_raw = (0.5 * inflation_level + 0.5 * inflation_momentum).dropna()

                raw_series_list.append((inflation_raw.rename(name), weight))
                self.details.append({
                    "indicator": name,
                    "source": source,
                    "weight": weight,
                    "status": "used",
                    "target": target,
                    "yoy": float(yoy.dropna().iloc[-1]) if not yoy.dropna().empty else None,
                    "m3_ann": float(m3_ann.dropna().iloc[-1]) if not m3_ann.dropna().empty else None,
                })

            except Exception as exc:
                self.details.append({
                    "indicator": name,
                    "source": source,
                    "weight": weight,
                    "status": "skipped",
                    "reason": str(exc),
                })

        if not raw_series_list:
            return 0.0

        total_weight = sum(w for _, w in raw_series_list)
        combined_df = pd.concat([s for s, _ in raw_series_list], axis=1)
        weights_norm = [w / total_weight for _, w in raw_series_list]
        combined = combined_df.mul(weights_norm).sum(axis=1, min_count=1).dropna()

        inflation_score_series = smooth_compress(rolling_zscore(combined)).dropna()
        self.score_series = inflation_score_series

        if inflation_score_series.empty:
            self.score = 0.0
            regime_label = "Neutral"
        else:
            self.score = float(inflation_score_series.iloc[-1])
            regime_series = quantile_regime(inflation_score_series)
            rv = regime_series.dropna()
            current_regime = rv.iloc[-1] if not rv.empty else 0
            regime_label = REGIME_LABELS.get(
                int(current_regime) if not pd.isna(current_regime) else 0, "Neutral"
            )

        for d in self.details:
            if d["status"] == "used":
                d["score"] = self.score
                d["regime"] = regime_label

        return self.score
