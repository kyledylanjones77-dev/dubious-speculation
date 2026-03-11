"""
Cowen Analysis Engine
Implements Benjamin Cowen's key analytical frameworks:

1. Bitcoin Risk Metric (0-1 scale based on logarithmic regression)
2. Logarithmic Regression Bands (fair value model)
3. Bull Market Support Band (20W SMA + 21W EMA)
4. Bear Market Resistance Band (key resistance zones)
5. 4-Year Cycle Analysis (halving-based)
6. Bitcoin Dominance Framework
7. Macro Overlay (DXY, rates, oil, business cycles)
8. Asset-specific analysis for Gold, Silver, Uranium, ETH

The engine combines these indicators to produce 30/60/180 day forecasts.
"""
import numpy as np
import json
import os
import math
from datetime import datetime, timedelta
from api.market_data import MarketDataAPI

# Bitcoin Genesis Block: Jan 3, 2009
BTC_GENESIS = datetime(2009, 1, 3)

# Halving dates
HALVING_DATES = [
    datetime(2012, 11, 28),  # Block 210,000
    datetime(2016, 7, 9),    # Block 420,000
    datetime(2020, 5, 11),   # Block 630,000
    datetime(2024, 4, 20),   # Block 840,000 (estimated)
]

class CowenAnalysisEngine:
    def __init__(self):
        self.market_api = MarketDataAPI()
        self.knowledge_base = self._load_knowledge_base()
        self.cowen_thesis = self._load_cowen_thesis()

    def _load_cowen_thesis(self):
        """Load Cowen's specific 2026 thesis extracted from transcript analysis."""
        insights_path = "data/latest_insights.json"
        if os.path.exists(insights_path):
            try:
                with open(insights_path, "r") as f:
                    data = json.load(f)
                return data.get("current_market_thesis", {})
            except Exception:
                pass
        return {}

    def _load_knowledge_base(self):
        """Load and merge extracted insights with default frameworks."""
        defaults = self._default_knowledge_base()
        kb_path = "data/knowledge_base.json"
        if os.path.exists(kb_path):
            try:
                with open(kb_path, "r") as f:
                    file_kb = json.load(f)
                # Merge file data into defaults (file enriches, doesn't replace)
                for key, val in file_kb.items():
                    if key not in defaults:
                        defaults[key] = val
            except Exception:
                pass
        return defaults

    def _default_knowledge_base(self):
        """
        Default knowledge base built from Cowen's well-known frameworks.
        This gets enriched as more transcripts are processed.
        """
        return {
            "frameworks": {
                "risk_metric": {
                    "description": "Bitcoin risk metric on 0-1 scale using log regression distance",
                    "extreme_low": 0.1,  # Strong buy zone
                    "low": 0.3,          # Accumulation zone
                    "neutral": 0.5,      # Fair value
                    "high": 0.7,         # Taking profits
                    "extreme_high": 0.9, # Blow-off top risk
                },
                "cycle_timing": {
                    "description": "4-year halving cycle framework",
                    "typical_peak_months_after_halving": [12, 18],
                    "typical_bottom_months_after_peak": [12, 14],
                    "midterm_year_pattern": "Historically weaker, consolidation period",
                    "pre_halving_year": "Typically recovery year",
                    "halving_year": "Mixed, often sideways with late-year push",
                    "post_halving_year": "Historically strongest year",
                },
                "btc_dominance": {
                    "description": "Bitcoin dominance cycle framework",
                    "alt_season_threshold": 40,  # Below 40% = alt season likely
                    "btc_season_threshold": 60,   # Above 60% = BTC season
                    "current_cycle_view": "Dominance tends to rise in bear markets, fall in bull markets",
                    "lengthening_dominance_cycles": True,
                },
                "regression_bands": {
                    "description": "Logarithmic regression bands for fair value",
                    "model": "log10",
                    "coefficients": {
                        # log10(price) = a * ln(days_since_genesis) + b
                        # Cowen's actual model uses log10 base for price
                        # Fitted using least-squares on non-bubble consolidation data (2012-2026)
                        # Green band (fair value) fitted to stable price periods
                        "a": 2.327,     # slope in log10(price) vs ln(days) space
                        "b": -15.375,   # intercept
                    },
                    "band_offsets": {
                        # Parallel bands offset from fair value by adjusting b
                        # Each band shares the same slope a, different intercept
                        "bottom": -0.6,    # deep bear territory
                        "low": -0.4,       # accumulation zone
                        "mid_low": -0.2,   # approaching fair value
                        "fair": 0.0,       # fair value (green line)
                        "mid_high": 0.2,   # above fair value
                        "high": 0.4,       # overheated
                        "top": 0.6,        # speculative peak zone (red line)
                    }
                },
                "bull_market_support_band": {
                    "description": "20-week SMA and 21-week EMA",
                    "bull_signal": "Price above both = bullish",
                    "bear_signal": "Price below both = bearish",
                    "crossover": "20W SMA crossing 21W EMA = trend change signal",
                },
                "200w_sma": {
                    "description": "200-week SMA as ultimate support in bull markets",
                    "rule": "When 200W SMA crosses prior ATH, cycle top is likely in",
                    "bear_support": "200W SMA acts as bear market support",
                },
                "macro_framework": {
                    "dxy": "Strong dollar = headwind for BTC. Weak dollar = tailwind.",
                    "fed_rates": "Rate cuts historically bullish for risk assets with lag",
                    "oil": "Oil spikes often end business cycles, bearish for everything",
                    "yield_curve": "Inversion = recession warning. Un-inversion = recession imminent.",
                    "business_cycle": "Late cycle = caution. Early cycle = accumulate.",
                },
                "gold_framework": {
                    "description": "Gold as macro hedge and BTC comparison",
                    "btc_gold_ratio": "Rising = risk-on environment, falling = risk-off",
                    "gold_in_midterm_years": "Gold tends to outperform BTC in midterm years",
                    "gold_cycle": "Gold tends to lead crypto in macro shifts",
                },
                "silver_framework": {
                    "gold_silver_ratio": "High ratio (>80) = silver undervalued. Low ratio (<60) = silver overvalued.",
                    "industrial_demand": "Silver has industrial component unlike gold",
                },
                "uranium_framework": {
                    "long_term_thesis": "Supply deficit narrative, multi-year bull case",
                    "volatility": "Can see sharp drawdowns despite long-term bull case",
                },
                "ethereum_framework": {
                    "eth_btc_ratio": "Key metric - tends to bleed against BTC when dominance rises",
                    "eth_in_bear_markets": "ETH typically drops more than BTC",
                    "eth_cycle": "ETH tends to outperform BTC late in bull markets",
                },
            },
            "key_principles": [
                "The market can stay irrational longer than you can stay solvent",
                "Logarithmic regression provides a fair value framework over long timeframes",
                "The 4-year cycle is the primary driver but may be lengthening",
                "Macro conditions override short-term technicals",
                "Bitcoin dominance is a leading indicator for alt season",
                "The 200-week SMA crossing the prior ATH signals cycle exhaustion",
                "Business cycles end with oil spikes and recessions",
                "Midterm years historically weaker for crypto",
                "Post-halving years historically strongest for BTC",
                "Risk management > speculation",
                "DCA into fear, take profits into euphoria",
                "Watch what the market does, not what it says",
            ]
        }

    # ========================
    # BITCOIN RISK METRIC
    # ========================

    def get_risk_metric(self):
        """
        Calculate Bitcoin risk metric (0-1 scale).
        Based on distance from logarithmic regression fair value.

        Method: Compare current price to the log regression line.
        Normalize the distance to produce a 0-1 score.
        """
        btc_data = self.market_api.get_bitcoin_data()
        current_price = btc_data.get("current_price", 0)
        if current_price <= 0:
            return {"risk_score": 0.5, "error": "No price data"}

        # Calculate fair value from log regression
        days_since_genesis = (datetime.now() - BTC_GENESIS).days
        fair_value = self._log_regression_price(days_since_genesis)

        # Calculate risk score using Cowen's approach:
        # Distance in log10 space between price and fair value,
        # normalized against the band range (bottom to top)
        if fair_value > 0 and current_price > 0:
            offsets = self.knowledge_base["frameworks"]["regression_bands"]["band_offsets"]
            bottom_offset = offsets.get("bottom", -0.6)
            top_offset = offsets.get("top", 0.6)
            total_range = top_offset - bottom_offset  # full band range in log10 space

            # Where is current price in log10 space relative to fair value?
            log10_deviation = math.log10(current_price) - math.log10(fair_value)
            # Normalize: bottom_offset -> 0, top_offset -> 1
            risk_score = max(0.0, min(1.0, (log10_deviation - bottom_offset) / total_range))
        else:
            risk_score = 0.5

        # Get cycle position
        cycle_info = self._get_cycle_position()

        # Band levels at current day
        bands = self._get_band_prices(days_since_genesis)

        # Zone classification
        if risk_score <= 0.15:
            zone = "EXTREME ACCUMULATION"
            action = "Maximum accumulation zone. Historically the best time to buy."
        elif risk_score <= 0.3:
            zone = "ACCUMULATION"
            action = "Good accumulation zone. DCA heavily."
        elif risk_score <= 0.45:
            zone = "EARLY BULL"
            action = "Trending up from undervaluation. Continue accumulation."
        elif risk_score <= 0.55:
            zone = "FAIR VALUE"
            action = "Near fair value. Neutral zone."
        elif risk_score <= 0.7:
            zone = "ELEVATED"
            action = "Above fair value. Consider taking some profits."
        elif risk_score <= 0.85:
            zone = "HIGH RISK"
            action = "Well above fair value. Take profits, reduce exposure."
        else:
            zone = "EXTREME RISK"
            action = "Potential blow-off top territory. Maximum caution."

        return {
            "risk_score": round(risk_score, 3),
            "zone": zone,
            "action": action,
            "current_price": current_price,
            "fair_value": round(fair_value, 2),
            "distance_from_fair": f"{((current_price / fair_value) - 1) * 100:.1f}%",
            "days_since_genesis": days_since_genesis,
            "cycle_position": cycle_info,
            "regression_bands": bands,
        }

    def _log_regression_price(self, days, offset=0.0):
        """
        Calculate the log regression price for a given day.
        Uses Cowen's actual model: log10(price) = a * ln(days) + b + offset
        The offset shifts the band up/down in log10 space (parallel bands).
        """
        if days <= 0:
            return 0
        coeffs = self.knowledge_base["frameworks"]["regression_bands"]["coefficients"]
        log_days = math.log(days)  # natural log of days
        log10_price = coeffs["a"] * log_days + coeffs["b"] + offset
        return 10 ** log10_price

    def _get_band_prices(self, days):
        """Get all regression band price levels using parallel offset bands."""
        offsets = self.knowledge_base["frameworks"]["regression_bands"]["band_offsets"]
        return {
            band: round(self._log_regression_price(days, off), 2)
            for band, off in offsets.items()
        }

    # ========================
    # CYCLE ANALYSIS
    # ========================

    def _get_cycle_position(self):
        """Determine where we are in the 4-year halving cycle."""
        now = datetime.now()

        # Find last and next halving
        last_halving = None
        next_halving = None
        for i, h in enumerate(HALVING_DATES):
            if h <= now:
                last_halving = h
            else:
                next_halving = h
                break

        if not next_halving:
            # Estimate next halving ~4 years after last
            next_halving = last_halving + timedelta(days=4 * 365)

        days_since_halving = (now - last_halving).days if last_halving else 0
        days_to_next = (next_halving - now).days
        cycle_length = (next_halving - last_halving).days if last_halving else 1461
        cycle_progress = days_since_halving / cycle_length

        # Determine cycle year
        if cycle_progress < 0.25:
            cycle_year = "Post-Halving Year 1 (historically strongest)"
        elif cycle_progress < 0.5:
            cycle_year = "Year 2 (midterm year - historically weaker)"
        elif cycle_progress < 0.75:
            cycle_year = "Year 3 (pre-halving year - typically recovery)"
        else:
            cycle_year = "Halving Year (historically mixed)"

        return {
            "last_halving": last_halving.isoformat() if last_halving else None,
            "next_halving": next_halving.isoformat() if next_halving else None,
            "days_since_halving": days_since_halving,
            "days_to_next_halving": days_to_next,
            "cycle_progress": round(cycle_progress, 3),
            "cycle_year": cycle_year,
        }

    def get_cycle_analysis(self):
        """Full 4-year cycle analysis."""
        cycle = self._get_cycle_position()
        risk = self.get_risk_metric()

        # Historical cycle patterns
        patterns = {
            "2012_cycle": {
                "halving": "2012-11-28",
                "peak": "2013-11-30",
                "months_to_peak": 12,
                "peak_price": 1100,
                "bottom_after": "2015-01-14",
                "drawdown": "-86%"
            },
            "2016_cycle": {
                "halving": "2016-07-09",
                "peak": "2017-12-17",
                "months_to_peak": 17,
                "peak_price": 19783,
                "bottom_after": "2018-12-15",
                "drawdown": "-84%"
            },
            "2020_cycle": {
                "halving": "2020-05-11",
                "peak": "2021-11-10",
                "months_to_peak": 18,
                "peak_price": 69000,
                "bottom_after": "2022-11-21",
                "drawdown": "-77%"
            },
            "2024_cycle": {
                "halving": "2024-04-20",
                "status": "In progress",
                "note": "Cowen noted no euphoric blow-off top in 2025, possible lengthening cycle"
            }
        }

        # Cowen's key cycle observations
        observations = [
            "Lengthening cycles theory: each cycle takes longer to peak",
            "Diminishing returns: each cycle has lower peak-to-peak multiplier",
            "200W SMA crossing prior ATH signals cycle exhaustion",
            "Midterm years (2 years after halving) historically weakest",
            f"Current cycle progress: {cycle['cycle_progress']*100:.1f}%",
            f"Current cycle year: {cycle['cycle_year']}",
        ]

        return {
            "current_position": cycle,
            "historical_patterns": patterns,
            "observations": observations,
            "risk_metric": risk["risk_score"],
        }

    # ========================
    # BULL/BEAR MARKET BANDS
    # ========================

    def get_bull_market_support_band(self, price_history):
        """
        Calculate the Bull Market Support Band.
        = 20-week SMA and 21-week EMA

        When price is above both -> bullish
        When price is below both -> bearish
        """
        if not price_history:
            return None

        prices = [p["price"] for p in price_history]

        # 20-week SMA (140 daily candles)
        sma_20w = self._sma(prices, 140)
        # 21-week EMA (147 daily candles)
        ema_21w = self._ema(prices, 147)

        current_price = prices[-1] if prices else 0
        sma_val = sma_20w[-1] if sma_20w else 0
        ema_val = ema_21w[-1] if ema_21w else 0

        above_sma = current_price > sma_val
        above_ema = current_price > ema_val

        if above_sma and above_ema:
            signal = "BULLISH - Price above Bull Market Support Band"
        elif not above_sma and not above_ema:
            signal = "BEARISH - Price below Bull Market Support Band"
        else:
            signal = "NEUTRAL - Price between SMA and EMA, trend uncertain"

        return {
            "sma_20w": round(sma_val, 2),
            "ema_21w": round(ema_val, 2),
            "current_price": round(current_price, 2),
            "above_sma": above_sma,
            "above_ema": above_ema,
            "signal": signal,
        }

    def get_200w_sma_analysis(self, price_history):
        """
        200-week SMA analysis.
        Key Cowen rule: When 200W SMA crosses the prior ATH, the cycle top is in.
        """
        if not price_history:
            return None

        prices = [p["price"] for p in price_history]
        sma_200w = self._sma(prices, 1400)  # 200 weeks * 7 days

        if not sma_200w:
            return None

        current_sma = sma_200w[-1]
        current_price = prices[-1]
        ath = max(prices)

        sma_crossed_ath = current_sma >= ath * 0.95  # Within 5% of ATH

        return {
            "sma_200w": round(current_sma, 2),
            "current_price": round(current_price, 2),
            "ath": round(ath, 2),
            "distance_from_200w": f"{((current_price / current_sma) - 1) * 100:.1f}%",
            "sma_near_ath": sma_crossed_ath,
            "signal": "CYCLE TOP WARNING - 200W SMA approaching prior ATH" if sma_crossed_ath else "Normal - 200W SMA below prior ATH",
        }

    # ========================
    # FORECASTS
    # ========================

    def get_forecasts(self, asset):
        """
        Generate 30/60/180 day forecasts using Cowen's framework.
        Combines cycle position, risk metric, regression bands, macro, and momentum.
        """
        if asset == "bitcoin":
            return self._bitcoin_forecast()
        elif asset == "ethereum":
            return self._ethereum_forecast()
        elif asset == "gold":
            return self._gold_forecast()
        elif asset == "silver":
            return self._silver_forecast()
        elif asset == "uranium":
            return self._uranium_forecast()
        elif asset == "dogecoin":
            return self._dogecoin_forecast()
        elif asset == "btc_dominance":
            return self._dominance_forecast()
        return {"error": "Unknown asset"}

    def _bitcoin_forecast(self):
        """
        Bitcoin forecast using full Cowen methodology.
        Integrates his specific 2026 thesis:
        - Bear market state of mind since Q4 2025
        - October 2026 base case bottom (4-year cycle)
        - May 2026 alternative if capitulation accelerates
        - March rallies form lower highs, then April-May weakness
        - Midterm year pattern: underperformance is normal
        """
        risk = self.get_risk_metric()
        cycle = self._get_cycle_position()
        btc_data = self.market_api.get_bitcoin_data()
        current_price = btc_data.get("current_price", 0)

        # Get price history for band analysis
        price_history = btc_data.get("price_history", [])
        bull_band = self.get_bull_market_support_band(price_history) if price_history else None
        sma_200w = self.get_200w_sma_analysis(price_history) if price_history else None

        # Regression bands for future dates
        days_now = (datetime.now() - BTC_GENESIS).days
        fair_30d = self._log_regression_price(days_now + 30)
        fair_60d = self._log_regression_price(days_now + 60)
        fair_180d = self._log_regression_price(days_now + 180)

        # Score components (each -1 to +1)
        scores = {}

        # 1. Risk metric component
        risk_score = risk["risk_score"]
        if risk_score < 0.3:
            scores["risk_metric"] = 0.8
        elif risk_score < 0.5:
            scores["risk_metric"] = 0.3
        elif risk_score < 0.7:
            scores["risk_metric"] = -0.2
        else:
            scores["risk_metric"] = -0.7

        # 2. Cycle position component (Cowen's midterm year thesis)
        progress = cycle["cycle_progress"]
        now = datetime.now()
        month = now.month

        if progress < 0.25:
            scores["cycle"] = 0.7
        elif progress < 0.5:
            # Midterm year - Cowen is specifically bearish here
            # Apply his seasonal pattern: March lower high -> April-June weakness
            if month in [3]:
                scores["cycle"] = -0.2  # March rally = lower high
            elif month in [4, 5, 6]:
                scores["cycle"] = -0.6  # April-June weakness expected
            elif month in [7, 8, 9]:
                scores["cycle"] = -0.5  # Continued weakness toward Oct bottom
            elif month in [10]:
                scores["cycle"] = -0.1  # Potential bottom month (base case)
            elif month in [11, 12]:
                scores["cycle"] = 0.2   # Post-bottom recovery if Oct thesis plays
            else:
                scores["cycle"] = -0.3  # Default midterm caution
        elif progress < 0.75:
            scores["cycle"] = 0.2
        else:
            scores["cycle"] = 0.4

        # 3. Bull market support band
        if bull_band:
            if bull_band["above_sma"] and bull_band["above_ema"]:
                scores["bull_band"] = 0.6
            elif not bull_band["above_sma"] and not bull_band["above_ema"]:
                scores["bull_band"] = -0.6
            else:
                scores["bull_band"] = 0.0

        # 4. Distance from fair value
        if current_price > 0 and fair_30d > 0:
            dist = (current_price / fair_30d) - 1
            scores["fair_value"] = max(-1, min(1, -dist))

        # 5. Cowen's bear market thesis overlay
        # He explicitly stated bear market state of mind since Q4 2025
        thesis = self.cowen_thesis
        if thesis.get("overall", "").lower().find("bear") >= 0:
            scores["cowen_thesis"] = -0.4
        elif thesis.get("overall", "").lower().find("bull") >= 0:
            scores["cowen_thesis"] = 0.4
        else:
            scores["cowen_thesis"] = 0.0

        # Composite score (-1 to +1)
        if scores:
            composite = sum(scores.values()) / len(scores)
        else:
            composite = 0

        # Generate price range estimates using Cowen's specific levels
        offsets = self.knowledge_base["frameworks"]["regression_bands"]["band_offsets"]
        def estimate_range(days_ahead, fair_val):
            future_days = days_now + days_ahead
            band_low = self._log_regression_price(future_days, offsets["low"])
            band_high = self._log_regression_price(future_days, offsets["high"])
            band_bottom = self._log_regression_price(future_days, offsets["bottom"])
            band_top = self._log_regression_price(future_days, offsets["top"])

            base_volatility = 0.15 * (days_ahead / 30) ** 0.5
            # Apply bearish skew for midterm year weakness
            bear_skew = 0.0
            target_date = now + timedelta(days=days_ahead)
            if 0.25 <= progress < 0.5:  # Midterm year
                if target_date.month in [4, 5, 6, 7, 8, 9]:
                    bear_skew = -0.05 * (days_ahead / 30)
                if target_date.month == 10 and days_ahead > 120:
                    bear_skew *= 0.5

            bull_mult = 1 + base_volatility * (1 + composite)
            bear_mult = 1 - base_volatility * (1.2 - composite)
            center = current_price * (1 + (composite * 0.02 + bear_skew) * days_ahead / 30)

            low_est = max(band_bottom, current_price * bear_mult)
            high_est = min(band_top, current_price * bull_mult)

            return {
                "low_estimate": round(low_est, 2),
                "mid_estimate": round(center, 2),
                "high_estimate": round(high_est, 2),
                "fair_value_at_date": round(fair_val, 2),
                "regression_band_low": round(band_low, 2),
                "regression_band_high": round(band_high, 2),
            }

        # Determine bias with Cowen's thesis weight
        if composite > 0.3:
            bias = "BULLISH - Frameworks favor upside"
        elif composite > 0.0:
            bias = "SLIGHTLY BULLISH - Mild upside bias"
        elif composite > -0.15:
            bias = "CAUTIOUS - Bear market state of mind per Cowen"
        elif composite > -0.3:
            bias = "BEARISH - Midterm year weakness expected"
        else:
            bias = "BEARISH - Multiple frameworks align bearish"

        # Build context from Cowen's specific thesis
        thesis_context = self._get_relevant_insights("bitcoin")
        if thesis:
            if thesis.get("btc_near_term"):
                thesis_context.insert(0, f"Near-term: {thesis['btc_near_term']}")
            if thesis.get("btc_bottom_base_case"):
                thesis_context.insert(0, f"Base case bottom: {thesis['btc_bottom_base_case']}")
            if thesis.get("btc_cycle_view"):
                thesis_context.insert(0, f"Cycle view: {thesis['btc_cycle_view']}")

        return {
            "asset": "Bitcoin",
            "current_price": current_price,
            "bias": bias,
            "composite_score": round(composite, 3),
            "score_components": scores,
            "forecasts": {
                "30_day": estimate_range(30, fair_30d),
                "60_day": estimate_range(60, fair_60d),
                "180_day": estimate_range(180, fair_180d),
            },
            "risk_metric": risk,
            "cycle_position": cycle,
            "bull_market_support_band": bull_band,
            "key_levels": {
                "bull_band_support": bull_band["sma_20w"] if bull_band else None,
                "200w_sma": sma_200w["sma_200w"] if sma_200w else None,
                "fair_value": risk["fair_value"],
            },
            "cowen_context": thesis_context[:8],
        }

    def _ethereum_forecast(self):
        """
        Ethereum forecast - Cowen's 2026 view:
        ETH will spend more time in regression band in 2026.
        ETH/BTC ratio continues bleeding. Midterm year = pain for alts.
        """
        eth_data = self.market_api.get_ethereum_data()
        btc_data = self.market_api.get_bitcoin_data()
        dom = self.market_api.get_btc_dominance()

        current_eth = eth_data.get("current_price", 0)
        current_btc = btc_data.get("current_price", 0)
        eth_btc = current_eth / current_btc if current_btc > 0 else 0

        cycle = self._get_cycle_position()
        progress = cycle["cycle_progress"]

        thesis = self.cowen_thesis
        eth_view = thesis.get("eth_view", "")

        # Cowen's specific ETH thesis for 2026
        if progress < 0.25:
            eth_bias = "NEUTRAL - Post-halving, BTC leads initially"
        elif progress < 0.5:
            eth_bias = "BEARISH vs BTC - ETH/BTC ratio continues bleeding in midterm year"
        elif progress < 0.75:
            eth_bias = "ACCUMULATE - Pre-halving year, ETH starts recovering vs BTC"
        else:
            eth_bias = "BULLISH - Late cycle typically favors ETH over BTC"

        # Generate actual numeric forecasts for ETH
        if current_eth > 0:
            # ETH has higher beta than BTC (~1.3-1.5x)
            beta = 1.4
            btc_composite = self._bitcoin_forecast().get("composite_score", 0)
            eth_composite = btc_composite * beta  # ETH amplifies BTC moves

            def eth_estimate(days):
                vol = 0.20 * (days / 30) ** 0.5  # Higher vol than BTC
                center = current_eth * (1 + eth_composite * 0.025 * days / 30)
                return {
                    "low_estimate": round(current_eth * (1 - vol * (1.3 - eth_composite)), 2),
                    "mid_estimate": round(center, 2),
                    "high_estimate": round(current_eth * (1 + vol * (1 + eth_composite)), 2),
                }

            forecasts = {
                "30_day": eth_estimate(30),
                "60_day": eth_estimate(60),
                "180_day": eth_estimate(180),
            }
        else:
            forecasts = {
                "30_day": {"note": "No price data"},
                "60_day": {"note": "No price data"},
                "180_day": {"note": "No price data"},
            }

        context = self._get_relevant_insights("ethereum")
        if eth_view:
            context.insert(0, eth_view)

        return {
            "asset": "Ethereum",
            "current_price": current_eth,
            "eth_btc_ratio": round(eth_btc, 6),
            "bias_vs_btc": eth_bias,
            "bias": eth_bias,
            "cycle_position": cycle,
            "forecasts": forecasts,
            "cowen_context": context[:5],
        }

    def _gold_forecast(self):
        """
        Gold forecast - Cowen's 2026 view:
        Sizable correction expected for metals in 2026.
        Bull market support band needs to catch up.
        Secular bull market intact but near-term pullback likely.
        """
        gold = self.market_api.get_gold_data()
        macro = self.market_api.get_macro_data()
        cycle = self._get_cycle_position()

        gold_price = gold.get("current_price", 0)
        dxy = macro.get("DXY", {}).get("current", 0)

        thesis = self.cowen_thesis
        gold_view = thesis.get("gold_view", "")

        # Cowen says correction expected in 2026
        progress = cycle["cycle_progress"]
        if gold_view and "correction" in gold_view.lower():
            gold_bias = "CAUTIOUS - Correction expected in 2026 per Cowen"
        elif 0.25 < progress < 0.5:
            gold_bias = "MIXED - Midterm year strong for gold vs crypto, but correction risk"
        else:
            gold_bias = "NEUTRAL - Monitor DXY and real rates"

        # Generate numeric forecasts
        if gold_price > 0:
            def gold_estimate(days):
                vol = 0.08 * (days / 30) ** 0.5  # Gold lower vol than crypto
                # Bearish skew for 2026 correction thesis
                correction_bias = -0.02 if "correction" in gold_view.lower() else 0
                center = gold_price * (1 + correction_bias * days / 30)
                return {
                    "low_estimate": round(gold_price * (1 - vol * 1.2), 2),
                    "mid_estimate": round(center, 2),
                    "high_estimate": round(gold_price * (1 + vol * 0.8), 2),
                }
            forecasts = {
                "30_day": gold_estimate(30),
                "60_day": gold_estimate(60),
                "180_day": gold_estimate(180),
            }
        else:
            forecasts = {
                "30_day": {"note": "No price data"},
                "60_day": {"note": "No price data"},
                "180_day": {"note": "No price data"},
            }

        context = self._get_relevant_insights("gold")
        if gold_view:
            context.insert(0, gold_view)

        return {
            "asset": "Gold",
            "current_price": gold_price,
            "bias": gold_bias,
            "dxy": dxy,
            "dxy_impact": "Strong dollar headwind" if dxy > 105 else "Weak dollar tailwind" if dxy < 95 else "Neutral dollar",
            "forecasts": forecasts,
            "cowen_context": context[:5],
        }

    def _silver_forecast(self):
        """Silver forecast - gold/silver ratio focus. Correction expected 2026."""
        silver = self.market_api.get_silver_data()
        gold = self.market_api.get_gold_data()

        silver_price = silver.get("current_price", 0)
        gold_price = gold.get("current_price", 0)
        ratio = gold_price / silver_price if silver_price > 0 else 0

        # Cowen's silver framework: gold/silver ratio
        if ratio > 80:
            bias = "BULLISH - Gold/Silver ratio elevated, silver undervalued historically"
        elif ratio > 70:
            bias = "SLIGHTLY BULLISH - Ratio above average"
        elif ratio > 60:
            bias = "NEUTRAL - Correction risk for metals in 2026"
        else:
            bias = "BEARISH - Ratio low, silver may be overextended"

        # Generate numeric forecasts
        if silver_price > 0:
            def silver_estimate(days):
                vol = 0.12 * (days / 30) ** 0.5  # Silver higher vol than gold
                correction_bias = -0.015  # Metals correction thesis
                center = silver_price * (1 + correction_bias * days / 30)
                return {
                    "low_estimate": round(silver_price * (1 - vol * 1.3), 2),
                    "mid_estimate": round(center, 2),
                    "high_estimate": round(silver_price * (1 + vol * 0.9), 2),
                }
            forecasts = {
                "30_day": silver_estimate(30),
                "60_day": silver_estimate(60),
                "180_day": silver_estimate(180),
            }
        else:
            forecasts = {
                "30_day": {"note": "No price data"},
                "60_day": {"note": "No price data"},
                "180_day": {"note": "No price data"},
            }

        return {
            "asset": "Silver",
            "current_price": silver_price,
            "gold_silver_ratio": round(ratio, 2),
            "bias": bias,
            "forecasts": forecasts,
            "cowen_context": self._get_relevant_insights("silver"),
        }

    def _uranium_forecast(self):
        """Uranium forecast - long-term supply/demand focus."""
        uranium = self.market_api.get_uranium_data()
        current_price = uranium.get("current_price", 0)

        # Generate numeric forecasts
        if current_price > 0:
            def ura_estimate(days):
                vol = 0.15 * (days / 30) ** 0.5
                center = current_price * (1 + 0.01 * days / 30)  # Mild long-term bullish
                return {
                    "low_estimate": round(current_price * (1 - vol * 1.1), 2),
                    "mid_estimate": round(center, 2),
                    "high_estimate": round(current_price * (1 + vol * 1.2), 2),
                }
            forecasts = {
                "30_day": ura_estimate(30),
                "60_day": ura_estimate(60),
                "180_day": ura_estimate(180),
            }
        else:
            forecasts = {
                "30_day": {"note": "No price data"},
                "60_day": {"note": "No price data"},
                "180_day": {"note": "No price data"},
            }

        return {
            "asset": "Uranium (URA ETF)",
            "current_price": current_price,
            "change_pct": uranium.get("change_pct", 0),
            "bias": "LONG-TERM BULLISH - Supply deficit thesis, expect volatility",
            "forecasts": forecasts,
            "cowen_context": self._get_relevant_insights("uranium"),
        }

    def _dogecoin_forecast(self):
        """Dogecoin forecast - meme coin, high volatility, follows BTC with amplification."""
        doge = self.market_api.get_dogecoin_data()
        current_price = doge.get("current_price", 0)

        if current_price > 0:
            def doge_estimate(days):
                # DOGE is highly volatile - wider bands than BTC
                vol = 0.30 * (days / 30) ** 0.5
                # Slight mean-reversion tendency
                center = current_price * (1 + 0.005 * days / 30)
                return {
                    "low_estimate": round(current_price * (1 - vol * 1.2), 4),
                    "mid_estimate": round(center, 4),
                    "high_estimate": round(current_price * (1 + vol * 1.3), 4),
                }
            forecasts = {
                "30_day": doge_estimate(30),
                "60_day": doge_estimate(60),
                "180_day": doge_estimate(180),
            }
        else:
            forecasts = {
                "30_day": {"note": "No price data"},
                "60_day": {"note": "No price data"},
                "180_day": {"note": "No price data"},
            }

        # DOGE tracks BTC sentiment but amplified
        bias = "SPECULATIVE - Follows BTC direction with higher volatility, meme-driven momentum"

        return {
            "asset": "Dogecoin (DOGE)",
            "current_price": current_price,
            "change_24h": doge.get("change_24h", 0),
            "market_cap": doge.get("market_cap", 0),
            "bias": bias,
            "forecasts": forecasts,
            "cowen_context": ["Meme coins amplify BTC moves — higher upside in bulls, deeper drawdowns in bears"],
        }

    def _dominance_forecast(self):
        """Bitcoin Dominance forecast."""
        dom = self.market_api.get_btc_dominance()
        cycle = self._get_cycle_position()
        progress = cycle["cycle_progress"]

        btc_dom = dom.get("btc_dominance", 0)

        # Cowen's dominance framework
        # Dominance rises in bear markets, falls late in bull markets
        # Lengthening dominance cycles
        if btc_dom > 60:
            dom_bias = "HIGH - Indicates bear market conditions or early cycle BTC accumulation"
        elif btc_dom > 50:
            dom_bias = "ELEVATED - BTC leading, alt season not yet started"
        elif btc_dom > 40:
            dom_bias = "MODERATE - Transition zone, watch for breakdown"
        else:
            dom_bias = "LOW - Alt season conditions, rotation into alts"

        # Cycle-based expectation
        if progress < 0.5:
            cycle_expect = "Dominance typically rises or stays elevated early-to-mid cycle"
        else:
            cycle_expect = "Dominance typically falls in later stages of bull markets"

        return {
            "asset": "Bitcoin Dominance",
            "current_dominance": round(btc_dom, 2),
            "eth_dominance": round(dom.get("eth_dominance", 0), 2),
            "bias": dom_bias,
            "cycle_expectation": cycle_expect,
            "forecasts": {
                "30_day": {"note": "Short-term follows risk sentiment and macro"},
                "60_day": {"note": "Watch for alt breakdowns vs BTC"},
                "180_day": {"note": cycle_expect},
            },
            "alt_season_indicator": "NOT YET" if btc_dom > 45 else "APPROACHING" if btc_dom > 38 else "ACTIVE",
            "cowen_context": self._get_relevant_insights("dominance"),
        }

    # ========================
    # FULL ANALYSIS
    # ========================

    def analyze(self, asset):
        """Complete Cowen-style analysis for an asset."""
        forecast = self.get_forecasts(asset)

        if asset == "bitcoin":
            risk = self.get_risk_metric()
            cycle = self.get_cycle_analysis()
            btc_data = self.market_api.get_bitcoin_data()
            price_history = btc_data.get("price_history", [])

            return {
                "forecast": forecast,
                "risk_metric": risk,
                "cycle_analysis": cycle,
                "regression_bands": self.get_regression_bands(asset),
                "bull_market_support_band": self.get_bull_market_support_band(price_history),
                "sma_200w": self.get_200w_sma_analysis(price_history),
            }
        else:
            return {"forecast": forecast}

    def get_regression_bands(self, asset):
        """Get logarithmic regression band levels."""
        if asset != "bitcoin":
            return {"note": "Regression bands only available for Bitcoin"}

        days_now = (datetime.now() - BTC_GENESIS).days
        bands = self._get_band_prices(days_now)
        btc_data = self.market_api.get_bitcoin_data()
        current_price = btc_data.get("current_price", 0)

        # Determine which band we're in
        current_band = "unknown"
        band_levels = sorted(bands.items(), key=lambda x: x[1])
        for i, (name, price) in enumerate(band_levels):
            if current_price <= price:
                if i > 0:
                    current_band = f"Between {band_levels[i-1][0]} and {name}"
                else:
                    current_band = f"Below {name}"
                break
        else:
            current_band = f"Above {band_levels[-1][0]}"

        return {
            "current_price": current_price,
            "bands": bands,
            "current_band": current_band,
            "days_since_genesis": days_now,
        }

    def get_latest_insights(self):
        """Get latest insights extracted from video transcripts."""
        insights_path = "data/latest_insights.json"
        if os.path.exists(insights_path):
            with open(insights_path, "r") as f:
                return json.load(f)

        return {
            "latest_video": "Transcripts being processed...",
            "key_themes": list(self.knowledge_base["key_principles"]),
            "frameworks": list(self.knowledge_base["frameworks"].keys()),
        }

    def _get_relevant_insights(self, topic):
        """Get topic-relevant insights from knowledge base."""
        insights = []
        kb = self.knowledge_base

        # Map topics to framework keys
        topic_map = {
            "bitcoin": ["risk_metric", "cycle_timing", "regression_bands", "bull_market_support_band", "200w_sma"],
            "ethereum": ["ethereum_framework", "btc_dominance"],
            "gold": ["gold_framework", "macro_framework"],
            "silver": ["silver_framework", "macro_framework"],
            "uranium": ["uranium_framework"],
            "dominance": ["btc_dominance"],
        }

        for key in topic_map.get(topic, []):
            if key in kb["frameworks"]:
                fw = kb["frameworks"][key]
                if isinstance(fw, dict):
                    desc = fw.get("description", "")
                    if desc:
                        insights.append(desc)

        return insights[:5]  # Top 5 relevant insights

    # ========================
    # HELPER FUNCTIONS
    # ========================

    # ========================
    # REGRESSION BANDS TIMESERIES
    # ========================

    def get_regression_bands_timeseries(self, price_history):
        """
        Generate regression band values over time for charting overlay.
        Returns arrays aligned with price_history timestamps.
        """
        if not price_history:
            return {}

        offsets = self.knowledge_base["frameworks"]["regression_bands"]["band_offsets"]
        result = {band: [] for band in offsets}

        for point in price_history:
            ts = point["timestamp"]
            dt = datetime.fromtimestamp(ts / 1000)
            days = (dt - BTC_GENESIS).days
            if days <= 0:
                for band in result:
                    result[band].append({"timestamp": ts, "price": 0})
                continue

            for band, off in offsets.items():
                result[band].append({
                    "timestamp": ts,
                    "price": round(self._log_regression_price(days, off), 2)
                })

        return result

    # ========================
    # COMPOSITE MARKET SCORE
    # ========================

    def get_composite_score(self):
        """
        Master composite score combining all Cowen frameworks.
        Returns a -100 to +100 score with detailed breakdown.
        """
        components = {}
        weights = {
            "risk_metric": 20,
            "cycle_position": 20,
            "bull_band": 15,
            "macro": 10,
            "dominance": 10,
            "momentum": 10,
            "cowen_thesis": 15,
        }

        # 1. Risk Metric (-1 to +1)
        risk = self.get_risk_metric()
        risk_score = risk.get("risk_score", 0.5)
        # Invert: low risk = bullish, high risk = bearish
        components["risk_metric"] = (0.5 - risk_score) * 2

        # 2. Cycle position
        cycle = self._get_cycle_position()
        progress = cycle.get("cycle_progress", 0.5)
        # Post-halving Year 1 most bullish, midterm most bearish
        if progress < 0.25:
            components["cycle_position"] = 0.7
        elif progress < 0.5:
            components["cycle_position"] = -0.4
        elif progress < 0.75:
            components["cycle_position"] = 0.2
        else:
            components["cycle_position"] = 0.3

        # 3. Bull Market Support Band
        btc_data = self.market_api.get_bitcoin_data()
        price_history = btc_data.get("price_history", [])
        bull_band = self.get_bull_market_support_band(price_history) if price_history else None
        if bull_band:
            if bull_band["above_sma"] and bull_band["above_ema"]:
                components["bull_band"] = 0.6
            elif not bull_band["above_sma"] and not bull_band["above_ema"]:
                components["bull_band"] = -0.6
            else:
                components["bull_band"] = 0.0
        else:
            components["bull_band"] = 0.0

        # 4. Macro (simplified)
        macro = self.market_api.get_macro_data()
        dxy = macro.get("DXY", {}).get("current", 100)
        if dxy > 108:
            components["macro"] = -0.5  # Strong dollar = bearish for BTC
        elif dxy > 103:
            components["macro"] = -0.2
        elif dxy < 95:
            components["macro"] = 0.5   # Weak dollar = bullish
        else:
            components["macro"] = 0.1

        # 5. Dominance
        dom = self.market_api.get_btc_dominance()
        btc_dom = dom.get("btc_dominance", 50)
        if btc_dom > 60:
            components["dominance"] = -0.3  # Very high dom = bear market vibes
        elif btc_dom > 50:
            components["dominance"] = 0.1   # Moderately high = BTC strong
        elif btc_dom > 40:
            components["dominance"] = 0.3   # Normal range
        else:
            components["dominance"] = 0.5   # Low dom = alt season = late bull

        # 6. Price momentum
        if price_history and len(price_history) > 30:
            current = price_history[-1]["price"]
            thirty_ago = price_history[-30]["price"]
            momentum = (current / thirty_ago - 1)
            components["momentum"] = max(-1, min(1, momentum * 5))
        else:
            components["momentum"] = 0.0

        # 7. Cowen's explicit thesis overlay
        thesis = self.cowen_thesis
        thesis_text = thesis.get("overall", "").lower()
        if "bear" in thesis_text:
            components["cowen_thesis"] = -0.5
        elif "bull" in thesis_text:
            components["cowen_thesis"] = 0.5
        else:
            components["cowen_thesis"] = 0.0

        # Weighted composite
        total_weight = sum(weights.values())
        composite = sum(
            components.get(k, 0) * weights.get(k, 0)
            for k in weights
        ) / total_weight * 100

        # Interpretation
        if composite > 50:
            interpretation = "STRONGLY BULLISH - Multiple Cowen frameworks align bullish"
        elif composite > 20:
            interpretation = "BULLISH - Majority of indicators favor upside"
        elif composite > 0:
            interpretation = "SLIGHTLY BULLISH - Mild positive bias"
        elif composite > -20:
            interpretation = "SLIGHTLY BEARISH - Mild negative bias"
        elif composite > -50:
            interpretation = "BEARISH - Majority of indicators favor downside"
        else:
            interpretation = "STRONGLY BEARISH - Multiple frameworks align bearish"

        return {
            "composite_score": round(composite, 1),
            "interpretation": interpretation,
            "components": {
                k: {
                    "score": round(v * 100, 1),
                    "weight": weights.get(k, 0),
                }
                for k, v in components.items()
            },
            "risk_metric": risk,
            "cycle_position": cycle,
        }

    def get_ben_signal(self):
        """
        'What Would Ben Do?' — Buy/Sell/Hold signal for Bitcoin.
        Combines ALL of Cowen's frameworks from 151 transcripts into
        a single actionable signal with detailed reasoning.

        Frameworks used:
        1. Risk Metric (log regression distance)
        2. 4-Year Cycle Position (halving-based)
        3. Bull Market Support Band (20W SMA + 21W EMA)
        4. Macro Overlay (DXY, rates, economy)
        5. Cowen's Explicit Thesis (from transcript analysis)
        6. BTC Dominance
        7. Price vs Fair Value
        8. Momentum
        """
        signals = []  # list of (signal_name, score, reasoning)
        # score: -2 (strong sell) to +2 (strong buy)

        # 1. Risk Metric
        risk = self.get_risk_metric()
        risk_score = risk.get("risk_score", 0.5)
        fair_value = risk.get("fair_value", 0)
        current_price = risk.get("current_price", 0)
        zone = risk.get("zone", "")

        if risk_score <= 0.15:
            signals.append(("Risk Metric", 2, f"Risk at {risk_score:.3f} — extreme accumulation zone. Historically the best buying opportunity."))
        elif risk_score <= 0.3:
            signals.append(("Risk Metric", 1.5, f"Risk at {risk_score:.3f} — accumulation zone. Ben says 'DCA into fear, not euphoria.'"))
        elif risk_score <= 0.45:
            signals.append(("Risk Metric", 0.8, f"Risk at {risk_score:.3f} — early bull territory. Price below fair value — continue accumulating."))
        elif risk_score <= 0.55:
            signals.append(("Risk Metric", 0, f"Risk at {risk_score:.3f} — near fair value. Neutral — hold position."))
        elif risk_score <= 0.7:
            signals.append(("Risk Metric", -0.8, f"Risk at {risk_score:.3f} — elevated. Consider taking some profits off the table."))
        elif risk_score <= 0.85:
            signals.append(("Risk Metric", -1.5, f"Risk at {risk_score:.3f} — high risk. Ben would be reducing exposure significantly."))
        else:
            signals.append(("Risk Metric", -2, f"Risk at {risk_score:.3f} — extreme risk. Potential blow-off top. Maximum profit-taking."))

        # 2. Price vs Fair Value
        if current_price > 0 and fair_value > 0:
            pct_from_fair = ((current_price / fair_value) - 1) * 100
            if pct_from_fair < -40:
                signals.append(("Fair Value", 2, f"Price is {pct_from_fair:.0f}% below fair value (${fair_value:,.0f}). Deep discount — generational buy zone."))
            elif pct_from_fair < -20:
                signals.append(("Fair Value", 1.2, f"Price is {pct_from_fair:.0f}% below fair value. Undervalued — accumulate."))
            elif pct_from_fair < 0:
                signals.append(("Fair Value", 0.5, f"Price is {pct_from_fair:.0f}% below fair value. Slightly cheap — lean buy."))
            elif pct_from_fair < 30:
                signals.append(("Fair Value", -0.3, f"Price is +{pct_from_fair:.0f}% above fair value. Near fair — hold."))
            else:
                signals.append(("Fair Value", -1.5, f"Price is +{pct_from_fair:.0f}% above fair value. Overextended — take profits."))

        # 3. 4-Year Cycle
        cycle = self._get_cycle_position()
        progress = cycle.get("cycle_progress", 0.5)
        cycle_year = cycle.get("cycle_year", "")
        days_since = cycle.get("days_since_halving", 0)

        if "Year 1" in cycle_year:
            signals.append(("Halving Cycle", 1.0, f"Year 1 post-halving ({days_since} days). Historically bullish — BTC tends to rally."))
        elif "Year 2" in cycle_year:
            signals.append(("Halving Cycle", -1.0, f"Midterm year ({days_since} days post-halving). Ben's data shows midterm years are the weakest. Expect chop and lower highs."))
        elif "Year 3" in cycle_year:
            signals.append(("Halving Cycle", 1.5, f"Year 3 — historically the strongest year in the cycle. Be positioned."))
        else:
            signals.append(("Halving Cycle", 0.3, f"Pre-halving year. Accumulation typically builds here."))

        # 4. Bull Market Support Band
        btc_data = self.market_api.get_bitcoin_data()
        price_history = btc_data.get("price_history", [])
        bull_band = self.get_bull_market_support_band(price_history) if price_history else None
        if bull_band:
            if bull_band["above_sma"] and bull_band["above_ema"]:
                signals.append(("Bull Band", 1.0, f"Price above both 20W SMA (${bull_band['sma_20w']:,.0f}) and 21W EMA. Bull trend confirmed."))
            elif not bull_band["above_sma"] and not bull_band["above_ema"]:
                signals.append(("Bull Band", -1.0, f"Price BELOW both 20W SMA (${bull_band['sma_20w']:,.0f}) and 21W EMA. Bear trend — Ben says this is not the time to be aggressive."))
            else:
                signals.append(("Bull Band", 0, f"Price between 20W SMA and 21W EMA. Indecisive — wait for confirmation."))

        # 5. Macro
        try:
            econ = self.market_api.get_macro_economy()
            macro_score = econ.get("assessment", {}).get("score", 0)
            outlook = econ.get("assessment", {}).get("outlook", "")
            if macro_score > 30:
                signals.append(("Macro Economy", 0.5, f"Economy score +{macro_score} ({outlook}). Supportive environment for risk assets."))
            elif macro_score > 0:
                signals.append(("Macro Economy", 0.2, f"Economy score +{macro_score} ({outlook}). Mildly supportive."))
            elif macro_score > -30:
                signals.append(("Macro Economy", -0.3, f"Economy score {macro_score} ({outlook}). Headwinds present — be cautious."))
            else:
                signals.append(("Macro Economy", -1.0, f"Economy score {macro_score} ({outlook}). Significant headwinds. Ben says macro matters."))
        except Exception:
            pass

        # 6. Cowen's Thesis (from 151 transcripts)
        thesis = self.cowen_thesis
        if thesis:
            overall = thesis.get("overall", "")
            near_term = thesis.get("btc_near_term", "")
            bottom_case = thesis.get("btc_bottom_base_case", "")

            if "bear" in overall.lower():
                signals.append(("Cowen's Thesis", -1.2, f"Ben's thesis: '{overall[:80]}' Base case bottom: {bottom_case}."))
            elif "bull" in overall.lower():
                signals.append(("Cowen's Thesis", 1.2, f"Ben's thesis: '{overall[:80]}'"))
            else:
                signals.append(("Cowen's Thesis", 0, f"Ben's thesis: '{overall[:80]}'"))

            if near_term:
                if "lower high" in near_term.lower() or "weakness" in near_term.lower():
                    signals.append(("Near-Term View", -0.8, f"Ben's near-term: '{near_term}'"))
                elif "rally" in near_term.lower() or "strength" in near_term.lower():
                    signals.append(("Near-Term View", 0.5, f"Ben's near-term: '{near_term}'"))

        # 7. BTC Dominance
        dom = self.market_api.get_btc_dominance()
        btc_dom = dom.get("btc_dominance", 0)
        if btc_dom > 60:
            signals.append(("BTC Dominance", -0.3, f"Dominance at {btc_dom}% — very high. Capital hiding in BTC, alt season far away. Bear market behavior."))
        elif btc_dom > 50:
            signals.append(("BTC Dominance", 0.3, f"Dominance at {btc_dom}% — BTC leading. Healthy for BTC but alts struggling."))
        elif btc_dom > 40:
            signals.append(("BTC Dominance", 0.5, f"Dominance at {btc_dom}% — balanced market. Both BTC and alts can work."))
        else:
            signals.append(("BTC Dominance", 0.2, f"Dominance at {btc_dom}% — low. Alt season territory — be selective."))

        # Calculate overall signal
        total_score = sum(s[1] for s in signals)
        max_possible = len(signals) * 2
        normalized = total_score / max_possible * 100 if max_possible > 0 else 0

        # Determine action
        if normalized > 40:
            action = "STRONG BUY"
            action_detail = "Multiple Cowen frameworks align bullish. Aggressive accumulation zone."
            color = "buy"
        elif normalized > 15:
            action = "BUY / DCA"
            action_detail = "Majority of indicators favor accumulation. Dollar-cost average in."
            color = "buy"
        elif normalized > 5:
            action = "LEAN BUY"
            action_detail = "Slight bullish edge. Small positions or continued DCA."
            color = "buy"
        elif normalized > -5:
            action = "HOLD"
            action_detail = "Mixed signals. Ben would say 'patience is a virtue.' Hold current positions."
            color = "hold"
        elif normalized > -15:
            action = "LEAN SELL"
            action_detail = "Slight bearish edge. Consider trimming positions or tightening stops."
            color = "sell"
        elif normalized > -40:
            action = "REDUCE"
            action_detail = "Majority of indicators bearish. Take profits and reduce exposure."
            color = "sell"
        else:
            action = "STRONG SELL"
            action_detail = "Multiple frameworks align bearish. Maximize cash, minimize exposure."
            color = "sell"

        # Build reasoning list (top signals sorted by absolute strength)
        sorted_signals = sorted(signals, key=lambda x: abs(x[1]), reverse=True)
        reasoning = [{"name": s[0], "score": round(s[1], 1), "detail": s[2]} for s in sorted_signals]

        return {
            "action": action,
            "action_detail": action_detail,
            "color": color,
            "score": round(normalized, 1),
            "raw_score": round(total_score, 2),
            "signal_count": len(signals),
            "bullish_signals": len([s for s in signals if s[1] > 0.3]),
            "bearish_signals": len([s for s in signals if s[1] < -0.3]),
            "neutral_signals": len([s for s in signals if -0.3 <= s[1] <= 0.3]),
            "reasoning": reasoning,
            "current_price": current_price,
            "fair_value": round(fair_value, 2),
            "risk_score": risk_score,
            "disclaimer": "Based on Benjamin Cowen's analytical frameworks. Not financial advice. Always do your own research.",
        }

    @staticmethod
    def _sma(data, period):
        """Simple Moving Average."""
        if len(data) < period:
            return []
        result = []
        for i in range(period - 1, len(data)):
            avg = sum(data[i - period + 1:i + 1]) / period
            result.append(avg)
        return result

    @staticmethod
    def _ema(data, period):
        """Exponential Moving Average."""
        if len(data) < period:
            return []
        multiplier = 2 / (period + 1)
        ema = [sum(data[:period]) / period]
        for price in data[period:]:
            ema.append((price - ema[-1]) * multiplier + ema[-1])
        return ema
