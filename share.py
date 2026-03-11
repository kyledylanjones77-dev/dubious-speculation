"""
Share CowenIntel - Make the app accessible to others.

Options:
  1. Local Network: Share on your WiFi (anyone on same network can access)
  2. Ngrok Tunnel: Share publicly via a URL (requires ngrok installed)
  3. Cloud Deploy: Instructions for deploying to Render/Railway

Usage:
  python share.py          # Start on local network (default)
  python share.py --ngrok  # Start with ngrok tunnel
"""
import subprocess
import socket
import sys
import os
import threading

def get_local_ip():
    """Get the machine's local network IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def start_local_network():
    """Start the app accessible on local network."""
    local_ip = get_local_ip()
    port = 5000

    print("\n" + "=" * 60)
    print("  COWEN INTELLIGENCE - SHARING ON LOCAL NETWORK")
    print("=" * 60)
    print(f"\n  Your app is available at:")
    print(f"  http://{local_ip}:{port}")
    print(f"\n  Share this URL with anyone on your WiFi network!")
    print(f"  (e.g. text this to your mom)")
    print(f"\n  Press Ctrl+C to stop sharing.")
    print("=" * 60 + "\n")

    # Import and run Flask on all interfaces
    from app import app
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def start_ngrok():
    """Start with ngrok tunnel for public access."""
    try:
        # Check if ngrok is installed
        subprocess.run(["ngrok", "version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("\nngrok is not installed. Install it:")
        print("  1. Download from https://ngrok.com/download")
        print("  2. Or: pip install pyngrok")
        print("\nAlternatively, use local network sharing: python share.py")
        return

    # Start Flask in background
    from app import app
    flask_thread = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False),
        daemon=True
    )
    flask_thread.start()

    print("\n" + "=" * 60)
    print("  COWEN INTELLIGENCE - NGROK TUNNEL")
    print("=" * 60)
    print("  Starting ngrok tunnel...")
    print("  The public URL will appear below.")
    print("  Share it with anyone!")
    print("=" * 60 + "\n")

    # Start ngrok
    subprocess.run(["ngrok", "http", "5000"])

if __name__ == "__main__":
    if "--ngrok" in sys.argv:
        start_ngrok()
    else:
        start_local_network()
