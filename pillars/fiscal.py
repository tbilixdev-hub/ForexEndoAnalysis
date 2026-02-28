import numpy as np
import pandas as pd

from config_.series_config import SERIES_CONFIG
from core.standardization import rolling_zscore, smooth_compress, quantile_regime, REGIME_LABELS


class FiscalPillar:

    def __init__(self, country, provider):
        self.country = country
        self.provider = provider
        self.score = 0.0
        self.score_series = pd.Series(dtype=float)
        self.details = []

    def run(self):
        country_config = SERIES_CONFIG.get(self.country, {})
        fiscal_config = country_config.get("fiscal", {})

        if not fiscal_config:
            return float("nan")

        role_to_indicator = {}
        for name, cfg in fiscal_config.items():
            role_to_indicator[cfg.get("role", name)] = (name, cfg)

        component_weights = {
            "debt_gdp": 0.25,
            "deficit_gdp": 0.20,
            "interest_gdp": 0.20,
            "liquidity": 0.20,
            "yield10": 0.15,
        }
        components = {}

        for role in ["debt_gdp", "deficit_gdp", "interest_gdp"]:
            if role not in role_to_indicator:
                continue
            try:
                _, cfg = role_to_indicator[role]
                raw = self.provider.get_series(self.country, cfg).resample("ME").ffill().dropna()
                components[role] = -rolling_zscore(raw)
            except Exception:
                pass

        if "yield10" in role_to_indicator:
            try:
                _, cfg = role_to_indicator["yield10"]
                raw = self.provider.get_series(self.country, cfg).resample("ME").last()
                yield_6m_change = raw.diff(6).dropna()
                components["yield10"] = -rolling_zscore(yield_6m_change)
            except Exception:
                pass

        receipts_series = None
        if "receipts" in role_to_indicator:
            try:
                _, receipts_cfg = role_to_indicator["receipts"]
                receipts_series = self.provider.get_series(self.country, receipts_cfg).resample("ME").ffill()
            except Exception:
                pass

        if receipts_series is not None and "interest_gdp" in role_to_indicator:
            try:
                _, interest_cfg = role_to_indicator["interest_gdp"]
                interest_series = self.provider.get_series(self.country, interest_cfg).resample("ME").ffill()
                liquidity_cover = (receipts_series / interest_series).dropna()
                components["liquidity"] = rolling_zscore(liquidity_cover)
            except Exception:
                pass

        if len(components) < 2:
            self.details.append({
                "status": "skipped",
                "reason": f"Fewer than 2 fiscal components available: {list(components.keys())}",
            })
            return float("nan")

        component_df = pd.concat(components, axis=1).dropna()
        if component_df.empty:
            self.details.append({"status": "skipped", "reason": "No overlapping fiscal observations"})
            return float("nan")

        avail = list(component_df.columns)
        total_w = sum(component_weights.get(c, 0) for c in avail)
        if total_w == 0:
            return float("nan")
        fiscal_raw = sum(
            (component_weights.get(c, 0) / total_w) * component_df[c]
            for c in avail
        )
        fiscal_score_series = smooth_compress(fiscal_raw)
        self.score_series = fiscal_score_series.dropna()

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
            "debt_z": float(last["debt_gdp"]) if "debt_gdp" in last.index else float("nan"),
            "deficit_z": float(last["deficit_gdp"]) if "deficit_gdp" in last.index else float("nan"),
            "interest_z": float(last["interest_gdp"]) if "interest_gdp" in last.index else float("nan"),
            "liquidity_z": float(last["liquidity"]) if "liquidity" in last.index else float("nan"),
            "yield_z": float(last["yield10"]) if "yield10" in last.index else float("nan"),
        })

        return self.score
