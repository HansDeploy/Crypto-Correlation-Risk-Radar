import importlib
import json
import os
import re
from html import escape

from dotenv import load_dotenv
from groq import Groq
import streamlit as st

from src.data_fetcher import get_top_coins_list

load_dotenv()

try:
	client = Groq(api_key=os.getenv("GROQ_API_KEY"))
except Exception as e:
	print(f"GROQ ERROR: {e}")
	client = None

st.set_page_config(
	layout="wide",
	initial_sidebar_state="collapsed",
	page_title="Crypto Correlation Risk Radar",
	page_icon="📡",
)

st.markdown(
	"""
	<style>
	:root {
		color-scheme: dark;
		--radar-background: #0b0e14;
		--radar-surface: #121923;
		--radar-accent: #00d9d2;
		--radar-text: #e0e5e9;
		--radar-muted: #929eaa;
	}

	.stApp,
	[data-testid="stAppViewContainer"] {
		background-color: var(--radar-background);
		background-image:
			linear-gradient(rgba(177, 205, 215, 0.025) 1px, transparent 1px),
			linear-gradient(90deg, rgba(177, 205, 215, 0.025) 1px, transparent 1px);
		background-size: 56px 56px;
		color: var(--radar-text);
	}

	[data-testid="stSidebar"],
	[data-testid="stSidebarCollapsedControl"] {
		display: none;
	}

	[data-testid="stHeader"] {
		background: transparent;
	}

	[data-testid="stMainBlockContainer"] {
		max-width: 1160px;
		padding-top: 3rem;
		padding-bottom: 4rem;
	}

	.hero {
		max-width: 850px;
		margin: 2rem auto 3rem;
		text-align: center;
	}

	.hero-kicker {
		color: var(--radar-accent);
		font-size: 0.78rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}

	.hero h1 {
		color: var(--radar-text);
		font-family: Georgia, "Times New Roman", serif;
		font-size: 3.25rem;
		font-weight: 500;
		line-height: 1.12;
		margin: 1rem 0;
	}

	.hero p {
		color: var(--radar-muted);
		font-size: 1.08rem;
		line-height: 1.7;
		margin: 0 auto;
		max-width: 660px;
	}

	.selector-label {
		color: var(--radar-text);
		font-size: 1rem;
		font-weight: 600;
		margin-bottom: 0.4rem;
	}

	[data-testid="stTextInput"] input {
		background-color: var(--radar-surface);
		border-color: rgba(224, 229, 233, 0.16);
		border-radius: 8px;
		min-height: 3.5rem;
		padding-left: 1rem;
	}

	[data-testid="stPills"] button {
		border-radius: 999px;
	}

	div.stButton > button[kind="primary"] {
		background: var(--radar-accent);
		border: 0;
		color: #061214;
		font-weight: 700;
		min-height: 3rem;
	}

	div.stButton > button[kind="primary"]:hover {
		background: #6ce8df;
		border: 0;
		color: #061214;
	}

	@media (max-width: 700px) {
		.hero h1 {
			font-size: 2.4rem;
		}
	}
	</style>
	""",
	unsafe_allow_html=True,
)

st.markdown(
	"""
	<section class="hero">
		<div class="hero-kicker">Portfolio structure / correlation analysis</div>
		<h1>Crypto Correlation Risk Radar</h1>
		<p>See whether your crypto holdings truly diversify your risk, or tend to move together when markets shift.</p>
	</section>
	""",
	unsafe_allow_html=True,
)

try:
	coin_records = get_top_coins_list(limit=500)
except Exception as error:
	st.error(f"Unable to load the coin list: {error}")
	coin_records = []

coin_labels = {
	coin["id"]: f'{coin["name"]} ({coin["symbol"]})'
	for coin in coin_records
	if all(key in coin for key in ("id", "name", "symbol"))
}
coin_ids = list(coin_labels)
coin_by_id = {coin["id"]: coin for coin in coin_records if coin.get("id") in coin_labels}

if "selected_coin_ids" not in st.session_state:
	st.session_state.selected_coin_ids = []


def _add_coin_from_pills() -> None:
	"""Add the currently selected search result to the portfolio."""
	coin_id = st.session_state.get("coin_pill_choice")
	selected_ids = st.session_state.selected_coin_ids
	if coin_id and coin_id not in selected_ids:
		if len(selected_ids) >= 10:
			st.session_state.coin_selection_message = "You can select up to 10 coins."
		else:
			selected_ids.append(coin_id)
	st.session_state.coin_pill_choice = None

_, selector_column, _ = st.columns([0.75, 4.5, 0.75])
with selector_column:
	st.markdown('<div class="selector-label">Choose assets to compare</div>', unsafe_allow_html=True)
	search_query = st.text_input(
		"Search cryptocurrencies",
		placeholder="Search and select coins in your portfolio...",
		label_visibility="collapsed",
		key="coin_search_query",
	)
	search_term = search_query.strip().casefold()
	if search_term:
		matching_coin_ids = [
			coin_id
			for coin_id in coin_ids
			if search_term in coin_labels[coin_id].casefold()
			or search_term in coin_id.casefold()
		][:24]
	else:
		matching_coin_ids = coin_ids[:12]
	matching_coin_ids = [
		coin_id for coin_id in matching_coin_ids
		if coin_id not in st.session_state.selected_coin_ids
	]
	if matching_coin_ids:
		st.pills(
			"Matching coins",
			options=matching_coin_ids,
			selection_mode="single",
			format_func=lambda coin_id: coin_by_id[coin_id]["name"],
			key="coin_pill_choice",
			on_change=_add_coin_from_pills,
			label_visibility="collapsed",
			width="stretch",
			wrap=True,
		)
	else:
		st.caption("No matching coins. Try another name, symbol, or CoinGecko ID.")
	if message := st.session_state.pop("coin_selection_message", None):
		st.warning(message)

	selected_coins = st.session_state.selected_coin_ids
	if selected_coins:
		st.markdown("#### Selected assets")
		for row_start in range(0, len(selected_coins), 5):
			row_ids = selected_coins[row_start : row_start + 5]
			asset_columns = st.columns(5)
			for column, coin_id in zip(asset_columns, row_ids):
				coin = coin_by_id[coin_id]
				with column:
					with st.container(border=True):
						if coin.get("image"):
							st.image(coin["image"], width=42)
						st.markdown(f"**{coin['name']}**")
						st.caption(coin["symbol"])
						if st.button("Remove", key=f"remove_{coin_id}", width="stretch"):
							st.session_state.selected_coin_ids.remove(coin_id)
							st.rerun()

_, action_column, _ = st.columns([1.5, 1, 1.5])
with action_column:
	analyze = st.button(
		"Analyze Portfolio",
		type="primary",
		width="stretch",
		disabled=not coin_ids,
	)

if analyze:
	if not st.session_state.selected_coin_ids:
		st.warning("Select at least one coin to continue.")
	else:
		analysis_page = importlib.import_module("pages.2_Analysis")
		selected_coins = st.session_state.selected_coin_ids
		coin_symbols = {
			coin_id: str(coin_by_id[coin_id].get("symbol", coin_id)).upper()
			for coin_id in selected_coins
		}
		analysis_results = analysis_page.render_analysis(selected_coins, coin_symbols)
		if analysis_results is not None:
			top_correlations, risk_score = analysis_results
			st.markdown("### AI Insights")
			if not top_correlations:
				st.info("At least two coins with valid return data are needed for interpretation.")
			else:
				selected_coin_details = [
					{"id": coin_id, "name": coin_labels.get(coin_id, coin_id)}
					for coin_id in selected_coins
				]
				prompt = (
					"You are a professional financial risk analyst. Identify the primary "
					"Narrative/Sector for each selected coin using common crypto narratives "
					"such as AI, DePIN, Layer 1, Layer 2, DeFi, RWA, Meme, GameFi, and "
					"Store of Value. For example, Bitcoin = Digital Gold / Store of Value, "
					"Render = AI / DePIN, and Solana = Layer 1. Then explain the correlation risk based on the calculated "
					"top correlated pairs. Return only valid JSON with exactly two keys: "
					'"narratives" (a dictionary mapping coin name to sector) and '
					'"risk_analysis" (a maximum 3-sentence explanation). Do not give '
					"financial advice; explain statistical risk only.\n\n"
					f"Selected coins:\n{json.dumps(selected_coin_details)}\n\n"
					f"Top correlated pairs:\n{json.dumps(top_correlations[:3])}\n\n"
					"You MUST respond ONLY with a valid JSON object. Do not include markdown "
					"code blocks (```json). Do not include any conversational text outside "
					"the JSON. The JSON must have exactly two keys: 'narratives' (a dict "
					"mapping coin names to their sector, e.g., {'Bitcoin': 'Store of Value'}) "
					"and 'risk_analysis' (a string containing the 2-3 sentence risk explanation, "
					f"including one sentence explaining why the portfolio's risk score is {risk_score} out of 10)."
				)
				try:
					with st.spinner("Preparing the risk interpretation..."):
						if client is None:
							raise RuntimeError("Groq client is unavailable")
						response = client.chat.completions.create(
							model="openai/gpt-oss-20b",
							messages=[{"role": "user", "content": prompt}],
						)
					response_text = response.choices[0].message.content
					if response_text:
						raw_response = response_text
						risk_analysis = raw_response
						insights = None
						json_start = response_text.find("{")
						json_end = response_text.rfind("}")
						if json_start != -1 and json_end > json_start:
							try:
								insights = json.loads(response_text[json_start : json_end + 1])
							except json.JSONDecodeError:
								pass
						if not isinstance(insights, dict):
							json_match = re.search(r"\{.*\}", response_text, flags=re.DOTALL)
							if json_match:
								try:
									insights = json.loads(json_match.group(0))
								except json.JSONDecodeError:
									insights = None
						if (
							isinstance(insights, dict)
							and isinstance(insights.get("narratives"), dict)
							and isinstance(insights.get("risk_analysis"), str)
						):
							narratives = insights["narratives"]
							if narratives:
								coin_columns = st.columns(len(narratives))
								coin_icons = {
									"bitcoin": "₿",
									"ethereum": "⟠",
								}
								for column, (coin_name, sector) in zip(coin_columns, narratives.items()):
									coin_icon = next(
										(icon for name, icon in coin_icons.items() if name in coin_name.casefold()),
										"◈",
									)
									with column:
										st.markdown(f"#### {coin_icon} {escape(str(coin_name))}")
										st.caption(str(sector))
							else:
								st.info("No coin narratives were returned.")
							risk_analysis = insights["risk_analysis"]
						risk_html = "<br>".join(escape(risk_analysis).splitlines())
						st.markdown(
							'<div style="border-left: 4px solid #00f2fe; padding: 15px; '
							'background: rgba(15, 23, 32, 0.88); color: #ffffff;">'
							f"{risk_html}</div>",
							unsafe_allow_html=True,
						)
					else:
						st.warning("AI Analysis is temporarily unavailable.")
				except Exception as e:
					print(f"GROQ ERROR: {e}")
					st.warning("AI Analysis is temporarily unavailable.")
			st.markdown("### Portfolio Risk Score")
			if risk_score is None:
				st.metric(label="Risk Score (Out of 10)", value="N/A")
				st.caption("A score requires valid correlations between at least two assets.")
			else:
				st.metric(label="Risk Score (Out of 10)", value=f"{risk_score} / 10")
				if risk_score <= 3:
					risk_color, risk_label = "#14F195", "Low Risk"
				elif risk_score <= 6:
					risk_color, risk_label = "#FFD700", "Moderate Risk"
				elif risk_score <= 8:
					risk_color, risk_label = "#FF8C00", "High Risk"
				else:
					risk_color, risk_label = "#FF4B4B", "Extreme Risk"
			st.markdown(
				f'<div style="height: 12px; width: 100%; margin-top: 8px; '
				f'background: rgba(224, 229, 233, 0.12); border-radius: 999px; overflow: hidden;">'
				f'<div role="progressbar" aria-valuenow="{risk_score}" aria-valuemin="0" '
				f'aria-valuemax="10" style="height: 100%; width: {risk_score * 10 if risk_score is not None else 0}%; '
				f'background: {risk_color if risk_score is not None else "#666"}; '
				f'border-radius: 999px; transition: width 300ms ease;"></div></div>',
				unsafe_allow_html=True,
			)
			if risk_score is not None:
				st.caption(f"{risk_label} · based on average pairwise historical correlation")
	st.markdown(
		'<div style="text-align: center; color: #666; font-size: 0.85rem; '
		'margin-top: 50px;">Powered by <b>HansDeploy</b></div>',
		unsafe_allow_html=True,
	)
