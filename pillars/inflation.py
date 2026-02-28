import numpy as np
import pandas as pd

from config_.series_config import SERIES_CONFIG


def _expanding_zscore(series):
    mean = series.expanding().mean()
    std = series.expanding().std(ddof=0)
    std = std.replace(0, np.nan)
    return (series - mean) / std


class InflationPillar:

    def __init__(self, country, provider):
        self.country = country
        self.provider = provider
        self.score = 0
        self.details = []

    @staticmethod
    def _inflation_block(series, target=None):
        yoy = series.pct_change(12) * 100
        m3_ann = ((series / series.shift(3)) ** 4 - 1) * 100
        accel = yoy.diff(3)

        df = pd.DataFrame({
            "yoy": yoy,
            "m3_ann": m3_ann,
            "accel": accel,
        }).dropna()

        if target is not None:
            df["yoy"] = df["yoy"] - target

        df["z_yoy"] = _expanding_zscore(df["yoy"])
        df["z_m3"] = _expanding_zscore(df["m3_ann"])
        df["z_accel"] = _expanding_zscore(df["accel"])

        df["block_score_raw"] = (
            0.4 * df["z_yoy"] +
            0.4 * df["z_m3"] +
            0.2 * df["z_accel"]
        ).clip(-3, 3)
        df["block_score"] = df["block_score_raw"] / 3
        return df

    def run(self):
        country_config = SERIES_CONFIG.get(self.country, {})
        inflation_config = country_config.get("inflation", {})

        if not inflation_config:
            return 0

        weighted_scores = []
        total_weight = 0

        for name, indicator in inflation_config.items():
            source = indicator.get("source", "unknown")
            weight = indicator.get("weight", 1.0)
            target = indicator.get("target")

            try:
                series = self.provider.get_series(self.country, indicator)
                block_df = self._inflation_block(series, target=target)
                if block_df.empty or block_df["block_score"].dropna().empty:
                    raise ValueError("No valid inflation block score values")
                latest = block_df.dropna().iloc[-1]
                indicator_score = float(latest["block_score"])
            except Exception as exc:
                self.details.append({
                    "indicator": name,
                    "source": source,
                    "weight": weight,
                    "status": "skipped",
                    "reason": str(exc),
                })
                continue

            weighted_scores.append(indicator_score * weight)
            total_weight += weight
            self.details.append({
                "indicator": name,
                "source": source,
                "weight": weight,
                "status": "used",
                "target": target,
                "yoy": float(latest["yoy"]),
                "m3_ann": float(latest["m3_ann"]),
                "accel": float(latest["accel"]),
                "z_yoy": float(latest["z_yoy"]),
                "z_m3": float(latest["z_m3"]),
                "z_accel": float(latest["z_accel"]),
                "score_raw": float(latest["block_score_raw"]),
                "score": indicator_score,
            })

        if total_weight == 0:
            return 0

        self.score = sum(weighted_scores) / total_weight
        return self.score
