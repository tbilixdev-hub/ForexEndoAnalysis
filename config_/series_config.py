# config/series_config.py

SERIES_CONFIG = {
    "USD": {
        "growth": {
            "pmi": {
                "source": "excel",      # change to "fred" later if needed
                "code": "US_PMI",
                "weight": 0.5
            },
            "industrial_production": {
                "source": "fred",
                "code": "INDPRO",
                "weight": 0.5
            }
        }
    },

    "EUR": {},
    "JPY": {},
    "GBP": {},
    "CAD": {},
    "AUD": {},
    "CHF": {},
    "NOK": {},
    "SEK": {},
    "NZD": {}
}