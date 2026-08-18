---
name: youtube-summary
description: >-
  Summarize a YouTube video from its URL or video ID by fetching the transcript
  and producing a TL;DR, a short overview, and bulleted key points. Use when the
  user pastes a YouTube link (youtube.com/watch, youtu.be, /shorts, /live) or a
  video ID and wants a summary, recap, key points, takeaways, notes, or "what is
  this video about". Triggers on phrasings like "summarize this video", "tl;dr
  this talk", "key points from a link", or just a bare YouTube URL when the
  surrounding intent is to digest it. Do NOT use for non-YouTube videos or URLs,
  for downloading audio/video, or when the user explicitly wants only the raw
  verbatim transcript (in that case just fetch it without summarizing).
compatibility: Requires the youtube-transcript-api Python package (pip install --user youtube-transcript-api).
---

# YouTube Summary

Turn a YouTube video into a tight, faithful summary by reading its transcript.

## Workflow

1. **Fetch the transcript** with the bundled script. It accepts a full URL (any
   form, extra params like `&t=16s` are fine) or a bare 11-char video ID:

   ```bash
   python3 scripts/fetch_transcript.py "<url-or-id>"
   ```

   The first line is metadata (`video_id`, `duration_min`, `words`); the rest is
   the transcript text. For a non-English video, add e.g. `--languages es en`.

2. **Read the whole transcript**, then write the summary. For long transcripts
   (many thousands of words) redirect to a temp file and read that, rather than
   piping a wall of text through the shell:

   ```bash
   python3 scripts/fetch_transcript.py "<url-or-id>" > /tmp/yt.txt
   ```

3. **Output the summary in chat** using the format below. Don't save it to a
   file unless asked.

## Output format

Default to three parts, in this order:

- **TL;DR** — 1–3 lines capturing the single most important thing.
- **Summary** — a short overview (1–2 short paragraphs): what the video is,
  who's speaking if relevant, and its through-line.
- **Key points** — a bulleted list of the substantive takeaways. Use sub-bullets
  or short bold lead-ins for structure when the video has distinct sections.

Scale length to the content: a 5-minute clip gets a few bullets; a 40-minute
talk gets more. Don't pad.

## Staying faithful

The whole value is accuracy — a summary the user can trust without watching.

- Ground every claim in the transcript. Don't add facts, figures, or names the
  speaker didn't say, and don't smooth over uncertainty by inventing specifics.
- Transcripts mis-hear proper nouns and numbers. If a name or term looks
  garbled, render your best reading and don't over-assert it.
- Preserve the speaker's actual stance. If they hedge, hedge; if they're
  promoting their own product, say so rather than presenting it as neutral.
- At the end, offer a relevant next step (e.g. save to a file, a one-line TL;DR,
  extract quotes) instead of assuming.

## When transcripts aren't available

If the script exits non-zero, read its stderr message and report it plainly —
common causes are transcripts disabled by the uploader, an age-restricted or
private video, or no track in the requested language. Don't fabricate a summary
from the title or your own knowledge; tell the user the transcript couldn't be
fetched and, if useful, suggest trying `--languages` with another code.
