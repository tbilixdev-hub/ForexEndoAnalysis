# config.py

WEIGHTS = {
    "growth": 0.25,
    "inflation": 0.25,
    "labor": 0.10,
    "monetary": 0.30,
    "fiscal": 0.10
}

COUNTRIES = ["USD", "EUR", "JPY", "GBP", "CAD", "AUD", "CHF", "NOK", "SEK", "NZD"]

MASTER_FREQUENCY = "M"

FRED_API_KEY = "8f91577c37e15642305321c74edcddf3"

SERIES_CONFIG = {
    "USD": {
        "fed_funds": {"source": "fred", "code": "FEDFUNDS"},
        "cpi": {"source": "fred", "code": "CPILFESL"},
        "pmi": {"source": "excel", "sheet": "PMI", "column": "USD_PMI"},
        "nmi": {"source": "excel", "sheet": "NMI", "column": "USD_NMI"},
        "umcsent": {"source": "fred", "code": "UMCSENT"},
        "permits": {"source": "fred", "code": "PERMIT"},
    }
}