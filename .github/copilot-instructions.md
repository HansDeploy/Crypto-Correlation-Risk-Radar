# Project: Crypto-Correlation-Risk-Radar

## Context
This is a professional financial analytics tool that calculates the historical correlation between multiple cryptocurrencies. It helps investors understand if their portfolio is truly diversified or just a duplicate of Bitcoin.

## Tech Stack
- Python 3.13
- Streamlit (for the web UI and navigation)
- Pandas & NumPy (for mathematical correlation)
- Plotly (for interactive Heatmaps)
- CoinGecko API (for fetching historical prices)
- Google GenAI (Gemini) for interpreting the results

## Coding Standards
- Language: English Only (UI, Code, Prompts).
- Structure: Use `src/` for backend logic (fetching, calculating) and `pages/` for Streamlit UI.
- Professional UI: Dark theme, clean layout, simple for beginners but powerful for experts.
- Always use `@st.cache_data` when fetching API data to prevent rate limits.
- Never hardcode API keys; use `.env`.

## Current Goal
Build the data fetcher and the correlation calculation logic in `src/`.
