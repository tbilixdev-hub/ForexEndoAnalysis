import numpy as np
import pandas as pd

from config import WEIGHTS
from pillars.growth import GrowthPillar
from pillars.inflation import InflationPillar
from pillars.labor import LaborPillar
from pillars.monetary import MonetaryPillar
from pillars.fiscal import FiscalPillar


def geometric_aggregate(pillars_dict, weights_dict):
    result = 1.0
    for k, v in pillars_dict.items():
        if pd.isna(v):
            continue
        result *= (1 + v) ** weights_dict[k]
    return result - 1


def sensitivity_test(pillars_dict, base_weights):
    results = {}
    for key in base_weights:
        for delta in [-0.1, 0.1]:
            new_weights = base_weights.copy()
            new_weights[key] += delta
            total = sum(new_weights.values())
            for k in new_weights:
                new_weights[k] /= total
            score = geometric_aggregate(pillars_dict, new_weights)
            results[f"{key}_{delta:+.1f}"] = score
    return results


class CountryModel:

    def __init__(self, country, provider):
        self.country = country
        self.provider = provider
        self.pillar_scores = {}
        self.internal_score = None
        self.details = {}
        self.correlation_matrix = None
        self.sensitivity_results = None

    def compute_pillars(self):
        growth_pillar = GrowthPillar(self.country, self.provider)
        growth_result = growth_pillar.run()
        growth_score = 0.5 * growth_result["growth_level"] + 0.5 * growth_result["growth_momentum"]

        inflation_pillar = InflationPillar(self.country, self.provider)
        inflation_score = inflation_pillar.run()

        labor_pillar = LaborPillar(self.country, self.provider)
        labor_score = labor_pillar.run()

        monetary_pillar = MonetaryPillar(self.country, self.provider)
        monetary_score = monetary_pillar.run()

        fiscal_pillar = FiscalPillar(self.country, self.provider)
        fiscal_score = fiscal_pillar.run()

        self.pillar_scores = {
            "growth": growth_score,
            "inflation": inflation_score,
            "labor": labor_score,
            "monetary": monetary_score,
            "fiscal": fiscal_score,
        }

        self.details["growth"] = growth_pillar.details
        self.details["growth_level"] = growth_pillar.growth_level_score
        self.details["growth_momentum"] = growth_pillar.growth_momentum_score
        self.details["inflation"] = inflation_pillar.details
        self.details["labor"] = labor_pillar.details
        self.details["monetary"] = monetary_pillar.details
        self.details["fiscal"] = fiscal_pillar.details

        pillar_series = {}
        for name, pillar in [
            ("growth", growth_pillar),
            ("inflation", inflation_pillar),
            ("labor", labor_pillar),
            ("monetary", monetary_pillar),
            ("fiscal", fiscal_pillar),
        ]:
            if hasattr(pillar, "score_series") and not pillar.score_series.empty:
                pillar_series[name] = pillar.score_series

        if len(pillar_series) >= 2:
            pillar_df = pd.DataFrame(pillar_series)
            self.correlation_matrix = pillar_df.corr()
            print(f"\n--- {self.country} Pillar Correlation Matrix ---")
            print(self.correlation_matrix)
        else:
            self.correlation_matrix = None

    def aggregate(self):
        self.internal_score = geometric_aggregate(self.pillar_scores, WEIGHTS)
        self.sensitivity_results = sensitivity_test(self.pillar_scores, WEIGHTS)

    def run(self):
        self.compute_pillars()
        self.aggregate()
        return self.internal_score
