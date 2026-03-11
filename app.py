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
from api.cowen_llm import CowenLLM
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

# Initialize Cowen LLM (loads existing vector store if available)
_openai_key = os.environ.get("OPENAI_API_KEY", "")
if not _openai_key:
    _key_file = os.path.expanduser("~/.claude/projects/C--Users-15404/memory/api-keys.md")
    if os.path.exists(_key_file):
        with open(_key_file) as _f:
            for _line in _f:
                if "OPENAI_API_KEY" in _line and "sk-" in _line:
                    _openai_key = _line.split("`")[3] if "`" in _line else ""
                    break
cowen_llm = CowenLLM(openai_api_key=_openai_key)

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
        "dogecoin": market_api.get_dogecoin_data(),
        "btc_dominance": market_api.get_btc_dominance(),
    }
    return jsonify(data)

@app.route("/api/analysis/<asset>")
def asset_analysis(asset):
    """Get Cowen-style analysis for a specific asset."""
    valid = ["bitcoin", "ethereum", "gold", "silver", "uranium", "dogecoin", "btc_dominance"]
    if asset not in valid:
        return jsonify({"error": f"Invalid asset. Choose from: {valid}"}), 400
    return jsonify(cowen_engine.analyze(asset))

@app.route("/api/forecasts")
def forecasts():
    """Get 30/60/180 day forecasts for all tracked assets."""
    results = {}
    for asset in ["bitcoin", "ethereum", "gold", "silver", "uranium", "dogecoin", "btc_dominance"]:
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

@app.route("/api/save-transcript", methods=["POST"])
def save_transcript():
    """Receive transcript data from browser automation and save it."""
    data = request.get_json()
    if not data or "video_id" not in data or "text" not in data:
        return jsonify({"error": "Need video_id and text"}), 400

    vid = data["video_id"]
    title = data.get("title", "")
    text = data["text"]
    segments = data.get("segments", [])

    filepath = os.path.join("data", "transcripts", f"{vid}.json")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    result = {
        "video_id": vid,
        "title": title,
        "transcript": segments,
        "full_text": text,
        "word_count": len(text.split()),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "method": "browser_ui",
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)

    # Update progress file
    progress_file = os.path.join("data", "transcript_progress.json")
    progress = {"completed": [], "failed": [], "ip_blocked": [], "total": 0}
    if os.path.exists(progress_file):
        try:
            with open(progress_file, "r") as f:
                progress = json.load(f)
        except:
            pass
    if vid not in progress["completed"]:
        progress["completed"].append(vid)
    with open(progress_file, "w") as f:
        json.dump(progress, f)

    return jsonify({"ok": True, "video_id": vid, "words": result["word_count"],
                     "total_completed": len(progress["completed"])})

@app.route("/api/transcript-progress")
def transcript_progress():
    """Get transcript download progress."""
    progress_file = os.path.join("data", "transcript_progress.json")
    if os.path.exists(progress_file):
        with open(progress_file, "r") as f:
            return jsonify(json.load(f))
    return jsonify({"completed": [], "failed": [], "total": 0})

@app.route("/api/video-list")
def video_list():
    """Get list of all video IDs that still need transcripts."""
    catalog_file = os.path.join("data", "all_videos_raw.txt")
    progress_file = os.path.join("data", "transcript_progress.json")

    videos = []
    if os.path.exists(catalog_file):
        with open(catalog_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "|||" in line:
                    vid, title = line.split("|||", 1)
                    videos.append({"id": vid, "title": title})

    done = set()
    if os.path.exists(progress_file):
        try:
            with open(progress_file, "r") as f:
                progress = json.load(f)
                done = set(progress.get("completed", []) + progress.get("failed", []))
        except:
            pass

    remaining = [v for v in videos if v["id"] not in done]
    return jsonify({"total": len(videos), "done": len(done), "remaining": remaining})

# ========================
# COWEN LLM / CHAT
# ========================

@app.route("/api/chat", methods=["POST"])
def chat():
    """Chat with the Ben Cowen AI. RAG-powered from transcript knowledge base."""
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "Need a 'message' field"}), 400

    message = data["message"].strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400

    # Optional conversation history from client
    history = data.get("history", [])

    result = cowen_llm.chat(message, conversation_history=history)
    return jsonify(result)

@app.route("/api/llm-status")
def llm_status():
    """Get LLM / vector store status."""
    return jsonify(cowen_llm.get_status())

@app.route("/api/llm-build", methods=["POST"])
def llm_build():
    """Trigger a vector store rebuild (async)."""
    force = request.get_json().get("force", False) if request.is_json else False

    def _build():
        cowen_llm.build_vector_store(force=force)

    thread = threading.Thread(target=_build, daemon=True)
    thread.start()
    return jsonify({"status": "building", "message": "Vector store build started in background"})

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
                for asset in ["bitcoin", "ethereum", "gold", "silver", "uranium", "dogecoin", "btc_dominance"]:
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
