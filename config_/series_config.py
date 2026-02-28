# config/series_config.py

SERIES_CONFIG = {
    "USD": {
        "growth": {
            "pmi": {
                "source": "excel",
                "sheet": "PMI",
                "code": "US_PMI",
                "weight": 0.3,
                "calc_type": "level_3m_change"
            },
            "nmi": {
                "source": "excel",
                "sheet": "NMI",
                "code": "US_NMI",
                "weight": 0.2,
                "calc_type": "level_3m_change"
            },
            "umcsent": {
                "source": "fred",
                "code": "UMCSENT",
                "weight": 0.3,
                "calc_type": "level_3m_change"
            },
            "permits": {
                "source": "fred",
                "code": "HOUST",
                "weight": 0.2,
                "calc_type": "permits_yoy_3m_change"
            }
        },
        "inflation": {
            "cpi": {
                "source": "fred",
                "code": "CPIAUCSL",
                "target": 2.0,
                "weight": 1.0
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
