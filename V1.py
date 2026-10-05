#!/usr/bin/env python3
"""
Handwritten-to-text converter using Google's Gemini API (free tier).

Setup:
    pip install google-genai pillow
    # Get a free key at https://aistudio.google.com/apikey
    export GEMINI_API_KEY="your-key"      # Windows: set GEMINI_API_KEY=your-key

Usage:
    python handwriting_to_text.py note.jpg
    python handwriting_to_text.py page1.png page2.png -o output.txt
    python handwriting_to_text.py scans/                 # whole folder
    python handwriting_to_text.py note.jpg --markdown    # keep lists/headings
    python handwriting_to_text.py doc.pdf                # PDFs work too
"""

import argparse
import mimetypes
import os
import sys
import time
from pathlib import Path

from google import genai
from google.genai import types

# "gemini-flash-latest" always points at the current Flash model, so the
# script keeps working when Google retires specific versions.
# Override with --model or the GEMINI_MODEL env var.
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

SUPPORTED = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".pdf"}


PROMPT_PLAIN = (
    "You are doing OCR on the attached image. Read only the characters that "
    "are visibly written in this image and type them out as you see them, "
    "line by line. Do not complete, continue or recall text from memory. "
    "If a word is illegible, write [illegible]; if unsure, add [?]. "
    "Output only the transcription."
)


PROMPT_MARKDOWN = (
    PROMPT_PLAIN + " Format the result as Markdown, preserving headings, bullet lists, "
    "numbered lists, underlines/emphasis, and simple tables where present."
)


def collect_files(paths):
    files = []
    for p in map(Path, paths):
        if p.is_dir():
            files += sorted(f for f in p.iterdir() if f.suffix.lower() in SUPPORTED)
        elif p.suffix.lower() in SUPPORTED:
            files.append(p)
        else:
            print(f"Skipping unsupported file: {p}", file=sys.stderr)
    return files


def transcribe(client, path, model, prompt, retries=4):
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    if path.suffix.lower() in {".heic", ".heif"}:
        mime = f"image/{path.suffix.lower().lstrip('.')}"
    part = types.Part.from_bytes(data=path.read_bytes(), mime_type=mime)

    for attempt in range(retries):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[part, prompt],
                config=types.GenerateContentConfig(temperature=0.7),
            )
            text = (resp.text or "").strip()
            if not text:
                cand = resp.candidates[0] if resp.candidates else None
                print("  Empty response. Details:", file=sys.stderr)
                print(
                    f"  finish_reason : {cand.finish_reason if cand else 'no candidates'}",
                    file=sys.stderr,
                )
                print(f"  prompt_feedback: {resp.prompt_feedback}", file=sys.stderr)
                print(f"  usage         : {resp.usage_metadata}", file=sys.stderr)
                if cand and cand.safety_ratings:
                    print(f"  safety        : {cand.safety_ratings}", file=sys.stderr)
            return text
        except Exception as e:  # free tier returns 429 when rate limited
            msg = str(e)
            retryable = "429" in msg or "RESOURCE_EXHAUSTED" in msg or "503" in msg
            if retryable and attempt < retries - 1:
                wait = 2**attempt * 5
                print(f"  Rate limited, retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                raise


def main():
    ap = argparse.ArgumentParser(description="Convert handwriting images/PDFs to text.")
    ap.add_argument("inputs", nargs="+", help="Image/PDF files or folders")
    ap.add_argument("-o", "--output", help="Write result to this file")
    ap.add_argument(
        "--markdown", action="store_true", help="Preserve formatting as Markdown"
    )
    ap.add_argument(
        "--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})"
    )
    args = ap.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        sys.exit(
            "Set GEMINI_API_KEY first (free key: https://aistudio.google.com/apikey)"
        )

    files = collect_files(args.inputs)
    if not files:
        sys.exit("No supported files found.")

    client = genai.Client(api_key=api_key)
    prompt = PROMPT_MARKDOWN if args.markdown else PROMPT_PLAIN

    results = []
    for i, f in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {f.name}", file=sys.stderr)
        try:
            text = transcribe(client, f, args.model, prompt)
        except Exception as e:
            text = f"[ERROR: {e}]"
        results.append((f, text))
        if i < len(files):
            time.sleep(4)  # stay under free-tier requests-per-minute limits

    if len(results) == 1:
        output = results[0][1]
    else:
        output = "\n\n".join(f"===== {f.name} =====\n{t}" for f, t in results)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Saved to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
