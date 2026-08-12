#!/usr/bin/env python3
"""Fetch a YouTube transcript as clean plain text.

Usage: fetch_transcript.py <youtube-url-or-video-id> [--languages en de ...]

Accepts a full URL (watch?v=, youtu.be/, /live/, /shorts/, /embed/, with any
extra query params like &t=16s) or a bare 11-char video ID. Prints a one-line
metadata header (video id, duration, word count) followed by the transcript
text to stdout. On failure, prints a diagnostic to stderr and exits non-zero.
"""
import re
import sys

ID_RE = re.compile(r"^[0-9A-Za-z_-]{11}$")


def extract_id(s: str) -> str:
    s = s.strip()
    if ID_RE.match(s):
        return s
    # Try common URL shapes.
    m = re.search(r"(?:v=|/(?:shorts|embed|live)/|youtu\.be/)([0-9A-Za-z_-]{11})", s)
    if m:
        return m.group(1)
    raise SystemExit(f"Could not extract a video ID from: {s!r}")


def main() -> int:
    args = sys.argv[1:]
    if not args:
        raise SystemExit("usage: fetch_transcript.py <url-or-id> [--languages en ...]")

    langs = ["en"]
    if "--languages" in args:
        i = args.index("--languages")
        langs = args[i + 1:] or ["en"]
        args = args[:i]
    if not args:
        raise SystemExit("usage: fetch_transcript.py <url-or-id> [--languages en ...]")

    vid = extract_id(args[0])

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        raise SystemExit(
            "youtube_transcript_api not installed. Install with: "
            "pip install --user youtube-transcript-api"
        )

    api = YouTubeTranscriptApi()
    try:
        # Newer API: instance .fetch(); supports language preference list.
        try:
            fetched = api.fetch(vid, languages=langs)
        except TypeError:
            fetched = api.fetch(vid)
        snippets = list(fetched)
        text = " ".join(s.text.replace("\n", " ") for s in snippets)
        last = snippets[-1].start if snippets else 0
    except Exception as e:  # noqa: BLE001 - surface the real reason to the agent
        raise SystemExit(f"Failed to fetch transcript for {vid}: {type(e).__name__}: {e}")

    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise SystemExit(f"Transcript for {vid} was empty.")

    print(f"# video_id={vid} duration_min={round(last / 60, 1)} words={len(text.split())}")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
