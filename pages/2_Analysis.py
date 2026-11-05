from math import cos, pi, sin

import plotly.graph_objects as go
import streamlit as st

from src.correlation import calculate_correlation_matrix, get_top_correlations
from src.data_fetcher import fetch_historical_prices


def _build_network_figure(
	corr_matrix,
	coin_symbols: dict[str, str],
) -> tuple[go.Figure, bool]:
	"""Build a circular correlation network with edges for strong positive pairs."""
	coins = list(corr_matrix.columns)
	coin_count = len(coins)
	positions = {
		coin: (cos(2 * pi * index / coin_count), sin(2 * pi * index / coin_count))
		for index, coin in enumerate(coins)
	}
	figure = go.Figure()
	has_edges = False

	for first_index, coin_a in enumerate(coins):
		for coin_b in coins[first_index + 1 :]:
			correlation = corr_matrix.at[coin_a, coin_b]
			if not correlation > 0.6:
				continue

			has_edges = True
			strength = min((correlation - 0.6) / 0.4, 1.0)
			figure.add_trace(
				go.Scatter(
					x=[positions[coin_a][0], positions[coin_b][0]],
					y=[positions[coin_a][1], positions[coin_b][1]],
					mode="lines",
					line={
						"color": "#ff4d5a" if correlation > 0.8 else "#ff9b72",
						"width": 2 + strength * 5,
					},
					hovertemplate=(
						f"{coin_symbols.get(coin_a, coin_a)} - "
						f"{coin_symbols.get(coin_b, coin_b)}"
						f"<br>Correlation: {correlation:.2f}<extra></extra>"
					),
					showlegend=False,
				)
			)

	figure.add_trace(
		go.Scatter(
			x=[positions[coin][0] for coin in coins],
			y=[positions[coin][1] for coin in coins],
			mode="markers+text",
			text=[coin_symbols.get(coin, coin).upper() for coin in coins],
			textposition="middle center",
			textfont={"color": "#ffffff", "size": 12, "weight": 700},
			marker={
				"size": 58,
				"color": "#14232d",
				"line": {"color": "#00d9d2", "width": 2},
			},
			hovertext=[f"{coin_symbols.get(coin, coin).upper()} ({coin})" for coin in coins],
			hovertemplate="%{hovertext}<extra></extra>",
			showlegend=False,
		)
	)
	figure.update_layout(
		template="plotly_dark",
		height=max(420, len(coins) * 55 + 200),
		paper_bgcolor="rgba(0,0,0,0)",
		plot_bgcolor="rgba(0,0,0,0)",
		showlegend=False,
		hovermode="closest",
		dragmode="pan",
		margin={"l": 30, "r": 30, "t": 20, "b": 20},
		xaxis={"visible": False, "range": [-1.25, 1.25], "fixedrange": False},
		yaxis={
			"visible": False,
			"range": [-1.25, 1.25],
			"scaleanchor": "x",
			"scaleratio": 1,
			"fixedrange": False,
		},
	)
	return figure, has_edges


def render_analysis(
	selected_coins: list[str],
	coin_symbols: dict[str, str] | None = None,
) -> tuple[list[dict[str, str | float]], float | None] | None:
	"""Render market correlations and return the highest correlated pairs.

	Args:
		selected_coins: CoinGecko IDs selected in the main application.
		coin_symbols: Mapping of CoinGecko IDs to display symbols.

	Returns:
		The top three correlation pairs and bounded risk score, or ``None`` if
		price analysis fails. The score is ``None`` when no off-diagonal
		correlations are available.
	"""
	try:
		with st.spinner("Fetching market history and calculating correlations..."):
			prices_df = fetch_historical_prices(selected_coins, days=365)

			if prices_df.empty:
				st.error("No historical price data was found for the selected coins.")
				return None

			corr_matrix = calculate_correlation_matrix(prices_df)
			if corr_matrix.empty:
				st.error("There is not enough price history to calculate correlations.")
				return None

		coin_symbols = coin_symbols or {}
		heatmap_tab, network_tab = st.tabs(["Heatmap", "Network Graph"])
		with heatmap_tab:
			st.subheader("Correlation Heatmap")
			coins = list(corr_matrix.columns)
			figure: go.Figure = go.Figure(
				data=go.Heatmap(
					z=corr_matrix.to_numpy(),
					x=coins,
					y=list(corr_matrix.index),
					colorscale="RdBu_r",
					zmin=-1,
					zmax=1,
					xgap=2,
					ygap=2,
					colorbar={"title": "Correlation"},
					hovertemplate="<b>%{y} / %{x}</b><br>Correlation: %{z:.2f}<extra></extra>",
				)
			)
			for row_index, coin_y in enumerate(corr_matrix.index):
				for column_index, coin_x in enumerate(corr_matrix.columns):
					correlation = corr_matrix.iat[row_index, column_index]
					if correlation != correlation:
						annotation_text = "—"
						text_color = "#111820"
					else:
						annotation_text = f"<b>{correlation:.2f}</b>"
						text_color = "#ffffff" if abs(correlation) >= 0.6 else "#111820"
					figure.add_annotation(
						x=coin_x,
						y=coin_y,
						text=annotation_text,
						showarrow=False,
						font={"color": text_color, "size": 15},
					)

			figure.update_layout(
				template="plotly_dark",
				height=len(selected_coins) * 50 + 200,
				paper_bgcolor="rgba(0,0,0,0)",
				plot_bgcolor="rgba(0,0,0,0)",
				xaxis_title=None,
				yaxis_title=None,
				margin={"l": 20, "r": 20, "t": 20, "b": 20},
			)
			st.plotly_chart(figure, width="stretch")
		with network_tab:
			st.subheader("Correlation Network")
			network_figure, has_edges = _build_network_figure(corr_matrix, coin_symbols)
			st.plotly_chart(network_figure, config={"scrollZoom": True}, width="stretch")
			if not has_edges:
				st.caption("No pairs have a positive correlation above 0.60.")

		top_correlations = get_top_correlations(corr_matrix)[:3]
		highest_pair = None
		highest_absolute_correlation = -1.0
		for row_index in range(len(corr_matrix.index)):
			for column_index in range(row_index + 1, len(corr_matrix.columns)):
				correlation = corr_matrix.iat[row_index, column_index]
				if correlation == correlation and abs(correlation) > highest_absolute_correlation:
					highest_absolute_correlation = abs(correlation)
					highest_pair = {
						"pair": f"{corr_matrix.index[row_index]}-{corr_matrix.columns[column_index]}",
						"correlation": float(correlation),
					}
		st.subheader("Highest Correlation Pairs")
		if highest_pair:
			st.dataframe(
				[highest_pair],
				hide_index=True,
				width="stretch",
			)
		else:
			st.info("No valid coin pairs are available to compare.")

		off_diagonal_correlations = [
			float(corr_matrix.iat[row_index, column_index])
			for row_index in range(len(corr_matrix.index))
			for column_index in range(len(corr_matrix.columns))
			if row_index != column_index
			and corr_matrix.iat[row_index, column_index]
			== corr_matrix.iat[row_index, column_index]
		]
		if off_diagonal_correlations:
			avg_corr = sum(off_diagonal_correlations) / len(off_diagonal_correlations)
			risk_score = min(10.0, max(0.0, round(avg_corr * 10, 1)))
		else:
			risk_score = None
		return top_correlations, risk_score
	except Exception as error:
		st.error(f"Analysis failed. Please try again. Details: {error}")
		return None
