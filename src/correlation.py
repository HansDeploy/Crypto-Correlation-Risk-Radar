"""Correlation analysis helpers for cryptocurrency price histories."""

import numpy as np
import pandas as pd


def calculate_correlation_matrix(prices_df: pd.DataFrame) -> pd.DataFrame:
	"""Calculate correlations between coins using their daily percentage returns.

	Args:
		prices_df: DataFrame of raw prices, with dates as rows and coin IDs as
			columns.

	Returns:
		A correlation matrix whose rows and columns correspond to the coins in
		``prices_df``.
	"""
	daily_returns = prices_df.pct_change().dropna()
	return daily_returns.corr()


def get_top_correlations(
	corr_matrix: pd.DataFrame,
) -> list[dict[str, str | float]]:
	"""Return up to three most strongly positively correlated unique coin pairs.

	Self-correlations and duplicate reversed pairs are excluded. Pairs with
	undefined correlations are ignored.

	Args:
		corr_matrix: Square correlation matrix with coin IDs on both axes.

	Returns:
		Up to three dictionaries containing a ``pair`` label and its
		``correlation``, sorted from highest to lowest correlation.
	"""
	if corr_matrix.empty:
		return []

	row_indices, column_indices = np.triu_indices_from(corr_matrix.to_numpy(), k=1)
	pairs: list[dict[str, str | float]] = []

	for row_index, column_index in zip(row_indices, column_indices):
		correlation = corr_matrix.iat[row_index, column_index]
		if pd.isna(correlation):
			continue

		coin_a = corr_matrix.index[row_index]
		coin_b = corr_matrix.columns[column_index]
		pairs.append(
			{
				"pair": f"{coin_a}-{coin_b}",
				"correlation": float(correlation),
			}
		)

	pairs.sort(key=lambda item: item["correlation"], reverse=True)
	return pairs[:3]
