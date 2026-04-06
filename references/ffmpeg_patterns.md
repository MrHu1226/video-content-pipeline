# FFmpeg Command Patterns

Quick reference for common ffmpeg operations in this pipeline.

## Audio Extraction

```bash
# Extract mono 16kHz WAV for whisper
ffmpeg -nostdin -y -i source.mp4 -ac 1 -ar 16000 -vn audio.wav
```

## Audio Splitting

```bash
# Split audio into 10-minute chunks
ffmpeg -nostdin -y -i audio.wav -ss 0 -t 600 -c copy chunk_001.wav
ffmpeg -nostdin -y -i audio.wav -ss 600 -t 600 -c copy chunk_002.wav
```

## Clip Cutting (Re-encode)

```bash
# Cut and re-encode to H.264 + AAC (cross-platform safe)
ffmpeg -nostdin -y \
  -i source.mp4 \
  -ss 00:05:12 -to 00:12:45 \
  -c:v libx264 -preset medium -crf 22 \
  -c:a aac -b:a 128k \
  -movflags +faststart \
  01_topic_name.mp4
```

## Clip Cutting (Stream Copy — faster, less precise)

```bash
# Copy without re-encoding (may have imprecise start/end)
ffmpeg -nostdin -y \
  -i source.mp4 \
  -ss 00:05:12 -to 00:12:45 \
  -c copy \
  01_topic_name.mp4
```

## HLS Remux

```bash
# Single stream
ffmpeg -nostdin -y -i "HLS_URL" -c copy -movflags +faststart source.mp4

# Separate video + audio streams
ffmpeg -nostdin -y \
  -i "VIDEO_HLS_URL" \
  -i "AUDIO_HLS_URL" \
  -c copy -movflags +faststart source.mp4
```

## Get Video Duration

```bash
ffprobe -v quiet -show_entries format=duration -of csv=p=0 source.mp4
```

## Key Flags

| Flag | Purpose |
|------|---------|
| `-nostdin` | Prevent stdin consumption in loops/batch scripts |
| `-y` | Overwrite output without asking |
| `-movflags +faststart` | Move moov atom to front for web streaming |
| `-preset medium` | Balance between encoding speed and compression |
| `-crf 22` | Visual quality (lower = better, 18-28 typical range) |
