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
            "core_cpi": {
                "source": "fred",
                "code": "CPILFESL",
                "target": 2.0,
                "weight": 0.6
            },
            "core_ppi": {
                "source": "fred",
                "code": "PPIFID",
                "target": 2.0,
                "weight": 0.4
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
        },
        "fiscal": {
            "debt_gdp": {
                "source": "fred",
                "code": "GFDEGDQ188S",
                "role": "debt_gdp"
            },
            "deficit_gdp": {
                "source": "fred",
                "code": "FYFSGDA188S",
                "role": "deficit_gdp"
            },
            "interest_gdp": {
                "source": "fred",
                "code": "A091RC1Q027SBEA",
                "role": "interest_gdp"
            },
            "receipts": {
                "source": "fred",
                "code": "FYFRGDA188S",
                "role": "receipts"
            },
            "yield10": {
                "source": "fred",
                "code": "DGS10",
                "role": "yield10"
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
