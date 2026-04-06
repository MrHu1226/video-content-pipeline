#!/usr/bin/env python3
"""Batch-cut clips from a source video based on a clip plan CSV.

Usage:
    python bulk_encode_clips.py <video_path> <clip_plan.csv> <clips_dir>
    python bulk_encode_clips.py <video_path> <clip_plan.csv> <clips_dir> --crf 18
    python bulk_encode_clips.py --help

clip_plan.csv format:
    index,start,end,title,description
    1,00:00:30,00:05:12,opening_thesis,Introduction and main argument
    2,00:05:12,00:12:45,case_study_apple,Apple's growth strategy breakdown
"""

import argparse
import csv
import re
import shutil
import subprocess
import sys
from pathlib import Path


def check_dependencies() -> None:
    """Verify required tools are installed."""
    if not shutil.which("ffmpeg"):
        print("✗ ffmpeg not found. Install it from https://ffmpeg.org/download.html")
        sys.exit(1)


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    print(f"▶ {' '.join(cmd)}")
    return subprocess.run(cmd, check=True)


def slugify_title(title: str, fallback: str) -> str:
    """Convert a free-form title into a filesystem-safe slug."""
    cleaned = title.strip().lower()
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._")
    return cleaned or fallback


def encode_clip(
    video_path: Path,
    output_path: Path,
    start: str,
    end: str,
    crf: int,
    preset: str,
) -> None:
    """Cut and re-encode a single clip to H.264 + AAC."""
    if output_path.exists():
        print(f"  ✓ {output_path.name} already exists, skipping")
        return

    run([
        "ffmpeg", "-nostdin", "-y",
        "-i", str(video_path),
        "-ss", start, "-to", end,
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path),
    ])


def main():
    parser = argparse.ArgumentParser(
        description="Batch-cut clips from a source video based on a clip plan CSV.",
    )
    parser.add_argument("video_path", help="Path to source video file")
    parser.add_argument("clip_plan", help="Path to clip_plan.csv")
    parser.add_argument("clips_dir", help="Output directory for clip files")
    parser.add_argument(
        "--crf", type=int, default=22,
        help="H.264 CRF quality (lower = better, 18-28 typical, default: 22)",
    )
    parser.add_argument(
        "--preset", default="medium",
        choices=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"],
        help="H.264 encoding preset (default: medium). Faster = larger file.",
    )
    args = parser.parse_args()

    check_dependencies()

    video_path = Path(args.video_path)
    clip_plan_path = Path(args.clip_plan)
    clips_dir = Path(args.clips_dir)
    clips_dir.mkdir(parents=True, exist_ok=True)

    if not video_path.exists():
        print(f"✗ Video not found: {video_path}")
        sys.exit(1)

    if not clip_plan_path.exists():
        print(f"✗ Clip plan not found: {clip_plan_path}")
        sys.exit(1)

    with open(clip_plan_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("✗ clip_plan.csv is empty")
        sys.exit(1)

    required_cols = {"index", "start", "end", "title"}
    actual_cols = set(rows[0].keys())
    missing_cols = required_cols - actual_cols
    if missing_cols:
        print(f"✗ clip_plan.csv missing required columns: {', '.join(missing_cols)}")
        print(f"  Expected: index,start,end,title,description")
        sys.exit(1)

    print(f"▶ Encoding {len(rows)} clips from {video_path.name} (crf={args.crf}, preset={args.preset}) ...")

    failed = []
    for row in rows:
        idx = int(row["index"])
        title = slugify_title(row["title"], f"clip_{idx:02d}")
        output_path = clips_dir / f"{idx:02d}_{title}.mp4"

        try:
            encode_clip(video_path, output_path, row["start"].strip(), row["end"].strip(), args.crf, args.preset)
            print(f"  ✓ {output_path.name}")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ {output_path.name} failed: {e}")
            failed.append(output_path.name)

    if failed:
        print(f"\n⚠ {len(failed)} clip(s) failed: {', '.join(failed)}")
        sys.exit(1)
    else:
        print(f"\n✓ All {len(rows)} clips encoded to {clips_dir}/")


if __name__ == "__main__":
    main()
