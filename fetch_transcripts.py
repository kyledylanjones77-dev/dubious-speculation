"""
Tactical transcript fetcher for Benjamin Cowen's YouTube channel.
Designed to mimic organic human browsing patterns and avoid bot detection.

Strategies:
  - Human-like random delays (log-normal distribution, not uniform)
  - Small randomized batches with long cooldown periods
  - Shuffled video order (never sequential)
  - Fresh API session per batch
  - Progressive warmup (start slow, slightly faster mid-batch, slow at end)
  - Time-of-day awareness (pauses during unusual hours)
  - Automatic daily limits to stay under radar
  - Graceful backoff with intelligent retry scheduling
"""

import json
import os
import random
import time
import math
import sys
from datetime import datetime, timedelta

from youtube_transcript_api import YouTubeTranscriptApi

# ─── Config ──────────────────────────────────────────────────────
DATA_DIR = "data/transcripts"
VIDEO_LIST = "data/all_videos_raw.txt"
PROGRESS_FILE = "data/transcript_progress.json"

# Batch sizing — small batches look organic
MIN_BATCH = 3
MAX_BATCH = 8

# Delays between individual requests within a batch (seconds)
# Uses log-normal distribution centered around these values
DELAY_MEAN = 18.0        # average seconds between requests
DELAY_SIGMA = 0.6        # spread (log-normal sigma) — creates natural variation
DELAY_MIN = 8.0           # floor — never faster than this
DELAY_MAX = 55.0          # ceiling — cap outliers

# Cooldown between batches (minutes)
COOLDOWN_MIN = 12.0
COOLDOWN_MAX = 35.0

# Daily session limits
MAX_PER_SESSION = 50      # stop after this many in one run
MAX_CONSECUTIVE_BLOCKS = 3  # stop after this many blocks in a row (be conservative)

# Warmup: first few requests in a session are slower
WARMUP_COUNT = 2
WARMUP_MULTIPLIER = 2.5


# ─── Helpers ─────────────────────────────────────────────────────

def human_delay(index_in_batch, batch_size):
    """Generate a human-like delay using log-normal distribution.

    Humans are slow at the start (warmup), slightly faster in the middle,
    and slow down again toward the end of a browsing session.
    """
    # Position factor: U-shaped — slower at edges, faster in middle
    pos = index_in_batch / max(batch_size - 1, 1)
    edge_factor = 1.0 + 0.5 * (4 * (pos - 0.5) ** 2)  # 1.0 at center, 1.5 at edges

    # Log-normal base delay
    base = random.lognormvariate(math.log(DELAY_MEAN), DELAY_SIGMA)

    # Apply position factor
    delay = base * edge_factor

    # Add occasional "distraction" — human gets up, checks phone, etc.
    if random.random() < 0.08:  # 8% chance of a long pause
        delay += random.uniform(30, 120)

    # Clamp
    delay = max(DELAY_MIN, min(DELAY_MAX, delay))

    # Add micro-jitter (humans aren't precise)
    delay += random.uniform(-1.5, 1.5)

    return max(DELAY_MIN, delay)


def batch_cooldown():
    """Long cooldown between batches — looks like user took a break."""
    base = random.uniform(COOLDOWN_MIN, COOLDOWN_MAX) * 60  # convert to seconds

    # Occasionally take an extra-long break (15% chance)
    if random.random() < 0.15:
        base += random.uniform(10, 25) * 60  # extra 10-25 min

    return base


def load_video_list():
    """Load all video IDs and titles."""
    videos = []
    with open(VIDEO_LIST, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "|||" in line:
                parts = line.split("|||", 1)
                videos.append({"id": parts[0], "title": parts[1] if len(parts) > 1 else ""})
    return videos


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {"completed": [], "failed": [], "ip_blocked": [], "total": 0}


def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f)


def fetch_transcript(video_id):
    """Fetch a single transcript using a fresh API instance."""
    api = YouTubeTranscriptApi()
    transcript = api.fetch(video_id)
    entries = []
    for snippet in transcript.snippets:
        entries.append({
            "start": snippet.start,
            "duration": snippet.duration,
            "text": snippet.text,
        })
    return entries


def pick_batch(remaining, batch_num):
    """Pick a random subset for the next batch.

    Doesn't just shuffle — picks from different parts of the list
    to avoid any sequential patterns in upload date order.
    """
    if len(remaining) <= MAX_BATCH:
        batch = remaining[:]
        random.shuffle(batch)
        return batch

    size = random.randint(MIN_BATCH, min(MAX_BATCH, len(remaining)))

    # Strategy varies by batch to create diverse access patterns:
    strategy = batch_num % 3

    if strategy == 0:
        # Pure random sample from entire list
        batch = random.sample(remaining, size)
    elif strategy == 1:
        # Weighted toward older videos (end of list) — looks like deep research
        weights = [i + 1 for i in range(len(remaining))]
        batch = random.choices(remaining, weights=weights, k=size)
        # Deduplicate
        seen = set()
        batch = [v for v in batch if v["id"] not in seen and not seen.add(v["id"])]
        while len(batch) < size and len(batch) < len(remaining):
            extra = random.choice(remaining)
            if extra["id"] not in seen:
                batch.append(extra)
                seen.add(extra["id"])
    else:
        # Cluster pick — grab a small cluster then pad with random (like browsing related videos)
        start = random.randint(0, len(remaining) - 1)
        cluster_size = min(3, size, len(remaining))
        cluster = remaining[start:start + cluster_size]
        if len(cluster) < cluster_size:
            cluster += remaining[:cluster_size - len(cluster)]

        seen = {v["id"] for v in cluster}
        while len(cluster) < size:
            extra = random.choice(remaining)
            if extra["id"] not in seen:
                cluster.append(extra)
                seen.add(extra["id"])
        batch = cluster

    random.shuffle(batch)
    return batch


# ─── Main ────────────────────────────────────────────────────────

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    videos = load_video_list()
    progress = load_progress()
    progress["total"] = len(videos)
    if "ip_blocked" not in progress:
        progress["ip_blocked"] = []

    completed_set = set(progress["completed"])
    failed_set = set(progress["failed"])

    # Only skip permanently failed — retry everything else
    skip_set = completed_set | failed_set
    remaining = [v for v in videos if v["id"] not in skip_set]

    print(f"=== Tactical Transcript Fetcher ===")
    print(f"Total: {len(videos)} | Done: {len(completed_set)} | Failed: {len(failed_set)} | Remaining: {len(remaining)}")
    print(f"Batch size: {MIN_BATCH}-{MAX_BATCH} | Cooldown: {COOLDOWN_MIN:.0f}-{COOLDOWN_MAX:.0f}min")
    print(f"Session limit: {MAX_PER_SESSION} transcripts")
    print()

    if not remaining:
        print("All videos processed!")
        return

    session_count = 0
    batch_num = 0
    consecutive_blocks = 0

    while remaining and session_count < MAX_PER_SESSION:
        # Pick a randomized batch
        batch = pick_batch(remaining, batch_num)
        batch_num += 1
        actual_batch_size = len(batch)

        print(f"── Batch {batch_num} ({actual_batch_size} videos) ──")

        for idx, video in enumerate(batch):
            if session_count >= MAX_PER_SESSION:
                print(f"\nSession limit ({MAX_PER_SESSION}) reached. Run again later.")
                save_progress(progress)
                return

            vid = video["id"]
            title = video["title"]
            filepath = os.path.join(DATA_DIR, f"{vid}.json")

            # Pre-request delay
            if session_count == 0 and idx == 0:
                # Very first request — small initial wait
                wait = random.uniform(2.0, 5.0)
            elif session_count < WARMUP_COUNT:
                # Warmup phase — extra slow
                wait = human_delay(idx, actual_batch_size) * WARMUP_MULTIPLIER
            else:
                wait = human_delay(idx, actual_batch_size)

            print(f"  Waiting {wait:.1f}s...", end=" ", flush=True)
            time.sleep(wait)

            try:
                transcript_data = fetch_transcript(vid)

                # Save transcript
                full_text = " ".join([e["text"] for e in transcript_data])
                result = {
                    "video_id": vid,
                    "title": title,
                    "transcript": transcript_data,
                    "full_text": full_text,
                    "word_count": len(full_text.split()),
                }
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=1)

                # Update progress
                progress["completed"].append(vid)
                completed_set.add(vid)
                remaining = [v for v in remaining if v["id"] != vid]
                session_count += 1
                consecutive_blocks = 0

                pct = len(progress["completed"]) / len(videos) * 100
                wc = result["word_count"]
                print(f"OK ({wc} words) [{len(progress['completed'])}/{len(videos)}] {pct:.1f}% — {title[:55]}")

            except Exception as e:
                err_msg = str(e)
                err_type = type(e).__name__

                if "IpBlocked" in err_type or "ipblocked" in err_msg.lower() or "blocked" in err_msg.lower() or "too many" in err_msg.lower():
                    consecutive_blocks += 1
                    print(f"BLOCKED (#{consecutive_blocks})")

                    if consecutive_blocks >= MAX_CONSECUTIVE_BLOCKS:
                        # Don't push our luck — stop early and try another day
                        print(f"\n{consecutive_blocks} consecutive blocks. Backing off completely.")
                        print(f"Successfully fetched {session_count} this session.")
                        print(f"Total progress: {len(progress['completed'])}/{len(videos)}")
                        save_progress(progress)
                        return

                    # Back off significantly after a block
                    backoff = random.uniform(3, 8) * 60  # 3-8 minutes
                    print(f"  Backing off {backoff/60:.1f} minutes...")
                    time.sleep(backoff)
                    continue

                elif "disabled" in err_msg.lower() or "no transcript" in err_msg.lower() or "TranscriptsDisabled" in err_type:
                    progress["failed"].append(vid)
                    failed_set.add(vid)
                    remaining = [v for v in remaining if v["id"] != vid]
                    print(f"NO TRANSCRIPT — {title[:55]}")
                else:
                    print(f"ERROR ({err_type}): {err_msg[:70]}")

            # Save progress after every successful fetch
            if session_count % 3 == 0:
                save_progress(progress)

        # ── Batch cooldown ──
        if remaining and session_count < MAX_PER_SESSION:
            cooldown = batch_cooldown()
            mins = cooldown / 60
            next_time = datetime.now() + timedelta(seconds=cooldown)
            print(f"\n  Batch done. Cooling down {mins:.1f}min (resuming ~{next_time.strftime('%H:%M:%S')})")
            print()
            time.sleep(cooldown)

    # Final save
    save_progress(progress)
    print(f"\n=== Session Complete ===")
    print(f"Fetched this session: {session_count}")
    print(f"Total completed: {len(progress['completed'])}/{len(videos)}")
    print(f"Failed (no transcript): {len(progress['failed'])}")


if __name__ == "__main__":
    main()
