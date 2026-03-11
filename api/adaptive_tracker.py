"""
Adaptive Prediction Tracker
Tracks predictions vs actual outcomes to improve forecasting accuracy over time.

- Records each prediction with timestamp
- Compares to actual prices when the forecast period expires
- Calculates accuracy metrics
- Adjusts forecast confidence based on historical accuracy
- Learns which indicators are most predictive in different market conditions
"""
import json
import os
from datetime import datetime, timedelta

PREDICTIONS_FILE = "data/predictions_history.json"
ACCURACY_FILE = "data/accuracy_metrics.json"

class AdaptiveTracker:
    def __init__(self):
        self.predictions = self._load_predictions()
        self.accuracy = self._load_accuracy()

    def _load_predictions(self):
        if os.path.exists(PREDICTIONS_FILE):
            with open(PREDICTIONS_FILE, "r") as f:
                return json.load(f)
        return {"predictions": [], "evaluated": []}

    def _save_predictions(self):
        with open(PREDICTIONS_FILE, "w") as f:
            json.dump(self.predictions, f, indent=2)

    def _load_accuracy(self):
        if os.path.exists(ACCURACY_FILE):
            with open(ACCURACY_FILE, "r") as f:
                return json.load(f)
        return {
            "total_predictions": 0,
            "evaluated": 0,
            "within_range": 0,
            "accuracy_pct": 0,
            "mean_error_pct": 0,
            "by_asset": {},
            "by_period": {},
            "by_indicator": {},
            "confidence_adjustments": {
                "risk_metric": 1.0,
                "cycle_position": 1.0,
                "bull_band": 1.0,
                "macro": 1.0,
                "momentum": 1.0,
                "dominance": 1.0,
            }
        }

    def _save_accuracy(self):
        with open(ACCURACY_FILE, "w") as f:
            json.dump(self.accuracy, f, indent=2)

    def record_prediction(self, asset, period_days, forecast_data, indicators_used):
        """
        Record a new prediction for future evaluation.

        Args:
            asset: 'bitcoin', 'ethereum', etc.
            period_days: 30, 60, or 180
            forecast_data: dict with low_estimate, mid_estimate, high_estimate
            indicators_used: dict of indicator scores used
        """
        prediction = {
            "timestamp": datetime.now().isoformat(),
            "asset": asset,
            "period_days": period_days,
            "evaluate_after": (datetime.now() + timedelta(days=period_days)).isoformat(),
            "forecast": forecast_data,
            "indicators": indicators_used,
            "evaluated": False,
            "actual_price": None,
            "accuracy": None,
        }

        self.predictions["predictions"].append(prediction)
        self._save_predictions()

    def evaluate_expired_predictions(self, current_prices):
        """
        Check all predictions whose period has expired and evaluate accuracy.

        Args:
            current_prices: dict of {asset: current_price}
        """
        now = datetime.now()
        newly_evaluated = 0

        for pred in self.predictions["predictions"]:
            if pred["evaluated"]:
                continue

            eval_date = datetime.fromisoformat(pred["evaluate_after"])
            if now < eval_date:
                continue

            asset = pred["asset"]
            actual = current_prices.get(asset, 0)
            if actual <= 0:
                continue

            forecast = pred["forecast"]
            low = forecast.get("low_estimate", 0)
            high = forecast.get("high_estimate", 0)
            mid = forecast.get("mid_estimate", 0)

            # Calculate accuracy
            within_range = low <= actual <= high if low and high else False
            error_pct = abs(actual - mid) / mid * 100 if mid > 0 else 999

            pred["evaluated"] = True
            pred["actual_price"] = actual
            pred["accuracy"] = {
                "within_range": within_range,
                "error_pct": round(error_pct, 2),
                "actual_vs_mid": round((actual / mid - 1) * 100, 2) if mid > 0 else 0,
            }

            self.predictions["evaluated"].append(pred)
            newly_evaluated += 1

            # Update accuracy metrics
            self._update_accuracy(pred)

        if newly_evaluated > 0:
            self._save_predictions()
            self._save_accuracy()

        return newly_evaluated

    def _update_accuracy(self, pred):
        """Update running accuracy metrics."""
        acc = self.accuracy
        acc["total_predictions"] = len(self.predictions["predictions"])
        acc["evaluated"] += 1

        if pred["accuracy"]["within_range"]:
            acc["within_range"] += 1

        acc["accuracy_pct"] = round(acc["within_range"] / acc["evaluated"] * 100, 1) if acc["evaluated"] > 0 else 0

        # Running mean error
        prev_total_error = acc.get("mean_error_pct", 0) * (acc["evaluated"] - 1)
        acc["mean_error_pct"] = round((prev_total_error + pred["accuracy"]["error_pct"]) / acc["evaluated"], 2)

        # By asset
        asset = pred["asset"]
        if asset not in acc["by_asset"]:
            acc["by_asset"][asset] = {"total": 0, "within_range": 0, "mean_error": 0}

        aa = acc["by_asset"][asset]
        aa["total"] += 1
        if pred["accuracy"]["within_range"]:
            aa["within_range"] += 1
        prev_err = aa["mean_error"] * (aa["total"] - 1)
        aa["mean_error"] = round((prev_err + pred["accuracy"]["error_pct"]) / aa["total"], 2)

        # By period
        period = str(pred["period_days"])
        if period not in acc["by_period"]:
            acc["by_period"][period] = {"total": 0, "within_range": 0}
        pp = acc["by_period"][period]
        pp["total"] += 1
        if pred["accuracy"]["within_range"]:
            pp["within_range"] += 1

        # Adjust indicator confidence based on whether high-confidence indicators were right
        indicators = pred.get("indicators", {})
        for ind_name, ind_score in indicators.items():
            if ind_name not in acc["confidence_adjustments"]:
                acc["confidence_adjustments"][ind_name] = 1.0

            # If prediction was correct and this indicator contributed strongly,
            # increase its confidence. If wrong, decrease it.
            if pred["accuracy"]["within_range"]:
                # Slight boost for indicators that contributed to correct prediction
                if abs(ind_score) > 0.3:
                    acc["confidence_adjustments"][ind_name] *= 1.02
            else:
                # Slight reduction for strong indicators that contributed to wrong prediction
                if abs(ind_score) > 0.3:
                    acc["confidence_adjustments"][ind_name] *= 0.98

            # Clamp between 0.5 and 2.0
            acc["confidence_adjustments"][ind_name] = max(0.5, min(2.0, acc["confidence_adjustments"][ind_name]))

    def get_confidence_adjustments(self):
        """Get current confidence adjustments for each indicator."""
        return self.accuracy.get("confidence_adjustments", {})

    def get_accuracy_report(self):
        """Get a full accuracy report."""
        return {
            "total_predictions": self.accuracy.get("total_predictions", 0),
            "evaluated": self.accuracy.get("evaluated", 0),
            "within_range": self.accuracy.get("within_range", 0),
            "accuracy_pct": self.accuracy.get("accuracy_pct", 0),
            "mean_error_pct": self.accuracy.get("mean_error_pct", 0),
            "by_asset": self.accuracy.get("by_asset", {}),
            "by_period": self.accuracy.get("by_period", {}),
            "confidence_adjustments": self.accuracy.get("confidence_adjustments", {}),
            "recent_predictions": self.predictions.get("predictions", [])[-10:],
        }

    def record_daily_snapshot(self, forecasts_data, prices_data):
        """
        Called daily to record current forecasts and prices.
        Over time, this builds up training data for adaptive improvement.
        """
        snapshot = {
            "date": datetime.now().isoformat(),
            "prices": prices_data,
            "forecasts": {}
        }

        for asset, forecast in forecasts_data.items():
            if "forecasts" in forecast:
                for period, fdata in forecast["forecasts"].items():
                    key = f"{asset}_{period}"
                    if fdata.get("low_estimate"):
                        snapshot["forecasts"][key] = {
                            "low": fdata["low_estimate"],
                            "mid": fdata.get("mid_estimate", 0),
                            "high": fdata["high_estimate"],
                        }

        # Record predictions for tracking
        for asset in ["bitcoin", "ethereum", "gold", "silver", "uranium"]:
            if asset in forecasts_data and "forecasts" in forecasts_data[asset]:
                for period_key, fdata in forecasts_data[asset]["forecasts"].items():
                    if not fdata.get("low_estimate"):
                        continue
                    days = int(period_key.split("_")[0])
                    indicators = forecasts_data[asset].get("score_components", {})
                    self.record_prediction(asset, days, fdata, indicators)

        # Save snapshot
        snapshots_dir = "data/snapshots"
        os.makedirs(snapshots_dir, exist_ok=True)
        fname = datetime.now().strftime("%Y%m%d") + ".json"
        with open(os.path.join(snapshots_dir, fname), "w") as f:
            json.dump(snapshot, f, indent=2)
