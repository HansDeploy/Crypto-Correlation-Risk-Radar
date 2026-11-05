"""Fetch and align historical cryptocurrency prices from CoinGecko."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from math import isfinite
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st

logger = logging.getLogger(__name__)

_MARKET_CHART_URL = "https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
_MARKET_LIST_URL = "https://api.coingecko.com/api/v3/coins/markets"
_REQUEST_TIMEOUT = (5, 30)
_MAX_RATE_LIMIT_RETRIES = 2
_MAX_RETRY_DELAY_SECONDS = 30
_FALLBACK_TOP_COINS = [
	{"id": "bitcoin", "symbol": "BTC", "name": "Bitcoin"},
	{"id": "ethereum", "symbol": "ETH", "name": "Ethereum"},
	{"id": "tether", "symbol": "USDT", "name": "Tether"},
	{"id": "binancecoin", "symbol": "BNB", "name": "BNB"},
	{"id": "solana", "symbol": "SOL", "name": "Solana"},
	{"id": "usd-coin", "symbol": "USDC", "name": "USDC"},
	{"id": "ripple", "symbol": "XRP", "name": "XRP"},
	{"id": "staked-ether", "symbol": "STETH", "name": "Lido Staked Ether"},
	{"id": "dogecoin", "symbol": "DOGE", "name": "Dogecoin"},
	{"id": "the-open-network", "symbol": "TON", "name": "Toncoin"},
	{"id": "tron", "symbol": "TRX", "name": "TRON"},
	{"id": "cardano", "symbol": "ADA", "name": "Cardano"},
	{"id": "avalanche-2", "symbol": "AVAX", "name": "Avalanche"},
	{"id": "shiba-inu", "symbol": "SHIB", "name": "Shiba Inu"},
	{"id": "wrapped-bitcoin", "symbol": "WBTC", "name": "Wrapped Bitcoin"},
	{"id": "chainlink", "symbol": "LINK", "name": "Chainlink"},
	{"id": "bitcoin-cash", "symbol": "BCH", "name": "Bitcoin Cash"},
	{"id": "polkadot", "symbol": "DOT", "name": "Polkadot"},
	{"id": "uniswap", "symbol": "UNI", "name": "Uniswap"},
	{"id": "litecoin", "symbol": "LTC", "name": "Litecoin"},
]


def _rate_limit_delay(response: requests.Response, attempt: int) -> float:
	"""Return a bounded delay, respecting CoinGecko's Retry-After header."""
	retry_after = response.headers.get("Retry-After")
	if retry_after:
		try:
			delay = float(retry_after)
		except ValueError:
			try:
				retry_time = parsedate_to_datetime(retry_after)
				if retry_time.tzinfo is None:
					retry_time = retry_time.replace(tzinfo=timezone.utc)
				delay = (retry_time - datetime.now(timezone.utc)).total_seconds()
			except (TypeError, ValueError, OverflowError):
				delay = 2**attempt
	else:
		delay = 2**attempt

	return min(max(delay, 0), _MAX_RETRY_DELAY_SECONDS)


def _fetch_single_coin(coin_id: str, days: int) -> pd.Series:
	"""Fetch daily closing prices for one CoinGecko coin ID.

	Args:
		coin_id: CoinGecko's identifier, such as ``"bitcoin"``.
		days: Number of days of market-chart history to request.

	Returns:
		A Series indexed by timezone-naive dates, named with ``coin_id``.

	Raises:
		requests.exceptions.RequestException: If the request fails after any
			applicable rate-limit retries.
	"""
	url = _MARKET_CHART_URL.format(coin_id=quote(coin_id, safe=""))
	params = {"vs_currency": "usd", "days": days}

	for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
		response = requests.get(
			url,
			params=params,
			timeout=_REQUEST_TIMEOUT,
			headers={"Accept": "application/json", "User-Agent": "Crypto-Correlation-Risk-Radar/1.0"},
		)
		if response.status_code != 429:
			response.raise_for_status()
			break

		if attempt == _MAX_RATE_LIMIT_RETRIES:
			response.raise_for_status()

		time.sleep(_rate_limit_delay(response, attempt))

	payload = response.json()
	prices = payload.get("prices") if isinstance(payload, dict) else None
	if not isinstance(prices, list) or not prices:
		return pd.Series(dtype="float64", name=coin_id)

	timestamps: list[object] = []
	values: list[float] = []
	for point in prices:
		if not isinstance(point, (list, tuple)) or len(point) < 2:
			continue
		try:
			timestamp = float(point[0])
			price = float(point[1])
		except (TypeError, ValueError, OverflowError):
			continue
		if isfinite(timestamp) and isfinite(price):
			timestamps.append(timestamp)
			values.append(price)

	if not timestamps:
		return pd.Series(dtype="float64", name=coin_id)

	index = pd.to_datetime(timestamps, unit="ms", utc=True, errors="coerce")
	series = pd.Series(values, index=index, name=coin_id).dropna()
	series = series[~series.index.isna()]
	if series.empty:
		return pd.Series(dtype="float64", name=coin_id)

	series.index = series.index.tz_localize(None)
	return series.sort_index().resample("D").last().dropna().rename(coin_id)


@st.cache_data(ttl=86400)
def get_top_coins_list(limit: int = 500) -> list[dict]:
	"""Fetch the highest market-cap coins, falling back to a static list.

	Args:
		limit: Maximum number of coins to return. CoinGecko's 250-item page limit
			is handled internally through pagination.

	Returns:
		A list of dictionaries containing ``id``, uppercase ``symbol``, ``name``,
		and the CoinGecko image URL. On an API or response error, returns up to
		20 fallback coins with empty image URLs.

	Raises:
		ValueError: If ``limit`` is not a positive integer.
	"""
	if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
		raise ValueError("limit must be a positive integer")

	coins: list[dict] = []
	per_page = min(limit, 250)
	page = 1

	try:
		while len(coins) < limit:
			response = requests.get(
				_MARKET_LIST_URL,
				params={
					"vs_currency": "usd",
					"order": "market_cap_desc",
					"per_page": per_page,
					"page": page,
				},
				timeout=_REQUEST_TIMEOUT,
				headers={"Accept": "application/json", "User-Agent": "Crypto-Correlation-Risk-Radar/1.0"},
			)
			response.raise_for_status()
			page_coins = response.json()
			if not isinstance(page_coins, list):
				raise ValueError("CoinGecko returned an invalid coin list")

			for coin in page_coins:
				if not isinstance(coin, dict):
					continue
				coin_id = coin.get("id")
				symbol = coin.get("symbol")
				name = coin.get("name")
				if isinstance(coin_id, str) and isinstance(symbol, str) and isinstance(name, str):
					coins.append(
						{
							"id": coin_id,
							"symbol": symbol.upper(),
							"name": name,
							"image": coin.get("image", ""),
						}
					)
					if len(coins) == limit:
						break

			if len(page_coins) < per_page:
				break
			page += 1
			if page_coins and not any(isinstance(coin, dict) for coin in page_coins):
				break

		if coins:
			return coins
		logger.warning("CoinGecko returned no valid coins; using the fallback coin list")
		return [{**coin, "image": ""} for coin in _FALLBACK_TOP_COINS[:limit]]
	except (requests.exceptions.RequestException, ValueError, TypeError) as error:
		logger.warning("Failed to fetch CoinGecko coin list: %s", error)
		return [{**coin, "image": ""} for coin in _FALLBACK_TOP_COINS[:limit]]


@st.cache_data(ttl=3600)
def fetch_historical_prices(coin_ids: list[str], days: int = 90) -> pd.DataFrame:
	"""Fetch and combine daily USD closing prices for multiple coins.

	Failed coin requests are logged and skipped, allowing successfully fetched
	coins to remain available. The returned index contains timezone-naive dates.

	Args:
		coin_ids: CoinGecko IDs to fetch, for example ``["bitcoin", "ethereum"]``.
		days: Number of historical days to request. Defaults to 90.

	Returns:
		A DataFrame indexed by date with one column per successfully fetched
		coin. Returns an empty DataFrame if no usable price data is found.

	Raises:
		ValueError: If ``days`` is not a positive integer.
	"""
	if isinstance(days, bool) or not isinstance(days, int) or days <= 0:
		raise ValueError("days must be a positive integer")

	if not coin_ids:
		return pd.DataFrame()

	successful_series: list[pd.Series] = []
	seen_coin_ids: set[str] = set()

	for coin_id in coin_ids:
		if not isinstance(coin_id, str) or not coin_id.strip():
			logger.warning("Skipping invalid CoinGecko coin ID: %r", coin_id)
			continue

		coin_id = coin_id.strip()
		if coin_id in seen_coin_ids:
			continue
		seen_coin_ids.add(coin_id)

		try:
			prices = _fetch_single_coin(coin_id, days)
		except (requests.exceptions.RequestException, ValueError, TypeError) as error:
			logger.warning("Failed to fetch prices for %s: %s", coin_id, error)
			continue

		if prices.empty:
			logger.warning("No price data found for %s", coin_id)
			continue
		successful_series.append(prices)

	if not successful_series:
		return pd.DataFrame()

	result = pd.concat(successful_series, axis=1).sort_index()
	result.index.name = "Date"
	return result
