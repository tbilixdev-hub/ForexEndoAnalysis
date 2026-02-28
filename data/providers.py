import pandas as pd
import requests
import time


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
        self._cache = {}

    def get_series(self, country, series_config):
        series_id = series_config["code"]

        if series_id in self._cache:
            return self._cache[series_id]

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
        }

        max_attempts = 4
        last_error = None
        for attempt in range(max_attempts):
            try:
                r = requests.get(FRED_API_URL, params=params, timeout=30)
                r.raise_for_status()
                break
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                if status == 429 and attempt < max_attempts - 1:
                    retry_after = exc.response.headers.get("Retry-After") if exc.response else None
                    try:
                        wait_seconds = float(retry_after) if retry_after is not None else (2 ** attempt)
                    except ValueError:
                        wait_seconds = float(2 ** attempt)
                    time.sleep(wait_seconds)
                    last_error = exc
                    continue
                raise
            except Exception as exc:
                last_error = exc
                if attempt < max_attempts - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise
        else:
            if last_error is not None:
                raise last_error
            raise RuntimeError(f"Failed to fetch FRED series {series_id}")

        obs = r.json().get("observations", [])
        vals = [(o["date"], o["value"]) for o in obs if o["value"] != "."]

        if not vals:
            raise ValueError(f"No data returned for {series_id}")

        series = pd.Series(
            [float(v) for _, v in vals],
            index=pd.to_datetime([d for d, _ in vals])
        )

        series = series.sort_index()
        self._cache[series_id] = series
        return series


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

        sheet = series_config.get("sheet", 0)
        column = series_config.get("column") or series_config.get("code")

        if column is None:
            raise ValueError(
                "Excel series config must include 'column' (or 'code' as alias)."
            )

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

    def __init__(self, fred_provider=None, excel_provider=None, excel_providers=None):
        self.fred = fred_provider
        self.excel = excel_provider
        self.excel_providers = excel_providers or {}

    def get_series(self, country, series_config):
        source = series_config["source"]

        if source == "fred":
            return self.fred.get_series(country, series_config)

        elif source == "excel":
            excel_provider = self.excel_providers.get(country, self.excel)
            if excel_provider is None:
                raise ValueError(f"Excel provider not initialized for {country}")
            return excel_provider.get_series(country, series_config)

        else:
            raise ValueError("Unknown data source")
