import numpy as np
import pandas as pd

from config_.series_config import SERIES_CONFIG
from core.standardization import (
    rolling_zscore, smooth_compress, quantile_regime, weighted_nanmean, REGIME_LABELS,
)

# Annual series (e.g. fiscal-year deficit) can lag the latest month by up to ~2 years.
MAX_FFILL_MONTHS = 24


class FiscalPillar:

    def __init__(self, country, provider):
        self.country = country
        self.provider = provider
        self.score = float("nan")
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

        def monthly(role):
            _, cfg = role_to_indicator[role]
            raw = self.provider.get_series(self.country, cfg)
            return raw.resample("ME").last().ffill().dropna()

        def add(name, fn):
            try:
                components[name] = fn()
            except Exception as exc:
                self.details.append({"status": "skipped", "reason": f"Failed {name}: {exc}"})

        def has(*roles):
            return all(r in role_to_indicator for r in roles)

        # Higher debt/GDP is a negative.
        if has("debt_gdp"):
            add("debt_gdp", lambda: -rolling_zscore(monthly("debt_gdp")))

        # Surplus(+)/deficit(-) as % of GDP: a larger balance is a positive.
        if has("deficit_gdp"):
            add("deficit_gdp", lambda: rolling_zscore(monthly("deficit_gdp")))

        # Interest outlays and GDP are both nominal $ (SAAR), so their ratio is % of GDP.
        interest_gdp = None
        if has("interest", "gdp"):
            try:
                interest = monthly("interest")
                gdp = monthly("gdp")
                interest_gdp = (interest / gdp.reindex(interest.index, method="ffill") * 100).dropna()
                components["interest_gdp"] = -rolling_zscore(interest_gdp)
            except Exception as exc:
                self.details.append({"status": "skipped", "reason": f"Failed interest_gdp: {exc}"})

        # Receipts (% of GDP) per unit of interest outlays (% of GDP): coverage ratio.
        if interest_gdp is not None and has("receipts"):
            def liquidity():
                receipts = monthly("receipts")
                aligned = receipts.reindex(interest_gdp.index.union(receipts.index)).ffill()
                return rolling_zscore((aligned / interest_gdp).dropna())
            add("liquidity", liquidity)

        if has("yield10"):
            add("yield10", lambda: -rolling_zscore(monthly("yield10").diff(6).dropna()))

        if len(components) < 2:
            self.details.append({
                "status": "skipped",
                "reason": f"Fewer than 2 fiscal components available: {list(components.keys())}",
            })
            return float("nan")

        # Carry low-frequency (annual/quarterly) components forward so the composite
        # isn't truncated to the date of the slowest series.
        component_df = pd.concat(components, axis=1, sort=True).ffill(limit=MAX_FFILL_MONTHS)
        weights = [component_weights.get(c, 0) for c in component_df.columns]
        fiscal_raw = weighted_nanmean(component_df, weights, min_count=2).dropna()
        if fiscal_raw.empty:
            self.details.append({"status": "skipped", "reason": "No overlapping fiscal observations"})
            return float("nan")
        component_df = component_df.loc[fiscal_raw.index]

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
