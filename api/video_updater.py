"""
Video Updater - Checks for new Benjamin Cowen videos and processes transcripts.
Runs on demand or can be scheduled.
"""
import json
import os
import re
import urllib.request
import time
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi

CHANNEL_ID = "UCRvqjQPSeaWn-uEx-w0XOIg"
DATA_DIR = "data"
TRANSCRIPT_DIR = "data/transcripts"
CATALOG_FILE = "data/video_catalog.json"

class VideoUpdater:
    def __init__(self):
        os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
        self.api = YouTubeTranscriptApi()

    def check_for_new_videos(self):
        """Check RSS feed for new videos and fetch their transcripts."""
        # Get latest from RSS
        rss_videos = self._fetch_rss()

        # Load existing catalog
        existing = set()
        if os.path.exists(CATALOG_FILE):
            with open(CATALOG_FILE, "r") as f:
                catalog = json.load(f)
            existing = {v["id"] for v in catalog}
        else:
            catalog = []

        # Find new videos
        new_videos = [v for v in rss_videos if v["id"] not in existing]

        results = {
            "checked_at": datetime.now().isoformat(),
            "total_in_catalog": len(catalog),
            "new_videos_found": len(new_videos),
            "processed": [],
            "failed": [],
        }

        for video in new_videos:
            vid = video["id"]
            title = video["title"]

            try:
                # Fetch transcript
                transcript = self.api.fetch(vid)
                entries = []
                for snippet in transcript.snippets:
                    entries.append({
                        "start": snippet.start,
                        "duration": snippet.duration,
                        "text": snippet.text
                    })

                full_text = " ".join([e["text"] for e in entries])
                result = {
                    "video_id": vid,
                    "title": title,
                    "transcript": entries,
                    "full_text": full_text,
                    "word_count": len(full_text.split()),
                    "fetched_at": datetime.now().isoformat(),
                }

                filepath = os.path.join(TRANSCRIPT_DIR, f"{vid}.json")
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=1)

                # Add to catalog
                catalog.append(video)
                results["processed"].append({"id": vid, "title": title})

                time.sleep(1)  # Rate limiting

            except Exception as e:
                results["failed"].append({"id": vid, "title": title, "error": str(e)})

        # Save updated catalog
        with open(CATALOG_FILE, "w") as f:
            json.dump(catalog, f, indent=2)

        return results

    def _fetch_rss(self):
        """Fetch latest videos from RSS feed."""
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

        try:
            with urllib.request.urlopen(req) as resp:
                data = resp.read().decode("utf-8")

            video_ids = re.findall(r'<yt:videoId>([^<]+)</yt:videoId>', data)
            titles = re.findall(r'<media:title>([^<]+)</media:title>', data)

            videos = []
            for vid, title in zip(video_ids, titles):
                videos.append({"id": vid, "title": title})
            return videos
        except Exception as e:
            print(f"RSS fetch error: {e}")
            return []

    def get_transcript_stats(self):
        """Get stats about downloaded transcripts."""
        if not os.path.exists(TRANSCRIPT_DIR):
            return {"total": 0}

        files = [f for f in os.listdir(TRANSCRIPT_DIR) if f.endswith(".json")]
        total_words = 0

        for f in files:
            try:
                with open(os.path.join(TRANSCRIPT_DIR, f), "r") as fh:
                    data = json.load(fh)
                total_words += data.get("word_count", 0)
            except:
                pass

        return {
            "total_transcripts": len(files),
            "total_words": total_words,
            "estimated_hours": total_words / 150 / 60,  # ~150 words per minute
        }
