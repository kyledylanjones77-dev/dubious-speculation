"""
Transcript Analyzer
Processes Benjamin Cowen's video transcripts to extract:
- Key indicators mentioned and their values
- Market views and predictions
- Framework references
- Chronological evolution of thinking
"""
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime

TRANSCRIPT_DIR = "data/transcripts"
OUTPUT_DIR = "data"

# Key terms and frameworks to track
INDICATORS = {
    "risk_metric": ["risk metric", "risk score", "risk level", "risk model"],
    "logarithmic_regression": ["logarithmic regression", "log regression", "regression band", "regression line", "fair value"],
    "bull_market_support": ["bull market support band", "bull market support", "20 week", "21 week", "support band"],
    "bear_market_resistance": ["bear market resistance", "resistance band"],
    "200_week_sma": ["200 week", "200-week", "200 week moving average", "200 week sma"],
    "btc_dominance": ["bitcoin dominance", "btc dominance", "dominance"],
    "four_year_cycle": ["four year cycle", "4 year cycle", "halving cycle", "halving", "post halving", "pre halving", "midterm year"],
    "dxy": ["dollar index", "dxy", "us dollar"],
    "fed_rates": ["fed", "federal reserve", "interest rate", "rate cut", "rate hike", "quantitative"],
    "oil": ["oil", "crude oil", "wti", "business cycle"],
    "yield_curve": ["yield curve", "inverted", "inversion", "treasury"],
    "gold": ["gold", "xau"],
    "silver": ["silver", "xag", "gold silver ratio"],
    "uranium": ["uranium", "nuclear"],
    "eth_btc": ["eth btc", "ethereum bitcoin", "eth/btc"],
    "alt_season": ["alt season", "altcoin season", "alt coin", "altcoin"],
    "stock_to_flow": ["stock to flow", "s2f"],
    "lengthening_cycles": ["lengthening cycle", "diminishing returns"],
    "total_crypto_market": ["total crypto", "total market cap", "cryptocurrency market"],
    "recession": ["recession", "recessionary"],
    "mayer_multiple": ["mayer multiple"],
    "pi_cycle": ["pi cycle"],
    "roi": ["return on investment", "roi"],
    "macro": ["macro", "macroeconomic"],
}

SENTIMENT_WORDS = {
    "bullish": ["bullish", "upside", "accumulate", "accumulation", "buy", "undervalued", "oversold", "support", "breakout", "recovery"],
    "bearish": ["bearish", "downside", "sell", "overvalued", "overbought", "resistance", "breakdown", "crash", "correction", "decline"],
    "neutral": ["sideways", "consolidation", "range bound", "neutral", "fair value"],
    "cautious": ["cautious", "careful", "risk", "warning", "concern", "uncertain"],
}

ASSET_MENTIONS = {
    "bitcoin": ["bitcoin", "btc"],
    "ethereum": ["ethereum", "eth", "ether"],
    "gold": ["gold", "xau"],
    "silver": ["silver", "xag"],
    "uranium": ["uranium", "ura"],
    "stocks": ["stocks", "s&p", "nasdaq", "dow jones", "equities", "spy"],
    "altcoins": ["altcoin", "alt coin", "alts"],
}


class TranscriptAnalyzer:
    def __init__(self):
        self.transcripts = []
        self.analysis_results = {}

    def load_transcripts(self):
        """Load all available transcripts."""
        if not os.path.exists(TRANSCRIPT_DIR):
            print("No transcripts directory found")
            return

        files = sorted(os.listdir(TRANSCRIPT_DIR))
        for fname in files:
            if not fname.endswith(".json"):
                continue
            filepath = os.path.join(TRANSCRIPT_DIR, fname)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.transcripts.append(data)
            except Exception as e:
                print(f"Error loading {fname}: {e}")

        print(f"Loaded {len(self.transcripts)} transcripts")

    def analyze_all(self):
        """Run full analysis on all transcripts."""
        results = {
            "analyzed_at": datetime.now().isoformat(),
            "total_transcripts": len(self.transcripts),
            "total_words": sum(t.get("word_count", 0) for t in self.transcripts),
            "indicator_frequency": self._count_indicators(),
            "sentiment_analysis": self._analyze_sentiment(),
            "asset_focus": self._count_asset_mentions(),
            "key_phrases": self._extract_key_phrases(),
            "framework_details": self._extract_framework_details(),
            "price_mentions": self._extract_price_mentions(),
            "predictions": self._extract_predictions(),
        }

        self.analysis_results = results
        return results

    def _count_indicators(self):
        """Count how often each indicator/framework is mentioned."""
        counts = Counter()
        for transcript in self.transcripts:
            text = transcript.get("full_text", "").lower()
            for indicator, keywords in INDICATORS.items():
                for kw in keywords:
                    count = text.count(kw)
                    if count > 0:
                        counts[indicator] += count

        return dict(counts.most_common())

    def _analyze_sentiment(self):
        """Analyze overall sentiment across transcripts."""
        sentiment_counts = Counter()
        per_transcript = []

        for transcript in self.transcripts:
            text = transcript.get("full_text", "").lower()
            t_sentiment = Counter()

            for sentiment, words in SENTIMENT_WORDS.items():
                for word in words:
                    count = text.count(word)
                    t_sentiment[sentiment] += count
                    sentiment_counts[sentiment] += count

            # Determine dominant sentiment for this transcript
            if t_sentiment:
                dominant = t_sentiment.most_common(1)[0][0]
            else:
                dominant = "neutral"

            per_transcript.append({
                "title": transcript.get("title", ""),
                "dominant_sentiment": dominant,
                "scores": dict(t_sentiment),
            })

        return {
            "overall": dict(sentiment_counts),
            "per_transcript": per_transcript[:20],  # Top 20 for display
        }

    def _count_asset_mentions(self):
        """Count mentions of each asset class."""
        counts = Counter()
        for transcript in self.transcripts:
            text = transcript.get("full_text", "").lower()
            for asset, keywords in ASSET_MENTIONS.items():
                for kw in keywords:
                    counts[asset] += text.count(kw)

        return dict(counts.most_common())

    def _extract_key_phrases(self):
        """Extract frequently repeated key phrases (Cowen's catchphrases)."""
        # Known Cowen phrases
        known_phrases = [
            "beauty of mathematics",
            "dubious speculation",
            "risk metric",
            "bull market support band",
            "logarithmic regression",
            "fair value",
            "200 week",
            "4 year cycle",
            "lengthening cycles",
            "diminishing returns",
            "bitcoin dominance",
            "alt season",
            "macro environment",
            "business cycle",
            "midterm year",
            "post halving",
            "pre halving",
            "rate cuts",
            "quantitative tightening",
            "quantitative easing",
            "total addressable market",
            "market cap",
        ]

        phrase_counts = Counter()
        for transcript in self.transcripts:
            text = transcript.get("full_text", "").lower()
            for phrase in known_phrases:
                count = text.count(phrase)
                if count > 0:
                    phrase_counts[phrase] += count

        return dict(phrase_counts.most_common(20))

    def _extract_framework_details(self):
        """Extract detailed framework information from transcripts."""
        frameworks = defaultdict(list)

        for transcript in self.transcripts:
            text = transcript.get("full_text", "").lower()
            title = transcript.get("title", "")

            # Look for percentage mentions near key indicators
            for framework, keywords in INDICATORS.items():
                for kw in keywords:
                    if kw in text:
                        # Find sentences containing the keyword
                        sentences = re.split(r'[.!?]', text)
                        for sent in sentences:
                            if kw in sent and len(sent.strip()) > 20:
                                # Look for numbers in the sentence
                                numbers = re.findall(r'\d+(?:\.\d+)?(?:\s*%)?', sent)
                                if numbers:
                                    frameworks[framework].append({
                                        "title": title,
                                        "context": sent.strip()[:200],
                                        "numbers": numbers[:5],
                                    })

        # Deduplicate and limit
        result = {}
        for fw, examples in frameworks.items():
            result[fw] = examples[:10]  # Top 10 examples per framework

        return result

    def _extract_price_mentions(self):
        """Extract price mentions and targets from transcripts."""
        price_mentions = []

        for transcript in self.transcripts:
            text = transcript.get("full_text", "")
            title = transcript.get("title", "")

            # Find dollar amounts
            prices = re.findall(
                r'\$[\d,]+(?:\.\d+)?(?:\s*(?:thousand|k|million|m|billion|b))?',
                text, re.IGNORECASE
            )

            if prices:
                price_mentions.append({
                    "title": title,
                    "prices_mentioned": list(set(prices))[:10],
                })

        return price_mentions[:30]

    def _extract_predictions(self):
        """Extract prediction-like statements from transcripts."""
        prediction_patterns = [
            r'(?:i think|i believe|likely|probably|expect|anticipate|predict)[\w\s,]+(?:going to|will|should|could|might)[\w\s,]+',
            r'(?:the most likely|historically|based on)[\w\s,]+',
        ]

        predictions = []
        for transcript in self.transcripts:
            text = transcript.get("full_text", "").lower()
            title = transcript.get("title", "")

            for pattern in prediction_patterns:
                matches = re.findall(pattern, text)
                for match in matches[:3]:
                    clean = match.strip()
                    if len(clean) > 30:
                        predictions.append({
                            "title": title,
                            "statement": clean[:200],
                        })

        return predictions[:50]

    def save_results(self):
        """Save analysis results."""
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # Save full analysis
        with open(os.path.join(OUTPUT_DIR, "transcript_analysis.json"), "w") as f:
            json.dump(self.analysis_results, f, indent=2)

        # Save knowledge base update
        self._update_knowledge_base()

        # Save latest insights for the app
        self._save_latest_insights()

        print(f"Analysis saved to {OUTPUT_DIR}/")

    def _update_knowledge_base(self):
        """Update the knowledge base with transcript-derived insights."""
        kb_path = os.path.join(OUTPUT_DIR, "knowledge_base.json")

        # Load existing or create new
        if os.path.exists(kb_path):
            with open(kb_path, "r") as f:
                kb = json.load(f)
        else:
            kb = {}

        # Update with analysis results
        kb["last_updated"] = datetime.now().isoformat()
        kb["transcripts_analyzed"] = self.analysis_results.get("total_transcripts", 0)
        kb["total_words_processed"] = self.analysis_results.get("total_words", 0)
        kb["indicator_frequency"] = self.analysis_results.get("indicator_frequency", {})
        kb["asset_focus"] = self.analysis_results.get("asset_focus", {})
        kb["key_phrases"] = self.analysis_results.get("key_phrases", {})
        kb["sentiment_summary"] = self.analysis_results.get("sentiment_analysis", {}).get("overall", {})

        with open(kb_path, "w") as f:
            json.dump(kb, f, indent=2)

    def _save_latest_insights(self):
        """Save insights formatted for the dashboard."""
        insights = {
            "generated_at": datetime.now().isoformat(),
            "transcript_stats": {
                "total_transcripts": len(self.transcripts),
                "total_words": sum(t.get("word_count", 0) for t in self.transcripts),
                "estimated_hours": sum(t.get("word_count", 0) for t in self.transcripts) / 150 / 60,
            },
            "key_themes": [
                "Logarithmic regression provides fair value framework for Bitcoin",
                "4-year halving cycle is the primary market driver",
                "Bitcoin dominance rises in bear markets, falls in bull markets",
                "Bull Market Support Band (20W SMA + 21W EMA) defines trend",
                "200-week SMA crossing prior ATH signals cycle top",
                "Business cycles end with oil spikes and recessions",
                "Midterm years (2 years post-halving) historically weakest for BTC",
                "Post-halving years historically strongest for BTC",
                "DCA into fear, take profits into euphoria",
                "Macro conditions (DXY, rates, oil) override short-term technicals",
                "Gold tends to outperform BTC in midterm/risk-off years",
                "ETH/BTC ratio tends to decline when BTC dominance rises",
            ],
            "most_discussed_indicators": list(
                self.analysis_results.get("indicator_frequency", {}).keys()
            )[:10],
            "latest_video": self.transcripts[0].get("title", "") if self.transcripts else "",
        }

        with open(os.path.join(OUTPUT_DIR, "latest_insights.json"), "w") as f:
            json.dump(insights, f, indent=2)


def main():
    analyzer = TranscriptAnalyzer()
    analyzer.load_transcripts()

    if not analyzer.transcripts:
        print("No transcripts to analyze!")
        return

    print("\nAnalyzing transcripts...")
    results = analyzer.analyze_all()

    print(f"\n=== Analysis Results ===")
    print(f"Total transcripts: {results['total_transcripts']}")
    print(f"Total words: {results['total_words']:,}")
    print(f"\nTop indicators mentioned:")
    for ind, count in list(results['indicator_frequency'].items())[:10]:
        print(f"  {ind}: {count}")
    print(f"\nAsset focus:")
    for asset, count in results['asset_focus'].items():
        print(f"  {asset}: {count}")
    print(f"\nSentiment overview:")
    for sent, count in results['sentiment_analysis']['overall'].items():
        print(f"  {sent}: {count}")

    analyzer.save_results()
    print("\nDone! Results saved.")

if __name__ == "__main__":
    main()
