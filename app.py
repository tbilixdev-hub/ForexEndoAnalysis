import streamlit as st

from config import COUNTRIES, FRED_API_KEY
from data.providers import FREDProvider, ExcelProvider, HybridProvider
from country.country_model import CountryModel


st.set_page_config(layout="wide")
st.title("Macro Score Dashboard")


# ==============================
# FILE UPLOAD (OPTIONAL)
# ==============================

uploaded_file = st.file_uploader(
    "Upload Excel Data (if required)",
    type=["xlsx"]
)


# ==============================
# PROVIDER INITIALIZATION
# ==============================

fred_provider = FREDProvider(FRED_API_KEY)

excel_provider = None
if uploaded_file is not None:
    try:
        excel_provider = ExcelProvider(uploaded_file)
    except Exception as exc:
        st.error(f"Could not read uploaded Excel file: {exc}")
        st.stop()

provider = HybridProvider(
    fred_provider=fred_provider,
    excel_provider=excel_provider
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
