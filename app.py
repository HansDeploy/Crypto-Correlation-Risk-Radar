import importlib
from io import BytesIO
import json
import os
import re
from html import escape

from dotenv import load_dotenv
from groq import Groq
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import streamlit as st

from src.data_fetcher import get_market_insights, get_top_coins_list

load_dotenv()

_COIN_SECTORS = {
	"bitcoin": "Store of Value",
	"wrapped-bitcoin": "Store of Value",
	"ethereum": "Layer 1",
	"solana": "Layer 1",
	"avalanche-2": "Layer 1",
	"cardano": "Layer 1",
	"binancecoin": "Layer 1",
	"ripple": "Payments",
	"litecoin": "Payments",
	"render": "AI",
	"render-token": "AI",
	"fetch-ai": "AI",
	"chainlink": "Oracle",
	"usd-coin": "Stablecoin",
	"usdc": "Stablecoin",
	"tether": "Stablecoin",
	"uniswap": "DeFi",
	"aave": "DeFi",
	"maker": "DeFi",
	"arbitrum": "Layer 2",
	"optimism": "Layer 2",
	"filecoin": "Storage",
	"the-graph": "Data",
	"monero": "Privacy",
}

_SECTOR_SUGGESTIONS = [
	("render", "Render", "AI"),
	("uniswap", "Uniswap", "DeFi"),
	("chainlink", "Chainlink", "Oracle"),
	("filecoin", "Filecoin", "Storage"),
	("arbitrum", "Arbitrum", "Layer 2"),
	("bitcoin", "Bitcoin", "Store of Value"),
	("ripple", "XRP", "Payments"),
	("monero", "Monero", "Privacy"),
]

_BLOCKED_SUGGESTION_IDS = {"usdc", "usdt", "dai", "busd", "usd-coin", "tether"}

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


def create_share_card(
	correlation_matrix: pd.DataFrame,
	weighted_risk_score: float | None,
	portfolio: list[tuple[str, str, float]],
	unweighted_risk_score: float | None,
	suggested_portfolio: list[tuple[str, str, float]],
	new_risk_score: float | None,
	app_url: str | None = None,
) -> BytesIO:
	"""Create a portrait report comparing current and suggested allocations."""
	width, height = 1080, 1920
	image = Image.new("RGB", (width, height), "#0b0e14")
	draw = ImageDraw.Draw(image)

	def load_font(size: int, bold: bool = False):
		font_names = ["DejaVuSans-Bold.ttf", "Arial Bold.ttf"] if bold else [
			"DejaVuSans.ttf",
			"Arial.ttf",
		]
		font_names.insert(0, "/usr/share/fonts/truetype/dejavu/" + font_names[0])
		for font_name in font_names:
			try:
				return ImageFont.truetype(font_name, size)
			except OSError:
				continue
		return ImageFont.load_default()

	title_font = load_font(42, bold=True)
	subtitle_font = load_font(19)
	panel_title_font = load_font(19, bold=True)
	score_font = load_font(88, bold=True)
	label_font = load_font(20, bold=True)
	body_font = load_font(22)
	small_font = load_font(16)

	background_top = (13, 20, 29)
	background_bottom = (7, 11, 17)
	for y in range(height):
		progress = y / (height - 1)
		color = tuple(
			int(start + (end - start) * progress)
			for start, end in zip(background_top, background_bottom)
		)
		draw.line((0, y, width, y), fill=color)

	cyan = "#00e0d2"
	text = "#e8edf2"
	muted = "#8995a3"
	panel = "#111923"

	draw.rounded_rectangle((27, 27, width - 27, height - 27), radius=32, outline="#12353d", width=8)
	draw.rounded_rectangle((34, 34, width - 34, height - 34), radius=28, outline="#087c7b", width=2)
	draw.rounded_rectangle((46, 46, width - 46, height - 46), radius=24, outline="#26333f", width=1)
	draw.rounded_rectangle((72, 77, 1008, 84), radius=4, fill=cyan)
	draw.text((76, 112), "Crypto Risk Radar", font=title_font, fill=text)
	draw.text((78, 169), "PORTFOLIO CORRELATION REPORT", font=small_font, fill=cyan)
	draw.text((78, 201), "Historical correlation · Current vs. optimized allocation", font=subtitle_font, fill=muted)

	name_by_id = {coin_id: coin_name for coin_id, coin_name, _ in portfolio}
	top_pair: tuple[str, str, float] | None = None
	for row_index, coin_a in enumerate(correlation_matrix.index):
		for column_index in range(row_index + 1, len(correlation_matrix.columns)):
			correlation = correlation_matrix.iat[row_index, column_index]
			if pd.notna(correlation) and (
				top_pair is None or abs(float(correlation)) > abs(top_pair[2])
			):
				top_pair = (
					str(coin_a),
					str(correlation_matrix.columns[column_index]),
					float(correlation),
				)
	if top_pair:
		pair_text = (
			f"{name_by_id.get(top_pair[0], top_pair[0])} & "
			f"{name_by_id.get(top_pair[1], top_pair[1])}"
		)
		correlation_text = f"{top_pair[2]:+.2f}"
	else:
		pair_text, correlation_text = "Not enough pair data", "N/A"

	def draw_holdings(
		holdings: list[tuple[str, str, float]],
		top: int,
		bottom: int,
		accent: str,
		empty_message: str,
	) -> None:
		draw.text((108, top), "ASSET", font=small_font, fill=muted)
		draw.text((872, top), "WEIGHT", font=small_font, fill=muted)
		draw.line((108, top + 32, 972, top + 32), fill="#26333f", width=1)
		sorted_holdings = sorted(holdings, key=lambda item: item[2], reverse=True)
		visible_holdings = sorted_holdings[:12]
		if not visible_holdings:
			draw.text((110, top + 58), empty_message, font=body_font, fill=muted)
			return
		row_height = min(43, max(30, (bottom - top - 48) // len(visible_holdings)))
		for index, (_, coin_name, weight) in enumerate(visible_holdings):
			y = top + 44 + index * row_height
			display_name = coin_name if len(coin_name) <= 46 else f"{coin_name[:43]}..."
			draw.text((110, y), display_name, font=body_font, fill=text)
			draw.text((880, y), f"{weight:.0f}%", font=body_font, fill=accent)
			if index < len(visible_holdings) - 1:
				draw.line((108, y + row_height - 5, 972, y + row_height - 5), fill="#202c37", width=1)
		if len(sorted_holdings) > len(visible_holdings):
			draw.text(
				(110, bottom - 25),
				f"+ {len(sorted_holdings) - len(visible_holdings)} more assets",
				font=small_font,
				fill=muted,
			)

	current_risk_text = (
		f"{weighted_risk_score:.1f} / 10"
		if weighted_risk_score is not None
		else "N/A"
	)
	unweighted_text = (
		f"Unweighted score: {unweighted_risk_score:.1f} / 10"
		if unweighted_risk_score is not None
		else "Unweighted score: N/A"
	)
	draw.rounded_rectangle((72, 250, 1008, 895), radius=26, fill=panel, outline="#2a3a47", width=2)
	draw.text((108, 285), "CURRENT PORTFOLIO RISK", font=panel_title_font, fill=muted)
	draw.text((105, 326), current_risk_text, font=score_font, fill="#ff8c69")
	draw.text((110, 432), unweighted_text, font=subtitle_font, fill=muted)
	draw.text((110, 472), f"Top risk pair: {pair_text} ({correlation_text})", font=small_font, fill="#ffb394")
	draw_holdings(portfolio, top=535, bottom=870, accent="#e8edf2", empty_message="No current holdings")

	improved = (
		weighted_risk_score is not None
		and new_risk_score is not None
		and new_risk_score < weighted_risk_score
	)
	arrow_color = "#35e0a1" if improved else cyan
	draw.rounded_rectangle((72, 925, 1008, 1035), radius=24, fill="#121d28", outline="#2a3a47", width=2)
	draw.text((125, 963), current_risk_text, font=label_font, fill="#ff8c69")
	draw.line((390, 986, 680, 986), fill=arrow_color, width=5)
	draw.polygon([(680, 976), (700, 986), (680, 996)], fill=arrow_color)
	optimized_risk_text = f"{new_risk_score:.1f} / 10" if new_risk_score is not None else "N/A"
	draw.text((748, 963), optimized_risk_text, font=label_font, fill=cyan)

	draw.rounded_rectangle((72, 1065, 1008, 1685), radius=26, fill="#101b25", outline=cyan, width=3)
	draw.text((108, 1100), "OPTIMIZED PORTFOLIO RISK", font=panel_title_font, fill=cyan)
	draw.text((105, 1140), optimized_risk_text, font=score_font, fill=cyan)
	draw.text((110, 1245), "SUGGESTED ALLOCATION", font=small_font, fill=muted)
	draw_holdings(
		suggested_portfolio,
		top=1280,
		bottom=1660,
		accent=cyan,
		empty_message="No suggested allocation available",
	)

	draw.line((72, 1730, 1008, 1730), fill="#26333f", width=2)
	draw.text((76, 1760), "Analyze your portfolio at", font=small_font, fill=muted)
	resolved_app_url = app_url or os.getenv("APP_URL")
	url_text = resolved_app_url if resolved_app_url else "Set APP_URL to your live dashboard URL"
	url_font = load_font(14)
	url_text = url_text if len(url_text) <= 86 else f"{url_text[:83]}..."
	draw.text((76, 1786), url_text, font=url_font, fill=cyan)
	draw.text((76, 1830), "Powered by HansDeploy", font=small_font, fill=text)
	draw.text((817, 1830), "CRYPTO RISK RADAR", font=small_font, fill=cyan)

	image_bytes = BytesIO()
	image.save(image_bytes, format="PNG")
	image_bytes.seek(0)
	return image_bytes


def _calculate_weighted_risk_score(
	correlation_matrix: pd.DataFrame,
	weights: pd.Series,
) -> float | None:
	"""Calculate the bounded risk score from a correlation matrix and weights."""
	matrix_weights = weights.reindex(correlation_matrix.index).fillna(0)
	weighted_matrix = (
		correlation_matrix.mul(matrix_weights, axis="index")
		.mul(matrix_weights.reindex(correlation_matrix.columns), axis="columns")
	)
	if not weighted_matrix.notna().to_numpy().any():
		return None
	return min(10.0, max(0.0, round(float(weighted_matrix.sum().sum()) * 10, 1)))


def get_suggested_portfolio(
	current_coins: list[str],
	portfolio_weights: dict[str, float],
	correlation_matrix: pd.DataFrame,
	current_risk_score: float | None,
) -> tuple[str | None, list[dict[str, str | float]], dict[str, float], float | None]:
	"""Return a sector-diversified allocation and its estimated weighted risk."""
	if not current_coins:
		return None, [], {}, None

	total_weight = sum(
		max(float(portfolio_weights.get(coin_id, 0)), 0) for coin_id in current_coins
	)
	if total_weight <= 0:
		normalized_weights = {coin_id: 1 / len(current_coins) for coin_id in current_coins}
	else:
		normalized_weights = {
			coin_id: max(float(portfolio_weights.get(coin_id, 0)), 0) / total_weight
			for coin_id in current_coins
		}

	sector_weights: dict[str, float] = {}
	for coin_id, weight in normalized_weights.items():
		sector = _COIN_SECTORS.get(coin_id.casefold(), "Other")
		sector_weights[sector] = sector_weights.get(sector, 0) + weight

	focus_sector, focus_weight = max(sector_weights.items(), key=lambda item: item[1])
	concentrated = focus_weight > 0.6
	if current_risk_score is None or (current_risk_score <= 6 and not concentrated):
		return None, [], {}, None

	current_ids = {coin_id.casefold() for coin_id in current_coins}
	suggestions: list[dict[str, str | float]] = []
	suggested_sectors: set[str] = set(sector_weights)
	for coin_id, name, sector in _SECTOR_SUGGESTIONS:
		if (
			coin_id.casefold() in _BLOCKED_SUGGESTION_IDS
			or coin_id.casefold() in current_ids
			or sector in suggested_sectors
		):
			continue
		suggestions.append({"id": coin_id, "name": name, "sector": sector})
		suggested_sectors.add(sector)
		if len(suggestions) == 2:
			break
	if not suggestions:
		return focus_sector if concentrated else None, [], None

	added_weight = 0.2
	retained_weight = 1 - added_weight
	adjusted_weights = pd.Series(
		{
			coin_id: weight * retained_weight
			for coin_id, weight in normalized_weights.items()
		},
		dtype="float64",
	)
	per_suggestion_weight = added_weight / len(suggestions)
	for suggestion in suggestions:
		suggestion["weight"] = per_suggestion_weight
		adjusted_weights[str(suggestion["id"])] = per_suggestion_weight
	adjusted_weight_map = adjusted_weights.to_dict()

	portfolio_ids = [*current_coins, *(str(item["id"]) for item in suggestions)]
	expanded_matrix = pd.DataFrame(
		0.0,
		index=portfolio_ids,
		columns=portfolio_ids,
	)
	current_matrix_ids = [
		coin_id for coin_id in current_coins if coin_id in correlation_matrix.index
		and coin_id in correlation_matrix.columns
	]
	if current_matrix_ids:
		expanded_matrix.loc[current_matrix_ids, current_matrix_ids] = (
			correlation_matrix.loc[current_matrix_ids, current_matrix_ids]
		)
	for coin_id in portfolio_ids:
		expanded_matrix.at[coin_id, coin_id] = 1.0

	estimated_risk_score = _calculate_weighted_risk_score(
		expanded_matrix,
		adjusted_weights,
	)
	return (
		focus_sector if concentrated else None,
		suggestions,
		adjusted_weight_map,
		estimated_risk_score,
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

	.market-insights {
		margin: 0 auto 1.5rem;
		max-width: 1000px;
	}

	.market-insights-title {
		color: var(--radar-muted);
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.12em;
		margin: 0 0 0.55rem 0.2rem;
		text-transform: uppercase;
	}

	.market-card {
		background: linear-gradient(145deg, rgba(20, 30, 42, 0.96), rgba(11, 17, 25, 0.96));
		border: 1px solid color-mix(in srgb, var(--market-accent) 48%, transparent);
		border-radius: 12px;
		box-shadow: 0 0 14px color-mix(in srgb, var(--market-accent) 12%, transparent),
			inset 0 0 18px rgba(255, 255, 255, 0.015);
		min-height: 98px;
		padding: 0.8rem 1rem;
	}

	.market-card-label {
		color: var(--radar-muted);
		font-size: 0.68rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.market-card-value {
		color: var(--market-accent);
		font-size: 1.28rem;
		font-weight: 700;
		line-height: 1.3;
		margin-top: 0.18rem;
		overflow-wrap: anywhere;
		text-shadow: 0 0 12px color-mix(in srgb, var(--market-accent) 35%, transparent);
	}

	.market-card-detail {
		color: var(--radar-muted);
		font-size: 0.72rem;
		margin-top: 0.12rem;
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

market_insights = get_market_insights()
fear_greed_value = market_insights["fear_greed_value"]
if isinstance(fear_greed_value, int):
	fear_greed_label = market_insights["fear_greed_classification"] or (
		"Extreme Fear" if fear_greed_value <= 24
		else "Fear" if fear_greed_value <= 44
		else "Neutral" if fear_greed_value <= 55
		else "Greed" if fear_greed_value <= 75
		else "Extreme Greed"
	)
	mood_color = "#ff5263" if fear_greed_value <= 44 else "#f5c451" if fear_greed_value <= 55 else "#35e0a1"
	mood_detail = f"Index {fear_greed_value}/100"
else:
	fear_greed_label = "N/A"
	mood_color = "#8995a3"
	mood_detail = "Fear and Greed Index unavailable"

btc_dominance = market_insights["btc_dominance"]
btc_dominance_text = f"{btc_dominance:.1f}%" if isinstance(btc_dominance, (int, float)) else "N/A"
market_cap_change = market_insights["market_cap_change_24h"]
market_cap_change_text = (
	f"Global market cap 24h: {market_cap_change:+.2f}%"
	if isinstance(market_cap_change, (int, float))
	else "Global market cap 24h: N/A"
)
trending_coin = market_insights["trending_coin"]
trending_symbol = market_insights["trending_symbol"]
trending_text = escape(trending_coin) if isinstance(trending_coin, str) else "N/A"
trending_detail = (
	f"{escape(trending_symbol)} · CoinGecko trending #1"
	if isinstance(trending_symbol, str)
	else "CoinGecko trending"
)

st.markdown(
	'<div class="market-insights"><div class="market-insights-title">Market Insights</div></div>',
	unsafe_allow_html=True,
)
market_columns = st.columns(3)
market_cards = [
	("Market Mood", fear_greed_label, mood_detail, mood_color),
	("BTC Dominance", btc_dominance_text, market_cap_change_text, "#00d9d2"),
	("Top Trending Coin", trending_text, trending_detail, "#8c7bff"),
]
for column, (label, value, detail, accent) in zip(market_columns, market_cards):
	with column:
		st.markdown(
			f'<div class="market-card" style="--market-accent: {accent}">'
			f'<div class="market-card-label">{label}</div>'
			f'<div class="market-card-value">{value}</div>'
			f'<div class="market-card-detail">{detail}</div></div>',
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

		st.markdown("#### Portfolio weights")
		weight_columns = st.columns(len(selected_coins))
		portfolio_weights = {}
		default_weight = 100 // len(selected_coins)
		for column, coin_id in zip(weight_columns, selected_coins):
			weight_key = f"portfolio_weight_{coin_id}"
			st.session_state.setdefault(weight_key, default_weight)
			with column:
				portfolio_weights[coin_id] = st.number_input(
					f"{coin_by_id[coin_id]['name']} (%)",
					min_value=0,
					max_value=100,
					step=1,
					key=weight_key,
				)
		total_weight = sum(portfolio_weights.values())
		if total_weight != 100:
			st.warning(
				f"Portfolio weights total {total_weight}%. They will be normalized "
				"to 100% for the weighted risk calculation."
			)

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
			top_correlations, risk_score, correlation_matrix = analysis_results
			total_weight = sum(
				st.session_state[f"portfolio_weight_{coin_id}"]
				for coin_id in selected_coins
			)
			if total_weight:
				normalized_weights = pd.Series(
					{
						coin_id: st.session_state[f"portfolio_weight_{coin_id}"] / total_weight
						for coin_id in selected_coins
					}
				)
			else:
				normalized_weights = pd.Series(
					1 / len(selected_coins),
					index=selected_coins,
				)
				st.warning(
					"All portfolio weights are 0%. Equal weights were used for the "
					"weighted risk calculation."
				)
			weighted_risk_score = _calculate_weighted_risk_score(
				correlation_matrix,
				normalized_weights,
			)

			suggested_portfolio: list[tuple[str, str, float]] = []
			new_risk_score: float | None = None
			if len(selected_coins) >= 2:
				focus_sector, suggested_coins, suggested_weights, estimated_risk_score = get_suggested_portfolio(
					selected_coins,
					portfolio_weights,
					correlation_matrix,
					weighted_risk_score,
				)
				if suggested_coins:
					suggested_portfolio = [
						(
							coin_id,
							coin_by_id[coin_id]["name"],
							suggested_weights[coin_id] * 100,
						)
						for coin_id in selected_coins
					]
					suggested_portfolio.extend(
						(
							str(suggestion["id"]),
							str(suggestion["name"]),
							float(suggestion["weight"]) * 100,
						)
						for suggestion in suggested_coins
					)
					new_risk_score = estimated_risk_score
					adjusted_allocation = [
						f"- **{coin_by_id[coin_id]['name']}** — "
						f"{suggested_weights[coin_id] * 100:.0f}%"
						for coin_id in selected_coins
					]
					adjusted_allocation.extend(
						f"- **{suggestion['name']}** ({suggestion['sector']}) — "
						f"{float(suggestion['weight']) * 100:.0f}%"
						for suggestion in suggested_coins
					)
					allocation_text = "\n".join(adjusted_allocation)
					old_score_text = (
						f"{weighted_risk_score:.1f}"
						if weighted_risk_score is not None
						else "N/A"
					)
					new_score_text = (
						f"{estimated_risk_score:.1f}"
						if estimated_risk_score is not None
						else "N/A"
					)
					focus_text = (
						f"Your portfolio is heavily focused on **{focus_sector}**. "
						if focus_sector
						else "To improve sector diversification, "
					)
					suggestion_text = (
						"### Suggested Portfolio\n\n"
						f"{focus_text}to reduce risk from **{old_score_text}/10** to an "
						f"estimated **{new_score_text}/10**, consider this adjusted allocation:\n\n"
						f"{allocation_text}\n\n"
						"*Estimate assumes zero correlation for suggested assets because their "
						"historical correlations are not in the current analysis.*"
					)
					st.info(suggestion_text)
				else:
					st.info(
						"### Diversification Suggestion\n\n"
						"No additional non-stablecoin sector suggestions are available for "
						"this portfolio."
					)

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
					f"including one sentence explaining why the unweighted risk score is {risk_score} "
					f"out of 10 and the weighted risk score is {weighted_risk_score} out of 10)."
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
			score_columns = st.columns(2)
			with score_columns[0]:
				st.metric(
					label="Unweighted Risk Score (Out of 10)",
					value=f"{risk_score} / 10" if risk_score is not None else "N/A",
				)
			with score_columns[1]:
				st.metric(
					label="Weighted Risk Score (Out of 10)",
					value=(
						f"{weighted_risk_score} / 10"
						if weighted_risk_score is not None
						else "N/A"
					),
				)
			if risk_score is None:
				st.caption("An unweighted score requires valid correlations between at least two assets.")
			else:
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
			image_bytes = create_share_card(
				correlation_matrix,
				weighted_risk_score,
				[
					(
						coin_id,
						coin_by_id[coin_id]["name"],
						float(st.session_state[f"portfolio_weight_{coin_id}"]),
					)
					for coin_id in selected_coins
				],
				risk_score,
				suggested_portfolio,
				new_risk_score,
				os.getenv("APP_URL"),
			)
			st.download_button(
				label="📸 Download Share Card",
				data=image_bytes,
				file_name="risk_radar_card.png",
				mime="image/png",
				on_click="ignore",
			)
	st.markdown(
		'<div style="text-align: center; color: #666; font-size: 0.85rem; '
		'margin-top: 50px;">Powered by <b>HansDeploy</b></div>',
		unsafe_allow_html=True,
	)
