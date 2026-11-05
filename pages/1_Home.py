import streamlit as st


st.title("Welcome to Crypto Risk Radar")
st.markdown(
	"### Diversification is an illusion when your assets move together."
)

st.warning(
	"**The problem:** If you buy 5 different coins, but they all drop when "
	"Bitcoin drops, you are not diversified. You are just holding 5 versions "
	"of Bitcoin."
)

st.markdown(
	"## How the Risk Radar helps\n"
	"The tool compares historical price movements and calculates the "
	"**correlation coefficient**, a value from **-1 to 1**. It shows how "
	"closely two assets have moved together in the past. A high positive "
	"correlation can point to overlapping risk, while a low or negative "
	"correlation may indicate different or opposite movement. Historical "
	"correlation does not guarantee future behavior."
)

st.markdown("## Reading the correlation colors")
red_column, white_column, blue_column = st.columns(3)

with red_column:
	st.markdown("🔴 **Red (Close to 1.0)**\n\nHigh risk. Assets move together.")

with white_column:
	st.markdown("⚪ **White (Close to 0.0)**\n\nNo correlation. Potentially better diversification.")

with blue_column:
	st.markdown("🔵 **Blue (Close to -1.0)**\n\nInverse correlation. One tends to rise as the other falls; this may act as a hedge.")

st.info(
	'To start analyzing, open the left sidebar and click **"Risk Radar"**.'
)
