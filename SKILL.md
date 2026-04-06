---
name: x-video-content-pipeline
description: >
  This skill should be used when the user shares a video URL (X/Twitter, YouTube,
  or any yt-dlp-supported source) and wants to download the video, split it into
  topic-based clips, transcribe and summarize content with timestamps, or produce
  Chinese content assets (WeChat articles, Xiaohongshu posts). Trigger phrases
  include "download this video", "clip this video", "summarize the video",
  "write a WeChat article from this", "turn this into Xiaohongshu content",
  "处理这个X链接", "按上次流程做", "下载这个视频并总结", "剪成高光",
  or any request combining a video URL with content extraction or repurposing.
---

# Video Content Pipeline

Turn long-form videos into structured clips, timestamped summaries, and
Chinese-language content assets for learning and platform sharing.

## Prerequisites

Verify before starting — install into a local `.venv_video` if missing:

| Tool      | Purpose                   | Install fallback             |
|-----------|---------------------------|------------------------------|
| `yt-dlp`  | Video download & metadata | `pip install yt-dlp`         |
| `ffmpeg`  | Clip cutting, audio extraction | Require system install  |
| `whisper` | Local transcription       | `pip install openai-whisper` |

## Workspace Layout

Create `video_<source>_<id>/` (e.g., `video_x_2040056891280355449/`).
See `assets/clip_plan_template.csv` for the clip index format.

```
video_<source>_<id>/
├── source.mp4
├── transcripts/          # Per-chunk whisper JSON
├── clips/                # Topic-based segments
├── clip_plan.csv
├── content_summary.md
├── wechat_article.md
└── xiaohongshu_posts.md
```

## Core Workflow

### 1. Download

Run `scripts/download_video.py <URL> <output_dir>`.
Handles yt-dlp download with automatic HLS fallback for slow sources.

### 2. Transcribe

Run `scripts/chunk_and_transcribe.py <video_path> <output_dir>`.
Extracts mono 16kHz audio, splits into ~10-min chunks, transcribes in parallel.

### 3. Clip by Topic

Split the video by **content themes**, not equal duration. Each clip = one
coherent idea, argument, or example.

1. Analyze the full transcript to identify topic boundaries
2. Write `clip_plan.csv` (see `assets/clip_plan_template.csv`)
3. Run `scripts/bulk_encode_clips.py <video_path> <clip_plan.csv> <clips_dir>`

Clip naming: `NN_short_topic_slug.mp4` (e.g., `03_market_timing.mp4`)

### 4. Generate Content

Three output formats — produce only what the user requests:

- **content_summary.md** — timestamped summary organized by topic sections.
  See `references/content_templates.md` for structure guide.
- **wechat_article.md** — polished long-form Chinese article.
  See `references/content_templates.md` for writing guidelines.
- **xiaohongshu_posts.md** — 3–5 short-form posts with hooks and tags.
  See `references/content_templates.md` for format spec.

## Key Constraints

- If the request is ambiguous, default to download + timestamped summary (safe baseline)
- When transcript quality is imperfect, focus on topic flow over verbatim quotes
- For platform-specific download issues, consult `references/platform_workarounds.md`
- For ffmpeg command patterns, consult `references/ffmpeg_patterns.md`
