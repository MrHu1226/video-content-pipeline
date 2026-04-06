# Platform-Specific Download Workarounds

## X / Twitter

**Common issues:**
- Direct downloads frequently stall or are extremely slow
- No embedded subtitles — must rely on local whisper transcription
- Video URLs are ephemeral HLS streams

**Workaround:**
1. Attempt normal `yt-dlp` download with a 120s timeout
2. If stalled, extract HLS URL: `yt-dlp --get-url <URL>`
3. Remux with ffmpeg: `ffmpeg -nostdin -y -i <hls_url> -c copy source.mp4`
4. If video and audio are separate streams (two URLs returned), use two `-i` inputs

**Cookies:** Some tweets require authentication. Use `yt-dlp --cookies-from-browser chrome`
if the video is behind a login wall.

## YouTube

**Common issues:**
- Generally reliable downloads
- May have auto-generated captions (often decent quality)
- Age-restricted videos need cookies

**Workaround:**
- Prefer auto-captions when available: `yt-dlp --write-auto-sub --sub-lang zh,en <URL>`
- Use auto-captions over whisper transcription when quality is sufficient
- For age-restricted: `yt-dlp --cookies-from-browser chrome <URL>`

## Bilibili

**Common issues:**
- Requires specific extractor in yt-dlp
- Video and audio streams are often separate (DASH)

**Workaround:**
- Use default yt-dlp merge: `yt-dlp --merge-output-format mp4 <URL>`
- For members-only: provide cookies via `--cookies-from-browser chrome`

## General Tips

- Always check available formats first: `yt-dlp --list-formats <URL>`
- Prefer mp4 container for maximum compatibility
- Add `--no-playlist` to avoid downloading entire playlists by accident
- Use `--print-json --skip-download` to inspect metadata before committing to download
