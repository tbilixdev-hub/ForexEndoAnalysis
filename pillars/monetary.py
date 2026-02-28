import numpy as np
import pandas as pd

from config_.series_config import SERIES_CONFIG
from core.standardization import rolling_zscore, smooth_compress, quantile_regime, REGIME_LABELS


class MonetaryPillar:

    def __init__(self, country, provider):
        self.country = country
        self.provider = provider
        self.score = 0.0
        self.score_series = pd.Series(dtype=float)
        self.details = []

    def run(self):
        country_config = SERIES_CONFIG.get(self.country, {})
        monetary_config = country_config.get("monetary", {})

        if not monetary_config:
            return float("nan")

        role_to_indicator = {}
        for name, cfg in monetary_config.items():
            role_to_indicator[cfg.get("role", name)] = (name, cfg)

        components = {}

        if "fed_rate" in role_to_indicator and "cpi_core" in role_to_indicator:
            try:
                _, fed_rate_cfg = role_to_indicator["fed_rate"]
                _, cpi_cfg = role_to_indicator["cpi_core"]
                fed_rate_m = self.provider.get_series(self.country, fed_rate_cfg).resample("ME").last()
                cpi_m = self.provider.get_series(self.country, cpi_cfg).resample("ME").last()
                cpi_yoy = cpi_m.pct_change(12, fill_method=None) * 100
                real_rate = fed_rate_m - cpi_yoy
                rate_6m_change = fed_rate_m.diff(6)
                rate_combined = (0.6 * real_rate + 0.4 * rate_6m_change).dropna()
                components["real_rate"] = -rolling_zscore(rate_combined)
            except Exception:
                pass

        if "fed_assets" in role_to_indicator and "gdp" in role_to_indicator:
            try:
                _, assets_cfg = role_to_indicator["fed_assets"]
                _, gdp_cfg = role_to_indicator["gdp"]
                fed_assets_m = self.provider.get_series(self.country, assets_cfg).resample("ME").last()
                gdp_monthly = self.provider.get_series(self.country, gdp_cfg).resample("ME").ffill()
                bs_pct_gdp = fed_assets_m / gdp_monthly
                bs_6m_change = bs_pct_gdp.pct_change(6, fill_method=None).dropna()
                components["balance_sheet"] = rolling_zscore(bs_6m_change)
            except Exception:
                pass

        if "m2" in role_to_indicator:
            try:
                _, m2_cfg = role_to_indicator["m2"]
                m2_m = self.provider.get_series(self.country, m2_cfg).resample("ME").last()
                m2_yoy = m2_m.pct_change(12, fill_method=None) * 100
                m2_6m_ann = ((m2_m / m2_m.shift(6)) ** 2 - 1) * 100
                m2_combined = (0.6 * m2_yoy + 0.4 * m2_6m_ann).dropna()
                components["m2"] = rolling_zscore(m2_combined)
            except Exception:
                pass

        if len(components) < 2:
            self.details.append({
                "status": "skipped",
                "reason": f"Fewer than 2 monetary components available: {list(components.keys())}",
            })
            return float("nan")

        component_df = pd.concat(components, axis=1).dropna()
        if component_df.empty:
            self.details.append({"status": "skipped", "reason": "No overlapping monetary observations"})
            return float("nan")

        monetary_raw = component_df.mean(axis=1)
        monetary_score_series = smooth_compress(monetary_raw)
        self.score_series = monetary_score_series.dropna()

        if self.score_series.empty:
            return float("nan")

        self.score = float(self.score_series.iloc[-1])
        regime_series = quantile_regime(self.score_series)
        rv = regime_series.dropna()
        current_regime = rv.iloc[-1] if not rv.empty else 0
        regime_label = REGIME_LABELS.get(
            int(current_regime) if not pd.isna(current_regime) else 0, "Neutral"
        )

        last = component_df.iloc[-1]
        self.details.append({
            "status": "used",
            "score": self.score,
            "regime": regime_label,
            "real_rate_z": float(last["real_rate"]) if "real_rate" in last.index else float("nan"),
            "balance_sheet_z": float(last["balance_sheet"]) if "balance_sheet" in last.index else float("nan"),
            "m2_z": float(last["m2"]) if "m2" in last.index else float("nan"),
        })

        return self.score
