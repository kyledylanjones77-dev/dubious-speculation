"""
Self-Learning Daily & Weekly Prediction Engine
Built on 151 transcripts / 492,605 words of Benjamin Cowen's analysis.

Makes daily and weekly price predictions for all tracked assets.
After each prediction period expires, evaluates accuracy and automatically
adjusts signal weights — amplifying what works, dampening what doesn't.

Learning loop:
  1. Generate prediction using weighted signals
  2. Wait for prediction window to expire
  3. Compare predicted vs actual
  4. Score each individual signal's contribution
  5. Nudge weights toward signals that were right
  6. Repeat — the model gets smarter over time
"""

import json
import os
import math
from datetime import datetime, timedelta

DATA_DIR = "data"
DAILY_FILE = os.path.join(DATA_DIR, "daily_predictions.json")

ASSETS = ["bitcoin", "ethereum", "gold", "silver", "uranium", "dogecoin"]

# 8 signals — each returns a % change expectation
SIGNAL_NAMES = [
    "regression",      # log regression fair value pull
    "momentum_7d",     # 7-day price momentum
    "momentum_30d",    # 30-day price momentum
    "mean_reversion",  # 20-day SMA reversion
    "volatility",      # volatility compression/expansion
    "macro_health",    # economy health score
    "cowen_thesis",    # Cowen's directional thesis from transcripts
    "cycle_position",  # 4-year halving cycle position
]

DEFAULT_WEIGHTS = {s: round(1.0 / len(SIGNAL_NAMES), 4) for s in SIGNAL_NAMES}


class DailyPredictor:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.data = self._load()

    def _load(self):
        if os.path.exists(DAILY_FILE):
            try:
                with open(DAILY_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "daily_predictions": [],
            "weekly_predictions": [],
            "weights": dict(DEFAULT_WEIGHTS),
            "learning_history": [],
            "stats": {
                "total_daily": 0,
                "total_weekly": 0,
                "daily_evaluated": 0,
                "weekly_evaluated": 0,
                "daily_direction_correct": 0,
                "weekly_direction_correct": 0,
                "daily_avg_error": 0,
                "weekly_avg_error": 0,
                "best_daily_streak": 0,
                "current_daily_streak": 0,
                "weight_updates": 0,
            },
        }

    def _save(self):
        with open(DAILY_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    # ─── Signal Calculators ───

    def _calc_regression(self, asset, current, market_api, cowen_engine):
        """Log regression fair value pull — strongest for BTC."""
        if asset != "bitcoin":
            return 0
        try:
            risk = cowen_engine.get_risk_metric()
            fair = risk.get("fair_value", current)
            if fair > 0 and current > 0:
                gap = (fair - current) / current
                return gap * 0.005  # 0.5% of gap per day
        except Exception:
            pass
        return 0

    def _calc_momentum_7d(self, prices, current):
        """7-day momentum — trend continuation."""
        if len(prices) < 7 or current <= 0:
            return 0
        week_ago = prices[-7]
        if week_ago <= 0:
            return 0
        weekly_ret = (current - week_ago) / week_ago
        return weekly_ret * 0.06  # 6% carry-forward per day

    def _calc_momentum_30d(self, prices, current):
        """30-day momentum — longer trend."""
        if len(prices) < 30 or current <= 0:
            return 0
        month_ago = prices[-30]
        if month_ago <= 0:
            return 0
        monthly_ret = (current - month_ago) / month_ago
        return monthly_ret * 0.015  # 1.5% carry-forward per day

    def _calc_mean_reversion(self, prices, current):
        """20-day SMA pull — revert to mean."""
        if len(prices) < 20 or current <= 0:
            return 0
        sma_20 = sum(prices[-20:]) / 20
        if sma_20 <= 0:
            return 0
        deviation = (current - sma_20) / sma_20
        return -deviation * 0.02  # 2% daily reversion

    def _calc_volatility(self, prices, current):
        """Volatility signal — compressed vol often precedes moves."""
        if len(prices) < 20 or current <= 0:
            return 0
        # Daily returns
        returns = []
        for i in range(1, min(20, len(prices))):
            if prices[i - 1] > 0:
                returns.append((prices[i] - prices[i - 1]) / prices[i - 1])
        if not returns:
            return 0
        vol = (sum(r ** 2 for r in returns) / len(returns)) ** 0.5
        avg_vol = 0.02  # ~2% daily vol is average for crypto
        if vol < avg_vol * 0.6:
            # Low vol → expect expansion, slight mean reversion
            sma = sum(prices[-10:]) / 10
            return (sma - current) / current * 0.01
        elif vol > avg_vol * 1.5:
            # High vol → expect contraction, pull toward SMA
            sma = sum(prices[-10:]) / 10
            return (sma - current) / current * 0.015
        return 0

    def _calc_macro(self, market_api):
        """Macro health influence — positive economy = slight bullish."""
        try:
            econ = market_api.get_macro_economy()
            score = econ.get("assessment", {}).get("score", 0)
            return score / 100 * 0.001  # ±0.1% daily max
        except Exception:
            return 0

    def _calc_thesis(self, asset, cowen_engine):
        """Cowen's thesis from 151 transcripts."""
        try:
            thesis = cowen_engine.cowen_thesis
            if not thesis:
                return 0

            outlook = thesis.get("overall", "").lower()
            btc_view = thesis.get("btc_near_term", "").lower()

            # Asset-specific thesis
            if asset == "bitcoin":
                if "bear" in outlook or "lower high" in btc_view:
                    return -0.002  # -0.2% daily drag
                elif "bull" in outlook:
                    return 0.002
                return -0.001  # cautious = slight negative

            elif asset == "ethereum":
                eth_view = thesis.get("eth_view", "").lower()
                if "bleeding" in eth_view or "regression band" in eth_view:
                    return -0.003
                return -0.001

            elif asset == "gold":
                gold_view = thesis.get("gold_view", "").lower()
                if "correction" in gold_view:
                    return -0.002
                return 0.001

            else:
                # Other assets follow BTC thesis with dampening
                if "bear" in outlook:
                    return -0.001
                elif "bull" in outlook:
                    return 0.001
                return 0

        except Exception:
            return 0

    def _calc_cycle(self, asset, cowen_engine):
        """4-year halving cycle position."""
        if asset != "bitcoin":
            return 0
        try:
            cycle = cowen_engine.get_cycle_analysis()
            progress = cycle.get("cycle_progress", 0.5)
            phase = cycle.get("cycle_phase", "")

            # Midterm year (Year 2) historically weak
            if "Year 2" in phase:
                return -0.001  # slight daily headwind
            elif "Year 3" in phase:
                return 0.002  # Year 3 historically strongest
            elif "Year 4" in phase or "Year 1" in phase:
                return 0.001
            return 0
        except Exception:
            return 0

    # ─── Core Prediction ───

    def _get_asset_data(self, asset, market_api):
        """Get current price and price history for an asset."""
        getter = {
            "bitcoin": market_api.get_bitcoin_data,
            "ethereum": market_api.get_ethereum_data,
            "gold": market_api.get_gold_data,
            "silver": market_api.get_silver_data,
            "uranium": market_api.get_uranium_data,
            "dogecoin": market_api.get_dogecoin_data,
        }
        fn = getter.get(asset)
        if not fn:
            return 0, []
        data = fn()
        price = data.get("current_price", 0)
        history = data.get("price_history", [])
        prices = [h["price"] for h in history if h.get("price")] if history else []
        return price, prices

    def _predict_asset(self, asset, horizon, market_api, cowen_engine):
        """
        Generate a prediction for one asset.
        horizon: 'daily' (1 day) or 'weekly' (7 days)
        """
        current, prices = self._get_asset_data(asset, market_api)
        if current <= 0:
            return {"error": "No price data"}

        weights = self.data["weights"]
        days = 1 if horizon == "daily" else 7

        # Calculate all signals (per-day basis)
        signals = {
            "regression": self._calc_regression(asset, current, market_api, cowen_engine),
            "momentum_7d": self._calc_momentum_7d(prices, current),
            "momentum_30d": self._calc_momentum_30d(prices, current),
            "mean_reversion": self._calc_mean_reversion(prices, current),
            "volatility": self._calc_volatility(prices, current),
            "macro_health": self._calc_macro(market_api),
            "cowen_thesis": self._calc_thesis(asset, cowen_engine),
            "cycle_position": self._calc_cycle(asset, cowen_engine),
        }

        # Weighted sum of daily signals, scaled by horizon
        daily_change = sum(weights.get(k, 0) * v for k, v in signals.items())
        total_change = daily_change * days

        # Clamp: daily ±3%, weekly ±8%
        max_change = 0.03 if horizon == "daily" else 0.08
        total_change = max(-max_change, min(max_change, total_change))

        predicted_price = current * (1 + total_change)

        # Confidence from signal agreement
        directions = [1 if v > 0.0001 else -1 if v < -0.0001 else 0 for v in signals.values()]
        nonzero = [d for d in directions if d != 0]
        if nonzero:
            agreement = abs(sum(nonzero)) / len(nonzero)
        else:
            agreement = 0
        confidence = round(25 + agreement * 55)  # 25-80% range

        # Direction label
        if total_change > 0.003:
            direction = "UP"
        elif total_change < -0.003:
            direction = "DOWN"
        else:
            direction = "FLAT"

        return {
            "current_price": round(current, 6 if current < 1 else 2),
            "predicted_price": round(predicted_price, 6 if predicted_price < 1 else 2),
            "predicted_change_pct": round(total_change * 100, 3),
            "direction": direction,
            "confidence": confidence,
            "signals": {k: round(v * 100 * days, 4) for k, v in signals.items()},
        }

    # ─── Generate Predictions ───

    def generate_daily(self, market_api, cowen_engine):
        """Generate daily predictions for all assets."""
        today = datetime.now().strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        # Don't regenerate if we already have today's
        existing = [p for p in self.data["daily_predictions"] if p["generated_date"] == today]
        if existing:
            return existing[0]

        predictions = {}
        for asset in ASSETS:
            try:
                predictions[asset] = self._predict_asset(asset, "daily", market_api, cowen_engine)
            except Exception as e:
                predictions[asset] = {"error": str(e)}

        entry = {
            "generated_date": today,
            "target_date": tomorrow,
            "generated_at": datetime.now().isoformat(),
            "predictions": predictions,
            "weights_used": dict(self.data["weights"]),
            "evaluated": False,
        }

        self.data["daily_predictions"].append(entry)
        self.data["stats"]["total_daily"] += len([p for p in predictions.values() if "error" not in p])
        self._save()
        return entry

    def generate_weekly(self, market_api, cowen_engine):
        """Generate weekly predictions (Monday→Friday or current→+7days)."""
        today = datetime.now().strftime("%Y-%m-%d")
        target = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

        # Don't regenerate if we have one this week
        week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
        existing = [p for p in self.data["weekly_predictions"]
                    if p["generated_date"] >= week_start and not p["evaluated"]]
        if existing:
            return existing[0]

        predictions = {}
        for asset in ASSETS:
            try:
                predictions[asset] = self._predict_asset(asset, "weekly", market_api, cowen_engine)
            except Exception as e:
                predictions[asset] = {"error": str(e)}

        entry = {
            "generated_date": today,
            "target_date": target,
            "generated_at": datetime.now().isoformat(),
            "predictions": predictions,
            "weights_used": dict(self.data["weights"]),
            "evaluated": False,
        }

        self.data["weekly_predictions"].append(entry)
        self.data["stats"]["total_weekly"] += len([p for p in predictions.values() if "error" not in p])
        self._save()
        return entry

    # ─── Evaluate & Learn ───

    def evaluate_predictions(self, market_api):
        """Evaluate all expired predictions and learn from results."""
        today = datetime.now().strftime("%Y-%m-%d")
        learned = False

        # Evaluate daily predictions
        for entry in self.data["daily_predictions"]:
            if entry["evaluated"] or entry["target_date"] >= today:
                continue
            results = self._evaluate_entry(entry, market_api)
            if results:
                entry["results"] = results
                entry["evaluated"] = True
                self._learn_from_results(entry, "daily")
                learned = True

        # Evaluate weekly predictions
        for entry in self.data["weekly_predictions"]:
            if entry["evaluated"] or entry["target_date"] >= today:
                continue
            results = self._evaluate_entry(entry, market_api)
            if results:
                entry["results"] = results
                entry["evaluated"] = True
                self._learn_from_results(entry, "weekly")
                learned = True

        if learned:
            self._save()

    def _evaluate_entry(self, entry, market_api):
        """Compare predictions to actual prices."""
        results = {}
        for asset, pred in entry["predictions"].items():
            if "error" in pred:
                continue
            try:
                current, _ = self._get_asset_data(asset, market_api)
                if current <= 0:
                    continue

                predicted = pred["predicted_price"]
                original = pred["current_price"]
                error_pct = abs(predicted - current) / current * 100

                actual_change = (current - original) / original if original > 0 else 0
                predicted_change = pred["predicted_change_pct"] / 100

                direction_correct = (
                    (pred["direction"] == "UP" and current > original) or
                    (pred["direction"] == "DOWN" and current < original) or
                    (pred["direction"] == "FLAT" and abs(current - original) / original < 0.005)
                )

                results[asset] = {
                    "predicted": predicted,
                    "actual": round(current, 6 if current < 1 else 2),
                    "error_pct": round(error_pct, 3),
                    "direction_correct": direction_correct,
                    "actual_change_pct": round(actual_change * 100, 3),
                    "predicted_change_pct": pred["predicted_change_pct"],
                }
            except Exception:
                continue
        return results

    def _learn_from_results(self, entry, horizon):
        """Adjust weights based on which signals predicted correctly."""
        results = entry.get("results", {})
        predictions = entry["predictions"]
        weights = self.data["weights"]
        stats = self.data["stats"]

        signal_scores = {s: 0.0 for s in SIGNAL_NAMES}
        signal_counts = {s: 0 for s in SIGNAL_NAMES}

        for asset, result in results.items():
            pred = predictions.get(asset, {})
            signals = pred.get("signals", {})
            actual_dir = 1 if result["actual_change_pct"] > 0.1 else -1 if result["actual_change_pct"] < -0.1 else 0

            # Update stats
            key = "daily" if horizon == "daily" else "weekly"
            stats[f"{key}_evaluated"] += 1
            if result["direction_correct"]:
                stats[f"{key}_direction_correct"] += 1
                if key == "daily":
                    stats["current_daily_streak"] += 1
                    stats["best_daily_streak"] = max(stats["best_daily_streak"], stats["current_daily_streak"])
            else:
                if key == "daily":
                    stats["current_daily_streak"] = 0

            # Running average error
            n = stats[f"{key}_evaluated"]
            prev_avg = stats[f"{key}_avg_error"]
            stats[f"{key}_avg_error"] = round(((prev_avg * (n - 1)) + result["error_pct"]) / n, 3)

            # Score each signal
            for sig_name, sig_value in signals.items():
                if sig_value == 0:
                    continue
                sig_dir = 1 if sig_value > 0 else -1
                if actual_dir == 0:
                    continue
                # +1 if signal pointed in actual direction, -1 if wrong
                signal_scores[sig_name] += 1.0 if sig_dir == actual_dir else -1.0
                signal_counts[sig_name] += 1

        # Adjust weights — larger nudge for daily (more data), smaller for weekly
        nudge_size = 0.015 if horizon == "daily" else 0.025
        for sig in SIGNAL_NAMES:
            if signal_counts[sig] > 0:
                accuracy_ratio = signal_scores[sig] / signal_counts[sig]  # -1 to +1
                adjustment = accuracy_ratio * nudge_size
                weights[sig] = max(0.03, min(0.40, weights[sig] + adjustment))

        # Renormalize to sum to 1.0
        total = sum(weights.values())
        if total > 0:
            for k in weights:
                weights[k] = round(weights[k] / total, 4)

        self.data["weights"] = weights
        stats["weight_updates"] += 1

        # Record learning event
        self.data["learning_history"].append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "horizon": horizon,
            "signal_scores": {k: round(v, 2) for k, v in signal_scores.items()},
            "new_weights": dict(weights),
        })
        # Keep only last 60 learning events
        self.data["learning_history"] = self.data["learning_history"][-60:]

    # ─── Public API ───

    def get_predictions(self, market_api, cowen_engine):
        """Get current daily + weekly predictions. Evaluates past ones first."""
        self.evaluate_predictions(market_api)

        daily = self.generate_daily(market_api, cowen_engine)
        weekly = self.generate_weekly(market_api, cowen_engine)

        stats = self.data["stats"]
        daily_acc = (
            round(stats["daily_direction_correct"] / stats["daily_evaluated"] * 100, 1)
            if stats["daily_evaluated"] > 0 else None
        )
        weekly_acc = (
            round(stats["weekly_direction_correct"] / stats["weekly_evaluated"] * 100, 1)
            if stats["weekly_evaluated"] > 0 else None
        )

        return {
            "daily": {
                "target_date": daily["target_date"],
                "generated_at": daily["generated_at"],
                "predictions": daily["predictions"],
            },
            "weekly": {
                "target_date": weekly["target_date"],
                "generated_at": weekly["generated_at"],
                "predictions": weekly["predictions"],
            },
            "weights": self.data["weights"],
            "stats": {
                "daily_predictions": stats["total_daily"],
                "weekly_predictions": stats["total_weekly"],
                "daily_evaluated": stats["daily_evaluated"],
                "weekly_evaluated": stats["weekly_evaluated"],
                "daily_accuracy": daily_acc,
                "weekly_accuracy": weekly_acc,
                "daily_avg_error": stats["daily_avg_error"],
                "weekly_avg_error": stats["weekly_avg_error"],
                "best_streak": stats["best_daily_streak"],
                "current_streak": stats["current_daily_streak"],
                "weight_updates": stats["weight_updates"],
            },
            "recent_learning": self.data["learning_history"][-5:],
            "history": self._get_history(),
        }

    def _get_history(self):
        """Get recent evaluated predictions for display."""
        daily_eval = [p for p in self.data["daily_predictions"] if p["evaluated"]][-14:]
        weekly_eval = [p for p in self.data["weekly_predictions"] if p["evaluated"]][-8:]

        history = []
        for entry in daily_eval:
            h = {"date": entry["target_date"], "type": "daily", "results": {}}
            for asset, result in entry.get("results", {}).items():
                h["results"][asset] = {
                    "predicted": result["predicted"],
                    "actual": result["actual"],
                    "error": result["error_pct"],
                    "correct": result["direction_correct"],
                }
            history.append(h)

        for entry in weekly_eval:
            h = {"date": entry["target_date"], "type": "weekly", "results": {}}
            for asset, result in entry.get("results", {}).items():
                h["results"][asset] = {
                    "predicted": result["predicted"],
                    "actual": result["actual"],
                    "error": result["error_pct"],
                    "correct": result["direction_correct"],
                }
            history.append(h)

        return sorted(history, key=lambda x: x["date"], reverse=True)
