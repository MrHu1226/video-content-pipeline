#!/usr/bin/env python3
"""Download a video from any yt-dlp-supported source with automatic HLS fallback.

Usage:
    python download_video.py <URL> <output_dir>
    python download_video.py <URL> <output_dir> --timeout 180
    python download_video.py --help
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path


def check_dependencies() -> None:
    """Verify required tools are installed."""
    missing = []
    for tool, install_hint in [
        ("yt-dlp", "pip install yt-dlp"),
        ("ffmpeg", "https://ffmpeg.org/download.html"),
    ]:
        if not shutil.which(tool):
            missing.append(f"  - {tool}  →  {install_hint}")
    if missing:
        print("✗ Missing required tools:\n" + "\n".join(missing))
        sys.exit(1)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"▶ {' '.join(cmd)}")
    return subprocess.run(cmd, check=True, **kwargs)


def _has_progress_files(output: Path) -> bool:
    """Check if yt-dlp has created any progress files (.part, .ytdl, temp files)."""
    parent = output.parent
    stem = output.stem
    for f in parent.iterdir():
        if f.name.startswith(stem) and f.name != output.name:
            return True
    return False


def download_normal(url: str, output: Path, timeout_seconds: int = 120) -> bool:
    """Try a standard yt-dlp download. Return True on success."""
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", str(output),
        url,
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        start = time.time()
        last_progress_time = start
        for line in proc.stdout:
            print(line, end="")
            now = time.time()
            # Reset timer whenever we see download progress
            if "%" in line or "ETA" in line or "Downloading" in line:
                last_progress_time = now
            stall_duration = now - last_progress_time
            if stall_duration > timeout_seconds and not output.exists():
                print(
                    f"\n⚠ Download stalled (no progress for {timeout_seconds}s). "
                    "Trying HLS fallback..."
                )
                proc.terminate()
                proc.wait(timeout=5)
                return False
        proc.wait()
        return proc.returncode == 0 and output.exists()
    except Exception as e:
        print(f"⚠ Normal download failed: {e}")
        return False


def download_hls_fallback(url: str, output: Path) -> bool:
    """Extract direct stream URLs via yt-dlp metadata and remux with ffmpeg.

    Uses yt-dlp -j to inspect format metadata and identify video vs audio
    streams, rather than blindly assuming URL order from --get-url.
    """
    import json as _json

    print("▶ Fetching stream metadata with yt-dlp -j ...")
    result = subprocess.run(
        ["yt-dlp", "-j", url],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"✗ Failed to get metadata: {result.stderr}")
        return False

    try:
        info = _json.loads(result.stdout)
    except _json.JSONDecodeError:
        print("✗ Failed to parse yt-dlp metadata")
        return False

    # If there's a direct URL (single stream), use it
    direct_url = info.get("url")
    if direct_url:
        cmd = [
            "ffmpeg", "-nostdin", "-y",
            "-i", direct_url,
            "-c", "copy", "-movflags", "+faststart",
            str(output),
        ]
        run(cmd)
        return output.exists()

    # Otherwise, look for the selected video and audio format URLs
    formats = info.get("requested_formats") or []
    video_url = None
    audio_url = None
    for fmt in formats:
        if fmt.get("vcodec", "none") != "none":
            video_url = fmt.get("url")
        elif fmt.get("acodec", "none") != "none":
            audio_url = fmt.get("url")

    if not video_url and not audio_url:
        # Last resort: fall back to --get-url
        print("▶ Metadata had no stream URLs, falling back to --get-url ...")
        get_url_result = subprocess.run(
            ["yt-dlp", "--get-url", url],
            capture_output=True, text=True,
        )
        urls = [u.strip() for u in get_url_result.stdout.strip().split("\n") if u.strip()]
        if not urls:
            print("✗ No URLs returned")
            return False
        video_url = urls[0]
        audio_url = urls[1] if len(urls) >= 2 else None

    cmd = ["ffmpeg", "-nostdin", "-y"]
    if video_url:
        cmd.extend(["-i", video_url])
    if audio_url:
        cmd.extend(["-i", audio_url])
    cmd.extend(["-c", "copy", "-movflags", "+faststart", str(output)])

    run(cmd)
    return output.exists()


def main():
    parser = argparse.ArgumentParser(
        description="Download a video from any yt-dlp-supported source with automatic HLS fallback.",
    )
    parser.add_argument("url", help="Video URL (X, YouTube, Bilibili, etc.)")
    parser.add_argument("output_dir", help="Directory to save source.mp4")
    parser.add_argument(
        "--timeout", type=int, default=120,
        help="Seconds to wait before falling back to HLS extraction (default: 120)",
    )
    args = parser.parse_args()

    check_dependencies()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "source.mp4"

    if output.exists():
        print(f"✓ {output} already exists, skipping download")
        return

    if download_normal(args.url, output, args.timeout):
        print(f"✓ Downloaded to {output}")
    elif download_hls_fallback(args.url, output):
        print(f"✓ Downloaded via HLS fallback to {output}")
    else:
        print("✗ All download methods failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
