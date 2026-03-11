"""
Fetch all video IDs from Benjamin Cowen's YouTube channel.
Uses youtube-transcript-api's list functionality and YouTube RSS/scraping.
"""
import json
import re
import urllib.request
import urllib.parse
import time

CHANNEL_ID = "UCRvqjQPSeaWn-uEx-w0XOIg"  # Into the Cryptoverse

def get_videos_from_rss(channel_id):
    """Get recent videos from RSS feed."""
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        data = resp.read().decode("utf-8")

    video_ids = re.findall(r'<yt:videoId>([^<]+)</yt:videoId>', data)
    titles = re.findall(r'<media:title>([^<]+)</media:title>', data)

    videos = []
    for vid, title in zip(video_ids, titles):
        videos.append({"id": vid, "title": title})
    return videos

def get_videos_from_playlist(upload_playlist_id, api_key=None):
    """
    Get all videos from the channel's uploads playlist.
    Uses YouTube's browse endpoint without API key.
    """
    # Convert channel ID to uploads playlist ID
    # UCRvqjQPSeaWn-uEx-w0XOIg -> UURvqjQPSeaWn-uEx-w0XOIg
    playlist_id = upload_playlist_id

    videos = []
    page_token = ""

    while True:
        url = f"https://www.youtube.com/playlist?list={playlist_id}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        })

        try:
            with urllib.request.urlopen(req) as resp:
                html = resp.read().decode("utf-8")
        except Exception as e:
            print(f"Error fetching playlist: {e}")
            break

        # Extract video IDs and titles from the page
        # Look for videoId patterns in the JSON data embedded in HTML
        video_pattern = r'"videoId":"([a-zA-Z0-9_-]{11})"'
        title_pattern = r'"title":\{"runs":\[\{"text":"([^"]+)"\}\]'

        found_ids = re.findall(video_pattern, html)
        found_titles = re.findall(title_pattern, html)

        # Deduplicate
        seen = set()
        for vid in found_ids:
            if vid not in seen:
                seen.add(vid)
                videos.append({"id": vid, "title": ""})

        break  # Single page for now

    return videos

def get_all_video_ids_via_search(channel_name="intothecryptoverse"):
    """
    Scrape video IDs from YouTube channel page.
    """
    url = f"https://www.youtube.com/@{channel_name}/videos"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    })

    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode("utf-8")

    # Extract ytInitialData JSON
    match = re.search(r'var ytInitialData = ({.*?});</script>', html)
    if not match:
        match = re.search(r'ytInitialData\s*=\s*({.*?});</script>', html)

    if match:
        try:
            data = json.loads(match.group(1))
            # Save for debugging
            with open("data/yt_initial_data.json", "w") as f:
                json.dump(data, f)

            # Extract video IDs from the JSON structure
            videos = extract_videos_from_initial_data(data)
            return videos
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")

    # Fallback: regex for video IDs
    video_ids = list(set(re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)))
    return [{"id": vid, "title": ""} for vid in video_ids]

def extract_videos_from_initial_data(data):
    """Recursively extract video info from ytInitialData."""
    videos = []
    seen = set()

    def walk(obj):
        if isinstance(obj, dict):
            if "videoId" in obj and "title" in obj:
                vid = obj["videoId"]
                if vid not in seen:
                    seen.add(vid)
                    title = ""
                    if isinstance(obj["title"], dict):
                        runs = obj["title"].get("runs", [])
                        if runs:
                            title = runs[0].get("text", "")
                        elif "simpleText" in obj["title"]:
                            title = obj["title"]["simpleText"]
                    elif isinstance(obj["title"], str):
                        title = obj["title"]
                    videos.append({"id": vid, "title": title})
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return videos

def get_uploads_playlist_id(channel_id):
    """Convert channel ID to uploads playlist ID."""
    # Replace UC with UU
    return "UU" + channel_id[2:]

if __name__ == "__main__":
    print("=== Fetching Benjamin Cowen's video catalog ===\n")

    # Method 1: RSS feed (recent 15)
    print("Method 1: RSS Feed...")
    rss_videos = get_videos_from_rss(CHANNEL_ID)
    print(f"  Found {len(rss_videos)} videos from RSS")

    # Method 2: Channel page scraping
    print("\nMethod 2: Channel page...")
    page_videos = get_all_video_ids_via_search("intothecryptoverse")
    print(f"  Found {len(page_videos)} videos from channel page")

    # Method 3: Uploads playlist
    uploads_pl = get_uploads_playlist_id(CHANNEL_ID)
    print(f"\nMethod 3: Uploads playlist ({uploads_pl})...")
    playlist_videos = get_videos_from_playlist(uploads_pl)
    print(f"  Found {len(playlist_videos)} videos from playlist")

    # Merge all, deduplicate
    all_videos = {}
    for v in rss_videos + page_videos + playlist_videos:
        if v["id"] not in all_videos or (v["title"] and not all_videos[v["id"]]["title"]):
            all_videos[v["id"]] = v

    video_list = list(all_videos.values())
    print(f"\n=== Total unique videos found: {len(video_list)} ===")

    # Save
    with open("data/video_catalog.json", "w") as f:
        json.dump(video_list, f, indent=2)

    print(f"Saved to data/video_catalog.json")

    # Show sample
    for v in video_list[:10]:
        print(f"  {v['id']}: {v['title']}")
