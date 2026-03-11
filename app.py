"""
Dubious Speculation Trading App
Based on Benjamin Cowen's (Into the Cryptoverse) analytical frameworks.

Tracks: Bitcoin, Ethereum, Gold, Silver, Uranium, BTC Dominance
Provides: 30-day, 60-day, 180-day forecasts using Cowen's methodology
Auto-updates when new videos are released.
"""
from flask import Flask, render_template, jsonify, request
from api.market_data import MarketDataAPI
from api.cowen_engine import CowenAnalysisEngine
from api.video_updater import VideoUpdater
from api.adaptive_tracker import AdaptiveTracker
from api.friday_predictor import FridayPredictor
import json
import os
import threading
import time

app = Flask(__name__)

# Initialize components
market_api = MarketDataAPI()
cowen_engine = CowenAnalysisEngine()
video_updater = VideoUpdater()
adaptive_tracker = AdaptiveTracker()
friday_predictor = FridayPredictor()

# ========================
# PAGES
# ========================

@app.route("/")
def index():
    return render_template("index.html")

# ========================
# API ENDPOINTS
# ========================

@app.route("/api/dashboard")
def dashboard_data():
    """Get all dashboard data in one call."""
    data = {
        "bitcoin": market_api.get_bitcoin_data(),
        "ethereum": market_api.get_ethereum_data(),
        "gold": market_api.get_gold_data(),
        "silver": market_api.get_silver_data(),
        "uranium": market_api.get_uranium_data(),
        "btc_dominance": market_api.get_btc_dominance(),
    }
    return jsonify(data)

@app.route("/api/analysis/<asset>")
def asset_analysis(asset):
    """Get Cowen-style analysis for a specific asset."""
    valid = ["bitcoin", "ethereum", "gold", "silver", "uranium", "btc_dominance"]
    if asset not in valid:
        return jsonify({"error": f"Invalid asset. Choose from: {valid}"}), 400
    return jsonify(cowen_engine.analyze(asset))

@app.route("/api/forecasts")
def forecasts():
    """Get 30/60/180 day forecasts for all tracked assets."""
    results = {}
    for asset in ["bitcoin", "ethereum", "gold", "silver", "uranium", "btc_dominance"]:
        results[asset] = cowen_engine.get_forecasts(asset)
    return jsonify(results)

@app.route("/api/risk-metric")
def risk_metric():
    """Get the Bitcoin risk metric (0-1 scale)."""
    return jsonify(cowen_engine.get_risk_metric())

@app.route("/api/regression-bands/<asset>")
def regression_bands(asset):
    """Get logarithmic regression band data."""
    return jsonify(cowen_engine.get_regression_bands(asset))

@app.route("/api/cycle-analysis")
def cycle_analysis():
    """Get 4-year cycle analysis."""
    return jsonify(cowen_engine.get_cycle_analysis())

@app.route("/api/macro")
def macro_indicators():
    """Get macro indicators."""
    return jsonify(market_api.get_macro_data())

@app.route("/api/macro-economy")
def macro_economy():
    """Get macroeconomic health: unemployment, jobless claims, payrolls, VIX, S&P 500."""
    return jsonify(market_api.get_macro_economy())

@app.route("/api/cowen-insights")
def cowen_insights():
    """Get latest insights from transcripts."""
    return jsonify(cowen_engine.get_latest_insights())

@app.route("/api/btc-history")
def btc_history():
    """Get full BTC price history for charting."""
    data = market_api.get_bitcoin_data()
    history = data.get("price_history", [])

    # Also calculate regression bands over time
    bands_over_time = cowen_engine.get_regression_bands_timeseries(history)

    return jsonify({
        "price_history": history,
        "regression_bands": bands_over_time,
    })

@app.route("/api/composite-score")
def composite_score():
    """Get the master composite score combining all Cowen frameworks."""
    return jsonify(cowen_engine.get_composite_score())

@app.route("/api/update-videos")
def update_videos():
    """Check for new videos."""
    result = video_updater.check_for_new_videos()
    return jsonify(result)

@app.route("/api/transcript-stats")
def transcript_stats():
    """Get transcript download/analysis stats."""
    return jsonify(video_updater.get_transcript_stats())

@app.route("/api/accuracy")
def accuracy_report():
    """Get prediction accuracy report showing how well forecasts performed."""
    return jsonify(adaptive_tracker.get_accuracy_report())

@app.route("/api/friday-predictions")
def friday_predictions():
    """Get weekly Friday price predictions with learning stats."""
    return jsonify(friday_predictor.get_current_predictions(market_api, cowen_engine))

@app.route("/api/confidence")
def confidence_adjustments():
    """Get current indicator confidence adjustments from adaptive learning."""
    return jsonify(adaptive_tracker.get_confidence_adjustments())

# ========================
# BACKGROUND VIDEO CHECKER
# ========================

def background_tasks():
    """Run periodic background tasks: video checks, daily snapshots, prediction evaluation, keep-alive."""
    import requests as bg_requests
    last_snapshot = None
    ping_count = 0

    while True:
        time.sleep(600)  # Every 10 minutes
        now = time.strftime("%Y-%m-%d")
        ping_count += 1

        # Self-ping keep-alive (prevents Render free tier from sleeping)
        render_url = os.environ.get("RENDER_EXTERNAL_URL")
        if render_url:
            try:
                bg_requests.get(f"{render_url}/api/risk-metric", timeout=10)
            except Exception:
                pass

        # Daily snapshot (once per day)
        if now != last_snapshot:
            try:
                # Record daily forecast snapshot for adaptive learning
                forecasts = {}
                prices = {}
                for asset in ["bitcoin", "ethereum", "gold", "silver", "uranium", "btc_dominance"]:
                    forecasts[asset] = cowen_engine.get_forecasts(asset)
                    if asset == "btc_dominance":
                        dom = market_api.get_btc_dominance()
                        prices[asset] = dom.get("btc_dominance", 0)
                    else:
                        data = getattr(market_api, f"get_{asset}_data")()
                        prices[asset] = data.get("current_price", 0)

                adaptive_tracker.record_daily_snapshot(forecasts, prices)
                adaptive_tracker.evaluate_expired_predictions(prices)
                last_snapshot = now
                print(f"[DAILY] Snapshot recorded for {now}")
            except Exception as e:
                print(f"[DAILY] Snapshot error: {e}")

        # Video check every 6 hours (~36 pings)
        if ping_count % 36 == 0:
            try:
                result = video_updater.check_for_new_videos()
                if result.get("new_videos_found", 0) > 0:
                    print(f"[AUTO-UPDATE] Found {result['new_videos_found']} new videos!")
                    from analysis.transcript_analyzer import TranscriptAnalyzer
                    analyzer = TranscriptAnalyzer()
                    analyzer.load_transcripts()
                    analyzer.analyze_all()
                    analyzer.save_results()
                    # Reload engine thesis
                    cowen_engine.cowen_thesis = cowen_engine._load_cowen_thesis()
                    print("[AUTO-UPDATE] Knowledge base updated!")
            except Exception as e:
                print(f"[AUTO-UPDATE] Error: {e}")

# ========================
# STARTUP
# ========================

def start_background():
    """Start background thread (called by both dev and gunicorn)."""
    bg_thread = threading.Thread(target=background_tasks, daemon=True)
    bg_thread.start()

# Auto-start background tasks when loaded by gunicorn
start_background()

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  DUBIOUS SPECULATION")
    print("  Based on Benjamin Cowen's analytical frameworks")
    print("  http://localhost:5000")
    print("="*60 + "\n")

    app.run(debug=True, port=5000, use_reloader=False)
