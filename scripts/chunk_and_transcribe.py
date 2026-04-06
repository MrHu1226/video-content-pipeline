#!/usr/bin/env python3
"""Extract audio from a video, split into chunks, and transcribe with whisper.

Usage:
    python chunk_and_transcribe.py <video_path> <output_dir>
    python chunk_and_transcribe.py <video_path> <output_dir> --model medium --chunk-minutes 5
    python chunk_and_transcribe.py --help
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Whisper is CPU/GPU-heavy. Default to 2 workers to avoid thrashing.
DEFAULT_WORKERS = min(2, os.cpu_count() or 1)


def check_dependencies() -> None:
    """Verify required tools are installed."""
    missing = []
    for tool, install_hint in [
        ("ffmpeg", "https://ffmpeg.org/download.html"),
        ("ffprobe", "Included with ffmpeg — https://ffmpeg.org/download.html"),
        ("whisper", "pip install openai-whisper"),
    ]:
        if not shutil.which(tool):
            missing.append(f"  - {tool}  →  {install_hint}")
    if missing:
        print("✗ Missing required tools:\n" + "\n".join(missing))
        sys.exit(1)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"▶ {' '.join(cmd)}")
    return subprocess.run(cmd, check=True, **kwargs)


def extract_audio(video_path: Path, audio_path: Path) -> None:
    if audio_path.exists():
        print(f"✓ {audio_path} already exists, skipping extraction")
        return
    run([
        "ffmpeg", "-nostdin", "-y",
        "-i", str(video_path),
        "-ac", "1", "-ar", "16000", "-vn",
        str(audio_path),
    ])


def get_duration(audio_path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(audio_path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def split_audio(audio_path: Path, chunks_dir: Path, chunk_duration: int) -> list[Path]:
    chunks_dir.mkdir(parents=True, exist_ok=True)
    duration = get_duration(audio_path)
    chunks = []
    idx = 0
    start = 0.0

    while start < duration:
        idx += 1
        chunk_path = chunks_dir / f"chunk_{idx:03d}.wav"
        if not chunk_path.exists():
            run([
                "ffmpeg", "-nostdin", "-y",
                "-i", str(audio_path),
                "-ss", str(start), "-t", str(chunk_duration),
                "-c", "copy",
                str(chunk_path),
            ])
        chunks.append(chunk_path)
        start += chunk_duration

    print(f"✓ Split into {len(chunks)} chunks")
    return chunks


def transcribe_chunk(chunk_path: Path, output_dir: Path, chunk_offset: float, model: str, language: str | None = None) -> dict:
    """Transcribe a single chunk. Returns the whisper result dict with adjusted timestamps."""
    stem = chunk_path.stem
    json_path = output_dir / f"{stem}.json"

    if json_path.exists():
        print(f"✓ {json_path} already exists, skipping")
        with open(json_path) as f:
            return json.load(f)

    cmd = [
        "whisper", str(chunk_path),
        "--model", model,
        "--output_format", "json",
        "--output_dir", str(output_dir),
    ]
    if language:
        cmd.extend(["--language", language])
    # If --language is omitted, whisper auto-detects
    run(cmd)

    with open(json_path) as f:
        data = json.load(f)

    if "segments" in data:
        for seg in data["segments"]:
            seg["start"] += chunk_offset
            seg["end"] += chunk_offset

    with open(json_path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data


def merge_transcripts(transcript_dir: Path, output_path: Path) -> None:
    """Merge all chunk transcripts into a single plaintext file with timestamps."""
    all_segments = []
    for json_file in sorted(transcript_dir.glob("chunk_*.json")):
        with open(json_file) as f:
            data = json.load(f)
        if "segments" in data:
            all_segments.extend(data["segments"])

    # Also check for audio.json (single-chunk case)
    audio_json = transcript_dir / "audio.json"
    if audio_json.exists():
        with open(audio_json) as f:
            data = json.load(f)
        if "segments" in data:
            all_segments.extend(data["segments"])

    all_segments.sort(key=lambda s: s["start"])

    lines = []
    for seg in all_segments:
        start_m, start_s = divmod(int(seg["start"]), 60)
        end_m, end_s = divmod(int(seg["end"]), 60)
        ts = f"[{start_m:02d}:{start_s:02d} - {end_m:02d}:{end_s:02d}]"
        lines.append(f"{ts} {seg.get('text', '').strip()}")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ Merged transcript written to {output_path} ({len(all_segments)} segments)")


def main():
    parser = argparse.ArgumentParser(
        description="Extract audio, split into chunks, and transcribe with whisper.",
    )
    parser.add_argument("video_path", help="Path to source video file")
    parser.add_argument("output_dir", help="Directory for audio, transcripts, and merged output")
    parser.add_argument(
        "--model", default="base", choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: base). Larger = more accurate but slower.",
    )
    parser.add_argument(
        "--chunk-minutes", type=int, default=10,
        help="Chunk duration in minutes for splitting long audio (default: 10)",
    )
    parser.add_argument(
        "--workers", type=int, default=DEFAULT_WORKERS,
        help=f"Max parallel whisper processes (default: {DEFAULT_WORKERS}). "
             "Whisper is CPU/GPU-heavy; more workers != faster.",
    )
    parser.add_argument(
        "--language", default=None,
        help="Language code for whisper (e.g. zh, en, ja). Omit for auto-detection.",
    )
    args = parser.parse_args()

    check_dependencies()

    video_path = Path(args.video_path)
    if not video_path.exists():
        print(f"✗ Video not found: {video_path}")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    audio_path = output_dir / "audio.wav"
    transcript_dir = output_dir / "transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)

    chunk_duration = args.chunk_minutes * 60

    # Step 1: Extract audio
    extract_audio(video_path, audio_path)

    # Step 2: Split if needed
    duration = get_duration(audio_path)
    if duration <= chunk_duration * 1.2:
        chunks = [audio_path]
        offsets = [0.0]
    else:
        chunks_dir = output_dir / "audio_chunks"
        chunks = split_audio(audio_path, chunks_dir, chunk_duration)
        offsets = [i * chunk_duration for i in range(len(chunks))]

    # Step 3: Transcribe (limited concurrency to avoid thrashing)
    print(f"▶ Transcribing {len(chunks)} chunk(s) with model '{args.model}', workers={args.workers} ...")
    failed_chunks = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(transcribe_chunk, chunk, transcript_dir, offset, args.model, args.language): chunk
            for chunk, offset in zip(chunks, offsets)
        }
        for future in as_completed(futures):
            chunk = futures[future]
            try:
                future.result()
                print(f"  ✓ {chunk.name} done")
            except Exception as e:
                print(f"  ✗ {chunk.name} failed: {e}")
                failed_chunks.append(chunk.name)

    if failed_chunks:
        print(
            "✗ Transcription incomplete; refusing to merge partial results. "
            f"Failed chunks: {', '.join(failed_chunks)}"
        )
        sys.exit(1)

    # Step 4: Merge
    merge_transcripts(transcript_dir, output_dir / "full_transcript.txt")


if __name__ == "__main__":
    main()
