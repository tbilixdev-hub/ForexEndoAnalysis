import numpy as np
import pandas as pd
import pytest

from config_.series_config import SERIES_CONFIG
from country.country_model import CountryModel, geometric_aggregate
from pillars.fiscal import FiscalPillar
from pillars.growth import GrowthPillar
from pillars.inflation import InflationPillar
from pillars.labor import LaborPillar
from pillars.monetary import MonetaryPillar

END = "2026-09-01"


class FakeProvider:
    """Serves synthetic series keyed by the config 'code'."""

    def __init__(self, data):
        self.data = data

    def get_series(self, country, cfg):
        if cfg["code"] not in self.data:
            raise ValueError(f"no data for {cfg['code']}")
        return self.data[cfg["code"]]


def monthly(start="1980-01-01", end=END):
    return pd.date_range(start, end, freq="MS")


def random_walk(index, seed, base=100.0, drift=0.002, vol=0.003):
    rng = np.random.default_rng(seed)
    return pd.Series(base * np.exp(np.cumsum(rng.normal(drift, vol, len(index)))), index)


def noise(index, seed, loc=0.0):
    return pd.Series(np.random.default_rng(seed).normal(loc, 1.0, len(index)), index)


def fiscal_data():
    q = pd.date_range("1970-01-01", "2026-04-01", freq="QS")
    a = pd.date_range("1970-01-01", "2025-01-01", freq="YS")
    d = pd.date_range("1970-01-01", "2026-09-30", freq="D")
    gdp = random_walk(q, 1, base=1000, drift=0.012, vol=0.005)
    return {
        "GFDEGDQ188S": noise(q, 2, 60),
        "FYFSGDA188S": noise(a, 3, -3),
        "A091RC1Q027SBEA": gdp * (0.02 + 0.002 * noise(q, 4)),
        "GDP": gdp,
        "FYFRGDA188S": noise(a, 5, 17),
        "DGS10": noise(d, 6, 4),
    }


def run_fiscal(data):
    pillar = FiscalPillar("USD", FakeProvider(data))
    pillar.run()
    used = [d for d in pillar.details if d["status"] == "used"]
    assert used, pillar.details
    return pillar, used[0]


def test_inflation_composite_does_not_jump_when_shorter_series_starts():
    cpi = random_walk(monthly(), seed=10)
    ppi = cpi[cpi.index >= "2010-01-01"]  # same dynamics, shorter history

    cpi_only = InflationPillar("USD", FakeProvider({"CPILFESL": cpi}))
    cpi_only.run()
    both = InflationPillar("USD", FakeProvider({"CPILFESL": cpi, "PPIFID": ppi}))
    both.run()

    pd.testing.assert_series_equal(both.score_series, cpi_only.score_series)


def test_growth_is_invariant_to_indicator_scale():
    idx = monthly()
    base = {
        "US_PMI": noise(idx, 20, 50),
        "US_NMI": noise(idx, 21, 55),
        "UMCSENT": noise(idx, 22, 70),
        "HOUST": random_walk(idx, 23, base=1500),
    }
    rescaled = dict(base, UMCSENT=base["UMCSENT"] * 100 + 1000)

    a = GrowthPillar("USD", FakeProvider(base))
    a.run()
    b = GrowthPillar("USD", FakeProvider(rescaled))
    b.run()

    assert not a.score_series.empty
    pd.testing.assert_series_equal(a.score_series, b.score_series)


def test_fiscal_score_runs_to_latest_month_despite_annual_series():
    pillar, _ = run_fiscal(fiscal_data())
    assert pillar.score_series.index[-1] == pd.Timestamp("2026-09-30")


def test_fiscal_larger_surplus_is_positive():
    data = fiscal_data()
    deficit = data["FYFSGDA188S"].copy()
    deficit.iloc[-1] = deficit.iloc[:-1].mean() + 5 * deficit.iloc[:-1].std()
    data["FYFSGDA188S"] = deficit

    _, detail = run_fiscal(data)
    assert detail["deficit_z"] > 1


def test_fiscal_interest_is_measured_relative_to_gdp():
    data = fiscal_data()
    trend = pd.Series(np.exp(np.linspace(0, 3, len(data["GDP"]))), data["GDP"].index)
    scaled = dict(data, GDP=data["GDP"] * trend, A091RC1Q027SBEA=data["A091RC1Q027SBEA"] * trend)

    _, base = run_fiscal(data)
    _, grown = run_fiscal(scaled)
    assert base["interest_z"] == pytest.approx(grown["interest_z"])
    assert base["liquidity_z"] == pytest.approx(grown["liquidity_z"])


def test_monetary_score_runs_past_last_gdp_print():
    idx = monthly()
    weekly = pd.date_range("1980-01-02", "2026-09-30", freq="W-WED")
    data = {
        "FEDFUNDS": noise(idx, 30, 3),
        "CPILFESL": random_walk(idx, 31),
        "WALCL": random_walk(weekly, 32, base=1e6, drift=0.001, vol=0.004),
        "GDP": random_walk(pd.date_range("1980-01-01", "2026-04-01", freq="QS"), 33, base=1e4, drift=0.012),
        "M2SL": random_walk(idx, 34),
    }
    pillar = MonetaryPillar("USD", FakeProvider(data))
    pillar.run()

    assert pillar.score_series.index[-1] == pd.Timestamp("2026-09-30")
    detail = [d for d in pillar.details if d["status"] == "used"][0]
    assert not np.isnan(detail["balance_sheet_z"])


def test_country_without_config_scores_nan_not_zero():
    assert SERIES_CONFIG["EUR"] == {}
    model = CountryModel("EUR", FakeProvider({}))
    score = model.run()

    assert np.isnan(score)
    assert all(np.isnan(v) for v in model.pillar_scores.values())
    assert model.sensitivity_results == {}


def test_geometric_aggregate_renormalizes_over_available_pillars():
    weights = {"a": 0.5, "b": 0.5}
    assert geometric_aggregate({"a": 0.4, "b": float("nan")}, weights) == pytest.approx(0.4)
    assert np.isnan(geometric_aggregate({"a": float("nan"), "b": float("nan")}, weights))


def test_pillar_series_share_month_end_index():
    idx = monthly()  # FRED-style first-of-month dates
    data = {
        "CPILFESL": random_walk(idx, 40),
        "PAYEMS": random_walk(idx, 41),
        "CES0500000003": random_walk(idx, 42),
        "UNRATE": noise(idx, 43, 5),
    }
    for pillar_cls in (InflationPillar, LaborPillar):
        pillar = pillar_cls("USD", FakeProvider(data))
        pillar.run()
        assert not pillar.score_series.empty
        assert pillar.score_series.index.is_month_end.all(), pillar_cls.__name__
