import streamlit as st

from config import COUNTRIES, FRED_API_KEY
from config_.series_config import SERIES_CONFIG
from data.providers import FREDProvider, ExcelProvider, HybridProvider
from country.country_model import CountryModel


st.set_page_config(layout="wide")
st.title("Macro Score Dashboard")


def get_excel_requirements(country):
    country_cfg = SERIES_CONFIG.get(country, {})
    requirements = []
    for pillar_cfg in country_cfg.values():
        if not isinstance(pillar_cfg, dict):
            continue
        for indicator_name, indicator_cfg in pillar_cfg.items():
            if indicator_cfg.get("source") != "excel":
                continue
            requirements.append({
                "indicator": indicator_name,
                "sheet": indicator_cfg.get("sheet", 0),
                "column": indicator_cfg.get("column") or indicator_cfg.get("code", "<missing>"),
            })
    # Deduplicate by sheet+column to keep instruction clean.
    seen = set()
    deduped = []
    for item in requirements:
        key = (item["sheet"], item["column"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


# ==============================
# FILE UPLOAD BY CURRENCY
# ==============================

st.subheader("Upload Data Files by Currency")
st.caption("Upload only the currencies that require Excel sources. USD currently needs one ISM file.")

excel_providers = {}
for country in COUNTRIES:
    reqs = get_excel_requirements(country)
    if not reqs:
        continue

    left_col, right_col = st.columns([3, 2])
    with left_col:
        st.markdown(f"**{country}**")
        for req in reqs:
            st.write(
                f"Required sheet `{req['sheet']}` with columns `Date`, `{req['column']}`"
            )

    with right_col:
        uploaded_file = st.file_uploader(
            f"Browse {country} file",
            type=["xlsx"],
            key=f"upload_{country}"
        )
        if uploaded_file is not None:
            try:
                excel_providers[country] = ExcelProvider(uploaded_file)
            except Exception as exc:
                st.error(f"{country}: could not read uploaded Excel file: {exc}")
                st.stop()

st.divider()


# ==============================
# PROVIDER INITIALIZATION
# ==============================

fred_provider = FREDProvider(FRED_API_KEY)

provider = HybridProvider(
    fred_provider=fred_provider,
    excel_providers=excel_providers
)


# ==============================
# COMPUTE COUNTRY SCORES
# ==============================

results = {}
details = {}

for country in COUNTRIES:
    model = CountryModel(country, provider)
    score = model.run()
    results[country] = {
        "internal": score,
        "growth": model.pillar_scores["growth"],
        "inflation": model.pillar_scores["inflation"],
        "labor": model.pillar_scores["labor"],
        "monetary": model.pillar_scores["monetary"],
        "fiscal": model.pillar_scores["fiscal"],
    }
    details[country] = model.details


# ==============================
# DISPLAY RESULTS
# ==============================

st.subheader("Internal Scores")

for country, vals in results.items():
    st.write(
        f"{country}: internal={vals['internal']:.2f} | "
        f"growth={vals['growth']:.2f} | inflation={vals['inflation']:.2f} | "
        f"labor={vals['labor']:.2f} | monetary={vals['monetary']:.2f} | "
        f"fiscal={vals['fiscal']:.2f}"
    )

with st.expander("Growth calculation details"):
    for country in COUNTRIES:
        st.write(f"{country}")
        growth_details = details.get(country, {}).get("growth", [])
        if not growth_details:
            st.write("  No growth indicators configured or all skipped.")
        else:
            for item in growth_details:
                if item["status"] == "used":
                    st.write(
                        f"  used: {item['indicator']} ({item['source']}), "
                        f"weight={item['weight']}, z={item['zscore']:.3f}, "
                        f"score={item['score']:+.1f}, regime={item['regime']}"
                    )
                else:
                    st.write(
                        f"  skipped: {item['indicator']} ({item['source']}), "
                        f"reason={item['reason']}"
                    )

with st.expander("Labor calculation details"):
    for country in COUNTRIES:
        st.write(f"{country}")
        labor_details = details.get(country, {}).get("labor", [])
        if not labor_details:
            st.write("  No labor indicators configured or all skipped.")
        else:
            for item in labor_details:
                if item["status"] == "used":
                    st.write(
                        f"  used: score={item['score']:+.3f}, regime={item['regime']}, "
                        f"nfp_z={item['nfp_z']:.2f}, ahe_z={item['ahe_z']:.2f}, "
                        f"unrate_z={item['unrate_z']:.2f}"
                    )
                else:
                    st.write(f"  skipped: reason={item['reason']}")

with st.expander("Inflation calculation details"):
    for country in COUNTRIES:
        st.write(f"{country}")
        inflation_details = details.get(country, {}).get("inflation", [])
        if not inflation_details:
            st.write("  No inflation indicators configured or all skipped.")
        else:
            for item in inflation_details:
                if item["status"] == "used":
                    st.write(
                        f"  used: {item['indicator']} ({item['source']}), "
                        f"target={item['target']}, score={item['score']:+.3f}"
                    )
                else:
                    st.write(
                        f"  skipped: {item['indicator']} ({item['source']}), "
                        f"reason={item['reason']}"
                    )

with st.expander("Monetary calculation details"):
    for country in COUNTRIES:
        st.write(f"{country}")
        monetary_details = details.get(country, {}).get("monetary", [])
        if not monetary_details:
            st.write("  No monetary indicators configured or all skipped.")
        else:
            for item in monetary_details:
                if item["status"] == "used":
                    st.write(
                        f"  used: score={item['score']:+.3f}, regime={item['regime']}, "
                        f"real_rate_z={item['real_rate_z']:.2f}, "
                        f"balance_sheet_z={item['balance_sheet_z']:.2f}, "
                        f"m2_z={item['m2_z']:.2f}"
                    )
                else:
                    st.write(f"  skipped: reason={item['reason']}")

with st.expander("Fiscal calculation details"):
    for country in COUNTRIES:
        st.write(f"{country}")
        fiscal_details = details.get(country, {}).get("fiscal", [])
        if not fiscal_details:
            st.write("  No fiscal indicators configured or all skipped.")
        else:
            for item in fiscal_details:
                if item["status"] == "used":
                    st.write(
                        f"  used: score={item['score']:+.3f}, regime={item['regime']}, "
                        f"debt_z={item['debt_z']:.2f}, deficit_z={item['deficit_z']:.2f}, "
                        f"interest_z={item['interest_z']:.2f}, liquidity_z={item['liquidity_z']:.2f}, "
                        f"yield_z={item['yield_z']:.2f}"
                    )
                else:
                    st.write(f"  skipped: reason={item['reason']}")
