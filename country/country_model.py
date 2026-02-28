from config import WEIGHTS
from pillars.growth import GrowthPillar


class CountryModel:

    def __init__(self, country, provider):
        self.country = country
        self.provider = provider
        self.pillar_scores = {}
        self.internal_score = None

    def compute_pillars(self):

        growth = GrowthPillar(self.country, self.provider).run()

        self.pillar_scores = {
            "growth": growth,
            "inflation": 0,
            "labor": 0,
            "monetary": 0,
            "fiscal": 0
        }

    def aggregate(self):
        total = 0
        for k, v in self.pillar_scores.items():
            total += WEIGHTS[k] * v
        self.internal_score = total

    def run(self):
        self.compute_pillars()
        self.aggregate()
        return self.internal_score