"""
Friday Price Predictor — "Just for Fun" weekly predictions.

Every week, generates specific price predictions for the coming Friday
for all tracked assets. After Friday passes, compares predictions to
actual prices and adjusts its confidence/weights based on accuracy.

Self-learning: tracks which indicators (regression, macro, momentum,
Cowen thesis) contribute to better predictions and adjusts weights.
"""

import json
import os
import math
from datetime import datetime, timedelta

DATA_DIR = "data"
PREDICTIONS_FILE = os.path.join(DATA_DIR, "friday_predictions.json")

# Assets we predict
ASSETS = ["bitcoin", "ethereum", "gold", "silver", "uranium", "sp500"]

# Initial indicator weights (sum to 1.0) — adjusted over time by learning
DEFAULT_WEIGHTS = {
    "regression": 0.25,    # log regression fair value trend
    "momentum": 0.25,      # recent price momentum
    "macro": 0.15,         # macro health score influence
    "cowen_thesis": 0.15,  # Cowen's directional bias
    "mean_reversion": 0.20, # pull toward recent moving average
}


class FridayPredictor:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.data = self._load()

    def _load(self):
        if os.path.exists(PREDICTIONS_FILE):
            try:
                with open(PREDICTIONS_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "predictions": [],
            "weights": dict(DEFAULT_WEIGHTS),
            "learning_stats": {
                "total_predictions": 0,
                "evaluated": 0,
                "correct_direction": 0,
                "avg_error_pct": 0,
                "best_streak": 0,
                "current_streak": 0,
            },
        }

    def _save(self):
        with open(PREDICTIONS_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    def _next_friday(self):
        """Get the date of the coming Friday (or today if it's Friday before market close)."""
        now = datetime.now()
        days_ahead = 4 - now.weekday()  # Friday = 4
        if days_ahead <= 0:
            days_ahead += 7
        return (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    def _last_friday(self):
        """Get the date of the most recent past Friday."""
        now = datetime.now()
        days_back = (now.weekday() - 4) % 7
        if days_back == 0 and now.hour < 16:
            days_back = 7  # If Friday before close, use last Friday
        return (now - timedelta(days=days_back)).strftime("%Y-%m-%d")

    def generate_predictions(self, market_api, cowen_engine):
        """Generate predictions for the coming Friday."""
        target_date = self._next_friday()

        # Check if we already have predictions for this Friday
        existing = [p for p in self.data["predictions"] if p["target_date"] == target_date]
        if existing:
            return existing[0]

        weights = self.data["weights"]
        predictions = {}

        for asset in ASSETS:
            try:
                pred = self._predict_asset(asset, weights, market_api, cowen_engine)
                predictions[asset] = pred
            except Exception as e:
                predictions[asset] = {"error": str(e)}

        entry = {
            "target_date": target_date,
            "generated_at": datetime.now().isoformat(),
            "predictions": predictions,
            "weights_used": dict(weights),
            "evaluated": False,
        }

        self.data["predictions"].append(entry)
        self.data["learning_stats"]["total_predictions"] += len([p for p in predictions.values() if "error" not in p])
        self._save()
        return entry

    def _predict_asset(self, asset, weights, market_api, cowen_engine):
        """Predict a single asset's Friday price using weighted indicators."""

        # Get current price
        if asset == "sp500":
            econ = market_api.get_macro_economy()
            sp = econ.get("sp500", {})
            current = sp.get("current", 0)
            history = sp.get("history", [])
            prices = [h["price"] for h in history] if history else []
        elif asset == "bitcoin":
            data = market_api.get_bitcoin_data()
            current = data.get("current_price", 0)
            history = data.get("price_history", [])
            prices = [h["price"] for h in history] if history else []
        elif asset == "ethereum":
            data = market_api.get_ethereum_data()
            current = data.get("current_price", 0)
            history = data.get("price_history", [])
            prices = [h["price"] for h in history] if history else []
        elif asset == "gold":
            data = market_api.get_gold_data()
            current = data.get("current_price", 0)
            history = data.get("price_history", [])
            prices = [h["price"] for h in history] if history else []
        elif asset == "silver":
            data = market_api.get_silver_data()
            current = data.get("current_price", 0)
            history = data.get("price_history", [])
            prices = [h["price"] for h in history] if history else []
        elif asset == "uranium":
            data = market_api.get_uranium_data()
            current = data.get("current_price", 0)
            history = data.get("price_history", [])
            prices = [h["price"] for h in history] if history else []
        else:
            return {"error": f"Unknown asset: {asset}"}

        if current <= 0:
            return {"error": "No price data"}

        # ── Indicator signals (each returns % change expectation) ──

        # 1. Regression / Fair value pull
        regression_signal = 0
        if asset == "bitcoin":
            try:
                risk = cowen_engine.get_risk_metric()
                fair = risk.get("fair_value", current)
                if fair > 0:
                    # Price tends to move toward fair value
                    gap_pct = (fair - current) / current
                    regression_signal = gap_pct * 0.05  # 5% of the gap per week
            except Exception:
                pass

        # 2. Momentum (7-day and 30-day)
        momentum_signal = 0
        if len(prices) >= 30:
            week_ago = prices[-7] if len(prices) >= 7 else prices[0]
            month_ago = prices[-30]
            weekly_mom = (current - week_ago) / week_ago if week_ago else 0
            monthly_mom = (current - month_ago) / month_ago if month_ago else 0
            # Blend: momentum continues but with dampening
            momentum_signal = weekly_mom * 0.4 + monthly_mom * 0.1

        # 3. Macro influence
        macro_signal = 0
        try:
            econ_data = market_api.get_macro_economy()
            assessment = econ_data.get("assessment", {})
            macro_score = assessment.get("score", 0)
            # Macro score (-100 to +100) → small weekly influence
            macro_signal = macro_score / 100 * 0.01  # ±1% max
        except Exception:
            pass

        # 4. Cowen thesis directional bias
        thesis_signal = 0
        try:
            thesis = cowen_engine.cowen_thesis
            if thesis:
                outlook = thesis.get("market_outlook", "").lower()
                if "bear" in outlook:
                    thesis_signal = -0.015  # -1.5% weekly drag
                elif "bull" in outlook:
                    thesis_signal = 0.015
                elif "cautious" in outlook or "neutral" in outlook:
                    thesis_signal = -0.005
        except Exception:
            pass

        # 5. Mean reversion (20-day SMA pull)
        mean_rev_signal = 0
        if len(prices) >= 20:
            sma_20 = sum(prices[-20:]) / 20
            deviation = (current - sma_20) / sma_20
            # Pull back toward SMA
            mean_rev_signal = -deviation * 0.15  # 15% reversion per week

        # ── Combine signals with learned weights ──
        signals = {
            "regression": regression_signal,
            "momentum": momentum_signal,
            "macro": macro_signal,
            "cowen_thesis": thesis_signal,
            "mean_reversion": mean_rev_signal,
        }

        weighted_change = sum(weights.get(k, 0) * v for k, v in signals.items())

        # Clamp to reasonable weekly range (-10% to +10%)
        weighted_change = max(-0.10, min(0.10, weighted_change))

        predicted_price = current * (1 + weighted_change)

        # Confidence based on signal agreement
        directions = [1 if v > 0 else -1 if v < 0 else 0 for v in signals.values()]
        agreement = abs(sum(directions)) / max(len(directions), 1)
        confidence = 0.3 + agreement * 0.5  # 30% base + up to 50% for full agreement

        return {
            "current_price": round(current, 2),
            "predicted_price": round(predicted_price, 2),
            "predicted_change_pct": round(weighted_change * 100, 2),
            "direction": "UP" if weighted_change > 0.002 else "DOWN" if weighted_change < -0.002 else "FLAT",
            "confidence": round(confidence * 100),
            "signals": {k: round(v * 100, 3) for k, v in signals.items()},
        }

    def evaluate_past_predictions(self, market_api):
        """Check past Fridays and score our predictions."""
        today = datetime.now().strftime("%Y-%m-%d")
        updated = False

        for entry in self.data["predictions"]:
            if entry["evaluated"]:
                continue
            if entry["target_date"] >= today:
                continue  # Not yet past

            # Get actual prices for that Friday
            actual_prices = self._get_actual_prices(entry["target_date"], market_api)
            if not actual_prices:
                continue

            results = {}
            for asset, pred in entry["predictions"].items():
                if "error" in pred:
                    continue

                actual = actual_prices.get(asset)
                if not actual or actual <= 0:
                    continue

                predicted = pred["predicted_price"]
                error_pct = abs(predicted - actual) / actual * 100
                direction_correct = (
                    (pred["direction"] == "UP" and actual > pred["current_price"]) or
                    (pred["direction"] == "DOWN" and actual < pred["current_price"]) or
                    (pred["direction"] == "FLAT" and abs(actual - pred["current_price"]) / pred["current_price"] < 0.01)
                )

                results[asset] = {
                    "predicted": predicted,
                    "actual": round(actual, 2),
                    "error_pct": round(error_pct, 2),
                    "direction_correct": direction_correct,
                }

                # Update learning stats
                stats = self.data["learning_stats"]
                stats["evaluated"] += 1
                if direction_correct:
                    stats["correct_direction"] += 1
                    stats["current_streak"] += 1
                    stats["best_streak"] = max(stats["best_streak"], stats["current_streak"])
                else:
                    stats["current_streak"] = 0

                # Running average error
                n = stats["evaluated"]
                stats["avg_error_pct"] = round(
                    ((stats["avg_error_pct"] * (n - 1)) + error_pct) / n, 2
                )

            entry["results"] = results
            entry["evaluated"] = True
            updated = True

            # ── Learn: adjust weights based on which signals were right ──
            self._adjust_weights(entry)

        if updated:
            self._save()

    def _get_actual_prices(self, date_str, market_api):
        """Get actual closing prices for a given date. Uses current prices as proxy for recent dates."""
        prices = {}
        try:
            btc = market_api.get_bitcoin_data()
            prices["bitcoin"] = btc.get("current_price", 0)

            eth = market_api.get_ethereum_data()
            prices["ethereum"] = eth.get("current_price", 0)

            gold = market_api.get_gold_data()
            prices["gold"] = gold.get("current_price", 0)

            silver = market_api.get_silver_data()
            prices["silver"] = silver.get("current_price", 0)

            ura = market_api.get_uranium_data()
            prices["uranium"] = ura.get("current_price", 0)

            econ = market_api.get_macro_economy()
            sp = econ.get("sp500", {})
            prices["sp500"] = sp.get("current", 0)
        except Exception:
            pass

        return prices

    def _adjust_weights(self, entry):
        """Learn from results: boost weights for signals that predicted direction correctly."""
        if not entry.get("results"):
            return

        weights = self.data["weights"]
        predictions = entry["predictions"]
        results = entry["results"]

        # For each evaluated asset, check which signals pointed the right way
        signal_scores = {k: 0 for k in DEFAULT_WEIGHTS}
        signal_counts = {k: 0 for k in DEFAULT_WEIGHTS}

        for asset, result in results.items():
            pred = predictions.get(asset, {})
            signals = pred.get("signals", {})
            actual_direction = 1 if result["actual"] > pred.get("current_price", 0) else -1

            for sig_name, sig_value in signals.items():
                if sig_value == 0:
                    continue
                sig_direction = 1 if sig_value > 0 else -1
                # +1 if signal was right, -1 if wrong
                signal_scores[sig_name] += 1 if sig_direction == actual_direction else -1
                signal_counts[sig_name] += 1

        # Adjust weights: small nudge (±0.02) based on signal accuracy
        for sig_name in weights:
            if signal_counts[sig_name] > 0:
                accuracy = signal_scores[sig_name] / signal_counts[sig_name]
                nudge = accuracy * 0.02  # ±2% weight adjustment
                weights[sig_name] = max(0.05, min(0.50, weights[sig_name] + nudge))

        # Renormalize weights to sum to 1.0
        total = sum(weights.values())
        if total > 0:
            for k in weights:
                weights[k] = round(weights[k] / total, 4)

        self.data["weights"] = weights

    def get_current_predictions(self, market_api, cowen_engine):
        """Get predictions for the coming Friday (generates if needed)."""
        # First evaluate any past predictions
        self.evaluate_past_predictions(market_api)

        # Generate new predictions for this week
        current = self.generate_predictions(market_api, cowen_engine)

        return {
            "target_friday": current["target_date"],
            "generated_at": current["generated_at"],
            "predictions": current["predictions"],
            "weights": self.data["weights"],
            "learning_stats": self.data["learning_stats"],
            "history": self._get_recent_history(),
        }

    def _get_recent_history(self):
        """Get last 8 weeks of prediction results."""
        evaluated = [p for p in self.data["predictions"] if p["evaluated"]]
        recent = evaluated[-8:]
        history = []

        for entry in recent:
            week = {
                "date": entry["target_date"],
                "results": {},
            }
            for asset, result in entry.get("results", {}).items():
                week["results"][asset] = {
                    "predicted": result["predicted"],
                    "actual": result["actual"],
                    "error_pct": result["error_pct"],
                    "correct": result["direction_correct"],
                }
            history.append(week)

        return history
