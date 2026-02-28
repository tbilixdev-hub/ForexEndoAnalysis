from config_.series_config import SERIES_CONFIG
from core.standardization import smart_zscore


class GrowthPillar:

    def __init__(self, country, provider):
        self.country = country
        self.provider = provider
        self.score = 0
        self.details = []

    def run(self):

        country_config = SERIES_CONFIG.get(self.country, {})
        growth_config = country_config.get("growth", {})

        if not growth_config:
            return 0  # no indicators defined

        weighted_scores = []
        total_weight = 0

        for name, indicator in growth_config.items():
            source = indicator.get("source", "unknown")
            weight = indicator.get("weight", 0)

            try:
                series = self.provider.get_series(self.country, indicator)
            except Exception as exc:
                self.details.append({
                    "indicator": name,
                    "source": source,
                    "weight": weight,
                    "status": "skipped",
                    "reason": str(exc)
                })
                continue  # skip missing data

            z = smart_zscore(series)

            if len(z.dropna()) == 0:
                self.details.append({
                    "indicator": name,
                    "source": source,
                    "weight": weight,
                    "status": "skipped",
                    "reason": "No valid z-score values"
                })
                continue

            latest_score = z.dropna().iloc[-1]
            weight = indicator["weight"]

            weighted_scores.append(latest_score * weight)
            total_weight += weight
            self.details.append({
                "indicator": name,
                "source": source,
                "weight": weight,
                "status": "used",
                "latest_score": float(latest_score)
            })

        if total_weight == 0:
            return 0

        self.score = sum(weighted_scores) / total_weight

        return self.score
