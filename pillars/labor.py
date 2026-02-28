import numpy as np
import pandas as pd

from config_.series_config import SERIES_CONFIG
from core.standardization import rolling_zscore, smooth_compress, quantile_regime, REGIME_LABELS


class LaborPillar:

    def __init__(self, country, provider):
        self.country = country
        self.provider = provider
        self.score = 0.0
        self.score_series = pd.Series(dtype=float)
        self.details = []

    def run(self):
        country_config = SERIES_CONFIG.get(self.country, {})
        labor_config = country_config.get("labor", {})

        if not labor_config:
            return float("nan")

        role_to_indicator = {}
        for name, cfg in labor_config.items():
            role_to_indicator[cfg.get("role", name)] = (name, cfg)

        base_weights = {"nfp": 0.4, "ahe": 0.3, "unrate": 0.3}
        component_series = {}

        for role in ["nfp", "ahe", "unrate"]:
            if role not in role_to_indicator:
                continue
            name, cfg = role_to_indicator[role]
            try:
                s = self.provider.get_series(self.country, cfg).dropna().astype(float)

                if role == "nfp":
                    derived = s.diff().rolling(3).mean()
                elif role == "ahe":
                    ahe_yoy = s.pct_change(12) * 100
                    ahe_3m_ann = ((s / s.shift(3)) ** 4 - 1) * 100
                    derived = 0.6 * ahe_yoy + 0.4 * ahe_3m_ann
                else:
                    unrate_6m_change = s.diff(6)
                    derived = 0.6 * (-s) + 0.4 * (-unrate_6m_change)

                component_series[role] = rolling_zscore(derived.dropna())

            except Exception as exc:
                self.details.append({
                    "status": "skipped",
                    "reason": f"Failed {role} ({name}): {exc}",
                })

        if len(component_series) < 2:
            self.details.append({
                "status": "skipped",
                "reason": f"Fewer than 2 labor components available: {list(component_series.keys())}",
            })
            return float("nan")

        df = pd.concat(component_series, axis=1).dropna()
        if df.empty:
            self.details.append({"status": "skipped", "reason": "No overlapping labor observations"})
            return float("nan")

        avail = list(df.columns)
        total_w = sum(base_weights[r] for r in avail if r in base_weights)
        labor_raw = sum(
            (base_weights[r] / total_w) * df[r]
            for r in avail if r in base_weights
        )
        labor_score_series = smooth_compress(labor_raw)
        self.score_series = labor_score_series.dropna()

        if self.score_series.empty:
            return float("nan")

        self.score = float(self.score_series.iloc[-1])
        regime_series = quantile_regime(self.score_series)
        rv = regime_series.dropna()
        current_regime = rv.iloc[-1] if not rv.empty else 0
        regime_label = REGIME_LABELS.get(
            int(current_regime) if not pd.isna(current_regime) else 0, "Neutral"
        )

        last = df.iloc[-1]
        self.details.append({
            "status": "used",
            "score": self.score,
            "regime": regime_label,
            "nfp_z": float(last["nfp"]) if "nfp" in last.index else float("nan"),
            "ahe_z": float(last["ahe"]) if "ahe" in last.index else float("nan"),
            "unrate_z": float(last["unrate"]) if "unrate" in last.index else float("nan"),
        })

        return self.score
