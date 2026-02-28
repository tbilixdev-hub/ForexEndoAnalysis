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
    excel_provider = ExcelProvider(uploaded_file)

provider = HybridProvider(
    fred_provider=fred_provider,
    excel_provider=excel_provider
)


# ==============================
# COMPUTE COUNTRY SCORES
# ==============================

results = {}

for country in COUNTRIES:
    model = CountryModel(country, provider)
    score = model.run()
    results[country] = score


# ==============================
# DISPLAY RESULTS
# ==============================

st.subheader("Internal Scores")

for country, score in results.items():
    st.write(f"{country}: {score:.2f}")