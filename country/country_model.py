from config import WEIGHTS
from pillars.growth import GrowthPillar
from pillars.inflation import InflationPillar
from pillars.labor import LaborPillar
from pillars.monetary import MonetaryPillar
from pillars.fiscal import FiscalPillar


class CountryModel:

    def __init__(self, country, provider):
        self.country = country
        self.provider = provider
        self.pillar_scores = {}
        self.internal_score = None
        self.details = {}

    def compute_pillars(self):

        growth_pillar = GrowthPillar(self.country, self.provider)
        growth = growth_pillar.run()
        inflation_pillar = InflationPillar(self.country, self.provider)
        inflation = inflation_pillar.run()
        labor_pillar = LaborPillar(self.country, self.provider)
        labor = labor_pillar.run()
        monetary_pillar = MonetaryPillar(self.country, self.provider)
        monetary = monetary_pillar.run()
        fiscal_pillar = FiscalPillar(self.country, self.provider)
        fiscal = fiscal_pillar.run()

        self.pillar_scores = {
            "growth": growth,
            "inflation": inflation,
            "labor": labor,
            "monetary": monetary,
            "fiscal": fiscal
        }
        self.details["growth"] = growth_pillar.details
        self.details["inflation"] = inflation_pillar.details
        self.details["labor"] = labor_pillar.details
        self.details["monetary"] = monetary_pillar.details
        self.details["fiscal"] = fiscal_pillar.details

    def aggregate(self):
        total = 0
        for k, v in self.pillar_scores.items():
            total += WEIGHTS[k] * v
        self.internal_score = total

    def run(self):
        self.compute_pillars()
        self.aggregate()
        return self.internal_score
