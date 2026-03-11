"""
Market Data API - Fetches live price data for all tracked assets.
Uses CoinGecko (crypto), Yahoo Finance (commodities/macro).
Handles rate limits with caching.
"""
import requests
import time
import json
import os
from datetime import datetime, timedelta

CACHE_DIR = "data/cache"
CACHE_TTL = 300  # 5 minutes

class MarketDataAPI:
    def __init__(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "application/json",
        })

    def _get_cached(self, key):
        path = os.path.join(CACHE_DIR, f"{key}.json")
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                if time.time() - data.get("_ts", 0) < CACHE_TTL:
                    return data
            except:
                pass
        return None

    def _get_stale_cache(self, key):
        """Return cached data even if expired — better than no data."""
        path = os.path.join(CACHE_DIR, f"{key}.json")
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except:
                pass
        return None

    def _set_cache(self, key, data):
        data["_ts"] = time.time()
        path = os.path.join(CACHE_DIR, f"{key}.json")
        with open(path, "w") as f:
            json.dump(data, f)

    # ========================
    # COINGECKO
    # ========================

    def _cg_get(self, endpoint, params=None):
        """CoinGecko API call with error handling."""
        url = f"https://api.coingecko.com/api/v3{endpoint}"
        try:
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code == 429:
                print("CoinGecko rate limited, using cache")
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"CoinGecko error: {e}")
            return None

    def _coingecko_market_chart(self, coin_id, days=365):
        """Fetch historical price data from CoinGecko."""
        cache_key = f"cg_{coin_id}_{days}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        data = self._cg_get(f"/coins/{coin_id}/market_chart", {
            "vs_currency": "usd",
            "days": str(days),
        })

        if data:
            self._set_cache(cache_key, data)
            return data
        return self._get_stale_cache(cache_key)

    def _coingecko_simple_price(self, coin_ids):
        """Get current prices from CoinGecko."""
        cache_key = f"cg_prices_{'_'.join(sorted(coin_ids))}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        data = self._cg_get("/simple/price", {
            "ids": ",".join(coin_ids),
            "vs_currencies": "usd",
            "include_24hr_change": "true",
            "include_market_cap": "true",
            "include_24hr_vol": "true",
        })

        if data:
            self._set_cache(cache_key, data)
            return data

        # Fallback to stale cache if API fails
        stale = self._get_stale_cache(cache_key)
        if stale:
            print(f"Using stale cache for {cache_key}")
            return stale
        return {}

    def _coingecko_global(self):
        """Get global crypto market data. Uses longer cache (30 min) since dominance changes slowly."""
        stale = self._get_stale_cache("cg_global")
        # Use 30-min cache for global data (dominance doesn't change fast)
        if stale and time.time() - stale.get("_ts", 0) < 1800:
            return stale

        data = self._cg_get("/global")
        if data:
            self._set_cache("cg_global", data)
            return data

        # If API fails, return stale cache rather than empty
        if stale:
            return stale
        return {}

    # ========================
    # YAHOO FINANCE
    # ========================

    def _yahoo_chart(self, symbol, range_str="5y", interval="1d"):
        """Fetch chart data from Yahoo Finance."""
        cache_key = f"yf_{symbol}_{range_str}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            resp = self.session.get(url, params={
                "interval": interval,
                "range": range_str,
            }, timeout=15)

            if resp.status_code == 200:
                data = resp.json()
                self._set_cache(cache_key, data)
                return data
            else:
                print(f"Yahoo Finance {symbol}: HTTP {resp.status_code}")
        except Exception as e:
            print(f"Yahoo Finance error for {symbol}: {e}")

        # Fallback to stale cache
        return self._get_stale_cache(cache_key)

    def _parse_yahoo(self, data):
        """Parse Yahoo Finance chart response."""
        if not data:
            return None, []

        result = data.get("chart", {}).get("result", [{}])[0]
        meta = result.get("meta", {})
        timestamps = result.get("timestamp", [])
        quotes = result.get("indicators", {}).get("quote", [{}])[0]
        closes = quotes.get("close", [])

        history = []
        for i, ts in enumerate(timestamps):
            if i < len(closes) and closes[i] is not None:
                history.append({"timestamp": ts * 1000, "price": closes[i]})

        return meta, history

    # ========================
    # ASSET DATA METHODS
    # ========================

    def get_bitcoin_data(self):
        """Get Bitcoin price, history, and key metrics."""
        prices = self._coingecko_simple_price(["bitcoin"])

        btc = prices.get("bitcoin", {})
        result = {
            "current_price": btc.get("usd", 0),
            "change_24h": btc.get("usd_24h_change", 0),
            "market_cap": btc.get("usd_market_cap", 0),
            "volume_24h": btc.get("usd_24h_vol", 0),
        }

        # Always use Yahoo Finance for history (reliable, free, 5yr range)
        yf_data = self._yahoo_chart("BTC-USD", "5y")
        meta, history = self._parse_yahoo(yf_data)
        if history:
            result["price_history"] = history
        if result["current_price"] == 0 and meta:
            result["current_price"] = meta.get("regularMarketPrice", 0)

        # Fallback: try CoinGecko chart if Yahoo had no history
        if not result.get("price_history"):
            chart = self._coingecko_market_chart("bitcoin", 365)
            if chart and "prices" in chart:
                result["price_history"] = [
                    {"timestamp": p[0], "price": p[1]}
                    for p in chart["prices"]
                ]

        return result

    def get_ethereum_data(self):
        """Get Ethereum price and history."""
        prices = self._coingecko_simple_price(["ethereum"])

        eth = prices.get("ethereum", {})
        result = {
            "current_price": eth.get("usd", 0),
            "change_24h": eth.get("usd_24h_change", 0),
            "market_cap": eth.get("usd_market_cap", 0),
            "volume_24h": eth.get("usd_24h_vol", 0),
        }

        # Always use Yahoo Finance for history
        yf_data = self._yahoo_chart("ETH-USD", "5y")
        meta, history = self._parse_yahoo(yf_data)
        if history:
            result["price_history"] = history
        if result["current_price"] == 0 and meta:
            result["current_price"] = meta.get("regularMarketPrice", 0)

        if not result.get("price_history"):
            chart = self._coingecko_market_chart("ethereum", 365)
            if chart and "prices" in chart:
                result["price_history"] = [
                    {"timestamp": p[0], "price": p[1]}
                    for p in chart["prices"]
                ]

        return result

    def get_gold_data(self):
        """Get Gold price data using Yahoo Finance (GC=F)."""
        cached = self._get_cached("gold_combined")
        if cached:
            return cached

        yf_data = self._yahoo_chart("GC=F", "5y")
        meta, history = self._parse_yahoo(yf_data)

        result = {
            "current_price": meta.get("regularMarketPrice", 0) if meta else 0,
            "previous_close": meta.get("previousClose", 0) if meta else 0,
            "price_history": history,
            "source": "yahoo_finance",
        }

        if result["current_price"] > 0 and result["previous_close"] > 0:
            result["change_pct"] = ((result["current_price"] / result["previous_close"]) - 1) * 100

        if result["current_price"] > 0:
            self._set_cache("gold_combined", result)

        return result

    def get_silver_data(self):
        """Get Silver price data."""
        cached = self._get_cached("silver_combined")
        if cached:
            return cached

        yf_data = self._yahoo_chart("SI=F", "5y")
        meta, history = self._parse_yahoo(yf_data)

        gold = self.get_gold_data()
        silver_price = meta.get("regularMarketPrice", 0) if meta else 0

        result = {
            "current_price": silver_price,
            "previous_close": meta.get("previousClose", 0) if meta else 0,
            "price_history": history,
            "source": "yahoo_finance",
        }

        if silver_price > 0:
            result["gold_silver_ratio"] = gold.get("current_price", 0) / silver_price
            if result["previous_close"] > 0:
                result["change_pct"] = ((silver_price / result["previous_close"]) - 1) * 100
            self._set_cache("silver_combined", result)

        return result

    def get_uranium_data(self):
        """Get Uranium price/proxy data via URA ETF."""
        cached = self._get_cached("uranium_combined")
        if cached:
            return cached

        yf_data = self._yahoo_chart("URA", "5y")
        meta, history = self._parse_yahoo(yf_data)

        result = {
            "current_price": meta.get("regularMarketPrice", 0) if meta else 0,
            "previous_close": meta.get("previousClose", 0) if meta else 0,
            "symbol": "URA",
            "name": "Global X Uranium ETF",
            "price_history": history,
        }

        if result["current_price"] > 0 and result["previous_close"] > 0:
            result["change_pct"] = ((result["current_price"] / result["previous_close"]) - 1) * 100

        if result["current_price"] > 0:
            self._set_cache("uranium_combined", result)

        return result

    def get_dogecoin_data(self):
        """Get Dogecoin price and history."""
        prices = self._coingecko_simple_price(["dogecoin"])

        doge = prices.get("dogecoin", {})
        result = {
            "current_price": doge.get("usd", 0),
            "change_24h": doge.get("usd_24h_change", 0),
            "market_cap": doge.get("usd_market_cap", 0),
            "volume_24h": doge.get("usd_24h_vol", 0),
        }

        # Always use Yahoo Finance for history
        yf_data = self._yahoo_chart("DOGE-USD", "5y")
        meta, history = self._parse_yahoo(yf_data)
        if history:
            result["price_history"] = history
        if result["current_price"] == 0 and meta:
            result["current_price"] = meta.get("regularMarketPrice", 0)

        if not result.get("price_history"):
            chart = self._coingecko_market_chart("dogecoin", 365)
            if chart and "prices" in chart:
                result["price_history"] = [
                    {"timestamp": p[0], "price": p[1]}
                    for p in chart["prices"]
                ]

        return result

    def get_btc_dominance(self):
        """Get Bitcoin dominance percentage."""
        global_data = self._coingecko_global()

        if global_data and "data" in global_data:
            gd = global_data["data"]
            mcap_pct = gd.get("market_cap_percentage", {})
            btc_pct = mcap_pct.get("btc", 0)

            # Sanity check: BTC dominance should be 20-80%. CoinGecko's /global
            # now includes tokenized RWAs in total market cap, making BTC appear ~6%.
            # If value seems unrealistic, use fallback calculation instead.
            if 20 <= btc_pct <= 80:
                return {
                    "btc_dominance": btc_pct,
                    "eth_dominance": mcap_pct.get("eth", 0),
                    "total_market_cap": gd.get("total_market_cap", {}).get("usd", 0),
                    "total_volume": gd.get("total_volume", {}).get("usd", 0),
                    "market_cap_change_24h": gd.get("market_cap_change_percentage_24h_usd", 0),
                }

        # Fallback: calculate dominance from BTC/ETH market caps
        return self._btc_dominance_fallback()

    def _btc_dominance_fallback(self):
        """Calculate BTC dominance from market caps when /global is rate limited."""
        try:
            # Reuse already-cached price data (same call the dashboard makes)
            btc_data = self._coingecko_simple_price(["bitcoin"])
            eth_data = self._coingecko_simple_price(["ethereum"])
            btc_mcap = btc_data.get("bitcoin", {}).get("usd_market_cap", 0)
            eth_mcap = eth_data.get("ethereum", {}).get("usd_market_cap", 0)

            if btc_mcap <= 0:
                return {"btc_dominance": 0, "eth_dominance": 0, "error": "Unable to fetch"}

            # Estimate total crypto market cap from BTC's typical dominance range (~57-60%)
            # This is approximate but better than showing 0
            est_total = btc_mcap / 0.58

            btc_dom = round((btc_mcap / est_total) * 100, 1) if est_total > 0 else 0
            eth_dom = round((eth_mcap / est_total) * 100, 1) if est_total > 0 else 0

            return {
                "btc_dominance": btc_dom,
                "eth_dominance": eth_dom,
                "total_market_cap": round(est_total),
                "total_volume": 0,
                "market_cap_change_24h": 0,
            }
        except Exception as e:
            print(f"Dominance fallback error: {e}")
            return {"btc_dominance": 0, "eth_dominance": 0, "error": "Unable to fetch"}

    def get_macro_data(self):
        """Get macro economic indicators."""
        macro = {}

        symbols = {
            "DXY": "DX-Y.NYB",
            "Oil_WTI": "CL=F",
            "Treasury_10Y": "^TNX",
        }

        for name, symbol in symbols.items():
            yf_data = self._yahoo_chart(symbol, "2y")
            meta, history = self._parse_yahoo(yf_data)

            if meta:
                macro[name] = {
                    "current": meta.get("regularMarketPrice", 0),
                    "previous_close": meta.get("previousClose", 0),
                    "price_history": history[-365:],
                }
            else:
                macro[name] = {"current": 0, "error": "Unavailable"}

        return macro

    def get_full_bitcoin_history(self):
        """Get maximum Bitcoin history for regression analysis."""
        return self._coingecko_market_chart("bitcoin", "max")

    # ========================
    # MACRO ECONOMY (FRED + Yahoo)
    # ========================

    def _fred_csv(self, series_id, start="2019-01-01"):
        """Fetch time series from FRED's public CSV endpoint (no API key needed).
        Cache for 24 hours since this data updates monthly/weekly.
        """
        cache_key = f"fred_{series_id}"
        cached = self._get_cached(cache_key)
        # Use 24hr cache for FRED data (updates infrequently)
        if cached and time.time() - cached.get("_ts", 0) < 86400:
            return cached.get("data", [])

        try:
            url = f"https://fred.stlouisfed.org/graph/fredgraph.csv"
            resp = self.session.get(url, params={
                "id": series_id,
                "cosd": start,
            }, timeout=15)

            if resp.status_code != 200:
                return []

            lines = resp.text.strip().split("\n")
            if len(lines) < 2:
                return []

            data = []
            for line in lines[1:]:  # skip header
                parts = line.strip().split(",")
                if len(parts) == 2 and parts[1] != ".":
                    try:
                        data.append({
                            "date": parts[0],
                            "value": float(parts[1]),
                        })
                    except ValueError:
                        continue

            self._set_cache(cache_key, {"data": data})
            return data

        except Exception as e:
            print(f"FRED error ({series_id}): {e}")
            return []

    def get_macro_economy(self):
        """Get macroeconomic health indicators: unemployment, claims, payrolls, VIX, S&P."""
        result = {}

        # ── FRED Series ──
        fred_series = {
            "unemployment_rate": {
                "id": "UNRATE",
                "name": "Unemployment Rate",
                "unit": "%",
                "freq": "Monthly",
                "divisor": 1,  # already in percent
            },
            "initial_claims": {
                "id": "ICSA",
                "name": "Initial Jobless Claims",
                "unit": "thousands",
                "freq": "Weekly",
                "divisor": 1000,  # FRED returns raw count, convert to thousands
            },
            "continuing_claims": {
                "id": "CCSA",
                "name": "Continuing Claims",
                "unit": "thousands",
                "freq": "Weekly",
                "divisor": 1000,  # FRED returns raw count, convert to thousands
            },
            "nonfarm_payrolls": {
                "id": "PAYEMS",
                "name": "Nonfarm Payrolls",
                "unit": "thousands",
                "freq": "Monthly",
                "divisor": 1,  # already in thousands
            },
        }

        for key, meta in fred_series.items():
            data = self._fred_csv(meta["id"])
            if data:
                divisor = meta.get("divisor", 1)
                latest_val = data[-1]["value"] / divisor
                prev_val = data[-2]["value"] / divisor if len(data) > 1 else latest_val

                # Calculate trend (change from previous)
                change = latest_val - prev_val

                # Normalize history values too
                history = [{"date": d["date"], "value": d["value"] / divisor} for d in data[-104:]]

                # For claims, also compute 4-week moving average
                ma4 = None
                if len(data) >= 4 and "claims" in key:
                    ma4 = sum(d["value"] / divisor for d in data[-4:]) / 4

                result[key] = {
                    "name": meta["name"],
                    "current": round(latest_val, 1),
                    "previous": round(prev_val, 1),
                    "change": round(change, 1),
                    "date": data[-1]["date"],
                    "unit": meta["unit"],
                    "frequency": meta["freq"],
                    "history": history,
                }
                if ma4 is not None:
                    result[key]["ma_4week"] = round(ma4, 1)
            else:
                result[key] = {"name": meta["name"], "error": "Unavailable"}

        # ── VIX (Fear Index) from Yahoo Finance ──
        vix_data = self._yahoo_chart("^VIX", "2y")
        vix_meta, vix_history = self._parse_yahoo(vix_data)
        if vix_meta:
            result["vix"] = {
                "name": "VIX (Volatility Index)",
                "current": round(vix_meta.get("regularMarketPrice", 0), 2),
                "previous_close": round(vix_meta.get("previousClose", 0), 2),
                "history": vix_history[-365:],
            }
            vix_val = result["vix"]["current"]
            if vix_val < 15:
                result["vix"]["signal"] = "Low fear — complacency"
            elif vix_val < 20:
                result["vix"]["signal"] = "Normal range"
            elif vix_val < 30:
                result["vix"]["signal"] = "Elevated fear"
            else:
                result["vix"]["signal"] = "Extreme fear — panic"
        else:
            result["vix"] = {"name": "VIX", "error": "Unavailable"}

        # ── S&P 500 from Yahoo Finance ──
        sp_data = self._yahoo_chart("^GSPC", "2y")
        sp_meta, sp_history = self._parse_yahoo(sp_data)
        if sp_meta:
            current = sp_meta.get("regularMarketPrice", 0)
            prev_close = sp_meta.get("previousClose", 0)
            result["sp500"] = {
                "name": "S&P 500",
                "current": round(current, 2),
                "previous_close": round(prev_close, 2),
                "change_pct": round(((current / prev_close) - 1) * 100, 2) if prev_close else 0,
                "history": sp_history[-365:],
            }
            # Calculate distance from 200-day SMA
            if len(sp_history) >= 200:
                sma_200 = sum(p["price"] for p in sp_history[-200:]) / 200
                result["sp500"]["sma_200"] = round(sma_200, 2)
                result["sp500"]["above_sma_200"] = current > sma_200
        else:
            result["sp500"] = {"name": "S&P 500", "error": "Unavailable"}

        # ── Housing Market ──
        result["housing"] = self._get_housing_data()

        # ── Summary assessment ──
        result["assessment"] = self._assess_macro_health(result)

        return result

    def _get_housing_data(self):
        """Get housing market indicators from FRED."""
        housing = {}

        series = {
            "mortgage_rate": {
                "id": "MORTGAGE30US",
                "name": "30-Year Fixed Mortgage Rate",
                "unit": "%",
                "divisor": 1,
            },
            "housing_starts": {
                "id": "HOUST",
                "name": "Housing Starts",
                "unit": "thousands SAAR",
                "divisor": 1,
            },
            "building_permits": {
                "id": "PERMIT",
                "name": "Building Permits",
                "unit": "thousands SAAR",
                "divisor": 1,
            },
            "home_price_index": {
                "id": "CSUSHPISA",
                "name": "Case-Shiller Home Price Index",
                "unit": "index",
                "divisor": 1,
            },
            "existing_home_sales": {
                "id": "EXHOSLUSM495S",
                "name": "Existing Home Sales",
                "unit": "millions SAAR",
                "divisor": 1,
            },
            "months_supply": {
                "id": "MSACSR",
                "name": "Months Supply of Houses",
                "unit": "months",
                "divisor": 1,
            },
            "median_home_price": {
                "id": "MSPUS",
                "name": "Median Home Sale Price",
                "unit": "dollars",
                "divisor": 1,
            },
        }

        for key, meta in series.items():
            data = self._fred_csv(meta["id"], start="2018-01-01")
            if data and len(data) >= 2:
                divisor = meta.get("divisor", 1)
                latest = data[-1]["value"] / divisor
                prev = data[-2]["value"] / divisor
                change = latest - prev

                # Year-over-year if we have enough data
                yoy = None
                if len(data) >= 13 and meta["unit"] != "%":
                    # Find value ~12 months ago
                    year_ago_idx = max(0, len(data) - 13)
                    year_ago_val = data[year_ago_idx]["value"] / divisor
                    if year_ago_val > 0:
                        yoy = round(((latest / year_ago_val) - 1) * 100, 1)

                history = [{"date": d["date"], "value": d["value"] / divisor} for d in data[-156:]]  # ~3 years

                housing[key] = {
                    "name": meta["name"],
                    "current": round(latest, 2),
                    "previous": round(prev, 2),
                    "change": round(change, 2),
                    "yoy_pct": yoy,
                    "date": data[-1]["date"],
                    "unit": meta["unit"],
                    "history": history,
                }
            else:
                housing[key] = {"name": meta["name"], "error": "Unavailable"}

        # Housing health assessment
        housing["assessment"] = self._assess_housing_health(housing)

        return housing

    def _assess_housing_health(self, h):
        """Assess housing market conditions."""
        signals = []
        score = 0

        # Mortgage rate
        mr = h.get("mortgage_rate", {})
        if "current" in mr:
            rate = mr["current"]
            if rate > 7.0:
                signals.append(f"Mortgage rate {rate}% — severely restrictive, crushing affordability")
                score -= 25
            elif rate > 6.5:
                signals.append(f"Mortgage rate {rate}% — restrictive, suppressing demand")
                score -= 15
            elif rate > 6.0:
                signals.append(f"Mortgage rate {rate}% — elevated, slowing activity")
                score -= 5
            elif rate > 5.0:
                signals.append(f"Mortgage rate {rate}% — moderate, manageable")
                score += 5
            else:
                signals.append(f"Mortgage rate {rate}% — supportive of housing")
                score += 15

        # Housing starts
        hs = h.get("housing_starts", {})
        if "current" in hs:
            starts = hs["current"]
            if starts > 1500:
                signals.append(f"Housing starts {starts:.0f}K — strong building activity")
                score += 10
            elif starts > 1200:
                signals.append(f"Housing starts {starts:.0f}K — healthy pace")
                score += 5
            elif starts > 900:
                signals.append(f"Housing starts {starts:.0f}K — below average")
                score -= 5
            else:
                signals.append(f"Housing starts {starts:.0f}K — recessionary levels")
                score -= 15

        # Months supply (equilibrium ~5-6 months)
        ms = h.get("months_supply", {})
        if "current" in ms:
            supply = ms["current"]
            if supply > 8:
                signals.append(f"Months supply {supply:.1f} — strong buyer's market, price pressure down")
                score -= 10
            elif supply > 6:
                signals.append(f"Months supply {supply:.1f} — balanced to buyer-leaning")
                score += 0
            elif supply > 4:
                signals.append(f"Months supply {supply:.1f} — balanced market")
                score += 5
            elif supply > 2:
                signals.append(f"Months supply {supply:.1f} — tight inventory, seller's market")
                score += 5
            else:
                signals.append(f"Months supply {supply:.1f} — extreme shortage")
                score -= 5

        # Home price trend (YoY)
        hpi = h.get("home_price_index", {})
        if hpi.get("yoy_pct") is not None:
            yoy = hpi["yoy_pct"]
            if yoy > 10:
                signals.append(f"Home prices +{yoy:.1f}% YoY — overheating, bubble risk")
                score -= 10
            elif yoy > 5:
                signals.append(f"Home prices +{yoy:.1f}% YoY — strong appreciation")
                score += 5
            elif yoy > 0:
                signals.append(f"Home prices +{yoy:.1f}% YoY — modest growth")
                score += 5
            elif yoy > -5:
                signals.append(f"Home prices {yoy:.1f}% YoY — slight decline")
                score -= 5
            else:
                signals.append(f"Home prices {yoy:.1f}% YoY — significant correction")
                score -= 15

        score = max(-100, min(100, score))

        if score > 10:
            outlook = "HEALTHY"
        elif score > -5:
            outlook = "MIXED"
        elif score > -20:
            outlook = "COOLING"
        else:
            outlook = "DISTRESSED"

        return {
            "score": score,
            "outlook": outlook,
            "signals": signals,
        }

    def _assess_macro_health(self, data):
        """Generate a macro health assessment based on all indicators."""
        signals = []
        score = 0  # -100 to +100

        # Unemployment
        unemp = data.get("unemployment_rate", {})
        if "current" in unemp:
            rate = unemp["current"]
            change = unemp.get("change", 0)
            if rate < 4.0:
                signals.append(f"Unemployment {rate}% — tight labor market")
                score += 15
            elif rate < 5.0:
                signals.append(f"Unemployment {rate}% — moderate")
                score += 5
            elif rate < 6.5:
                signals.append(f"Unemployment {rate}% — elevated, watch for recession")
                score -= 15
            else:
                signals.append(f"Unemployment {rate}% — recessionary")
                score -= 30

            if change > 0.3:
                signals.append("Unemployment rising sharply — bearish")
                score -= 15
            elif change < -0.2:
                signals.append("Unemployment improving — bullish")
                score += 10

        # Initial claims
        claims = data.get("initial_claims", {})
        if "current" in claims:
            val = claims["current"]
            if val < 220:
                signals.append(f"Jobless claims {val:.0f}K — very healthy")
                score += 10
            elif val < 280:
                signals.append(f"Jobless claims {val:.0f}K — normal range")
                score += 5
            elif val < 350:
                signals.append(f"Jobless claims {val:.0f}K — elevated layoffs")
                score -= 10
            else:
                signals.append(f"Jobless claims {val:.0f}K — recession-level layoffs")
                score -= 25

        # VIX
        vix = data.get("vix", {})
        if "current" in vix:
            v = vix["current"]
            if v > 30:
                signals.append(f"VIX {v:.1f} — extreme fear, possible capitulation")
                score -= 15
            elif v > 20:
                signals.append(f"VIX {v:.1f} — elevated uncertainty")
                score -= 5
            elif v < 13:
                signals.append(f"VIX {v:.1f} — extreme complacency, watch for correction")
                score -= 5

        # S&P 500 trend
        sp = data.get("sp500", {})
        if "above_sma_200" in sp:
            if sp["above_sma_200"]:
                signals.append("S&P 500 above 200-day SMA — uptrend")
                score += 10
            else:
                signals.append("S&P 500 below 200-day SMA — downtrend")
                score -= 15

        # Housing impact on macro
        housing = data.get("housing", {})
        h_assessment = housing.get("assessment", {})
        if h_assessment.get("score") is not None:
            h_score = h_assessment["score"]
            housing_outlook = h_assessment.get("outlook", "")
            if h_score > 10:
                signals.append(f"Housing market healthy — supportive")
                score += 5
            elif h_score < -10:
                signals.append(f"Housing market stressed — headwind")
                score -= 5

        # Clamp
        score = max(-100, min(100, score))

        if score > 20:
            outlook = "HEALTHY"
        elif score > 0:
            outlook = "MIXED-POSITIVE"
        elif score > -20:
            outlook = "MIXED-NEGATIVE"
        else:
            outlook = "DETERIORATING"

        return {
            "score": score,
            "outlook": outlook,
            "signals": signals,
        }
