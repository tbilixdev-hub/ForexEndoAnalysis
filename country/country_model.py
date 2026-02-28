from config import WEIGHTS
from pillars.growth import GrowthPillar
from pillars.inflation import InflationPillar


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

        self.pillar_scores = {
            "growth": growth,
            "inflation": inflation,
            "labor": 0,
            "monetary": 0,
            "fiscal": 0
        }
        self.details["growth"] = growth_pillar.details
        self.details["inflation"] = inflation_pillar.details

    def aggregate(self):
        total = 0
        for k, v in self.pillar_scores.items():
            total += WEIGHTS[k] * v
        self.internal_score = total

    def run(self):
        self.compute_pillars()
        self.aggregate()
        return self.internal_score
