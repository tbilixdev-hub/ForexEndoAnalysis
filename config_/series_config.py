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
        },
        "labor": {
            "nfp": {
                "source": "fred",
                "code": "PAYEMS",
                "role": "nfp"
            },
            "ahe": {
                "source": "fred",
                "code": "CES0500000003",
                "role": "ahe"
            },
            "unrate": {
                "source": "fred",
                "code": "UNRATE",
                "role": "unrate"
            }
        },
        "monetary": {
            "fed_rate": {
                "source": "fred",
                "code": "FEDFUNDS",
                "role": "fed_rate"
            },
            "cpi_core": {
                "source": "fred",
                "code": "CPILFESL",
                "role": "cpi_core"
            },
            "fed_assets": {
                "source": "fred",
                "code": "WALCL",
                "role": "fed_assets"
            },
            "gdp": {
                "source": "fred",
                "code": "GDP",
                "role": "gdp"
            },
            "m2": {
                "source": "fred",
                "code": "M2SL",
                "role": "m2"
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
