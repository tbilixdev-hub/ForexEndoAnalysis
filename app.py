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

    st.markdown(f"**{country} upload requirements**")
    for req in reqs:
        st.write(
            f"- Sheet `{req['sheet']}` must include columns: `Date`, `{req['column']}`"
        )

    uploaded_file = st.file_uploader(
        f"Upload {country} Excel file (.xlsx)",
        type=["xlsx"],
        key=f"upload_{country}"
    )
    if uploaded_file is not None:
        try:
            excel_providers[country] = ExcelProvider(uploaded_file)
        except Exception as exc:
            st.error(f"{country}: could not read uploaded Excel file: {exc}")
            st.stop()


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
        "growth": model.pillar_scores["growth"]
    }
    details[country] = model.details


# ==============================
# DISPLAY RESULTS
# ==============================

st.subheader("Internal Scores")

for country, vals in results.items():
    st.write(
        f"{country}: internal={vals['internal']:.2f} | growth={vals['growth']:.2f}"
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
