import pandas as pd
import requests


FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"


class DataProvider:
    def get_series(self, country, series_config):
        raise NotImplementedError


# ========================
# FRED PROVIDER
# ========================

class FREDProvider(DataProvider):

    def __init__(self, api_key):
        self.api_key = api_key

    def get_series(self, country, series_config):
        series_id = series_config["code"]

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
        }

        r = requests.get(FRED_API_URL, params=params, timeout=30)
        r.raise_for_status()

        obs = r.json().get("observations", [])
        vals = [(o["date"], o["value"]) for o in obs if o["value"] != "."]

        if not vals:
            raise ValueError(f"No data returned for {series_id}")

        series = pd.Series(
            [float(v) for _, v in vals],
            index=pd.to_datetime([d for d, _ in vals])
        )

        return series.sort_index()


# ========================
# EXCEL PROVIDER
# ========================

class ExcelProvider(DataProvider):

    def __init__(self, file):
        self.file = file
        try:
            self.excel = pd.ExcelFile(file, engine="openpyxl") if file else None
        except ImportError as exc:
            raise RuntimeError(
                "Excel upload requires the 'openpyxl' package. "
                "Add openpyxl to deployment dependencies."
            ) from exc

    def get_series(self, country, series_config):

        if self.excel is None:
            raise ValueError("Excel provider not initialized")

        sheet = series_config["sheet"]
        column = series_config["column"]

        df = pd.read_excel(self.excel, sheet_name=sheet)

        if "Date" not in df.columns:
            raise ValueError(f"'Date' column missing in sheet {sheet}")

        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")

        if column not in df.columns:
            raise ValueError(f"{column} not found in sheet {sheet}")

        return df[column].dropna().sort_index()


# ========================
# HYBRID PROVIDER
# ========================

class HybridProvider(DataProvider):

    def __init__(self, fred_provider=None, excel_provider=None):
        self.fred = fred_provider
        self.excel = excel_provider

    def get_series(self, country, series_config):
        source = series_config["source"]

        if source == "fred":
            return self.fred.get_series(country, series_config)

        elif source == "excel":
            if self.excel is None:
                raise ValueError("Excel provider not initialized")
            return self.excel.get_series(country, series_config)

        else:
            raise ValueError("Unknown data source")
