"""
gemini_audio.py — Audio evaluation via Google Gemini 2.0 Flash.

Uploads an audio file to Gemini and asks it to evaluate the track against
intended style tags, mood, and production quality. Returns structured JSON.

Requires GEMINI_API_KEY in .env.
"""

import json
import os
import re
import sys
from pathlib import Path

from google import genai

BASE_DIR = Path(__file__).parent.parent
GEMINI_MODEL = "gemini-2.5-flash"


def _load_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip()
    print("ERROR: GEMINI_API_KEY not found in environment or .env", file=sys.stderr)
    sys.exit(1)


def evaluate_track(
    audio_path: str,
    tags: str = "",
    mood: str = "",
    title: str = "",
    is_instrumental: bool = True,
    intended_lyrics: str = "",
) -> dict:
    """
    Upload an audio file to Gemini and get a structured evaluation.

    Returns a dict with keys: vocal_contamination, genre_match, mood_match,
    production_quality, artistic_interest, verdict, notes.
    """
    api_key = _load_api_key()
    client = genai.Client(api_key=api_key)

    # Upload the audio file
    # Use pathlib.Path object — the SDK's string path validation chokes on spaces in iCloud paths
    file_path = Path(audio_path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    # Determine mime type
    suffix = file_path.suffix.lower()
    mime_map = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".wav": "audio/wav", ".ogg": "audio/ogg"}
    mime_type = mime_map.get(suffix, "audio/mpeg")

    # Upload using file IO to avoid SDK path-string issues
    with open(file_path, "rb") as f:
        audio_file = client.files.upload(
            file=f,
            config={"mime_type": mime_type},
        )

    # Build the evaluation prompt
    instrumental_check = (
        "1. VOCAL CONTAMINATION: Are any vocals, singing, speech, humming, or voice sounds "
        "audible? This should be a purely instrumental track. Answer yes/no with description."
    ) if is_instrumental else (
        "1. VOCAL QUALITY: Are the vocals clear and intelligible? Do they match the intended "
        "style (check tags for vocal descriptors like 'raspy baritone', 'ethereal soprano', etc.)? "
        "Rate 1-5."
    )

    lyrics_check = ""
    if intended_lyrics and not is_instrumental:
        lyrics_check = (
            f"\n6. LYRIC ACCURACY: The intended lyrics were:\n{intended_lyrics[:500]}\n"
            "Can you make out any of these words/phrases in the generated track? Rate how closely "
            "the sung words match on a scale of 1-5."
        )

    prompt = f"""You are an expert music critic and audio engineer evaluating an AI-generated music track.

TRACK TITLE: {title}
INTENDED STYLE TAGS: {tags}
INTENDED MOOD/CHARACTER: {mood}
TYPE: {"Instrumental" if is_instrumental else "Vocal"}

Listen carefully to this track and evaluate:

{instrumental_check}
2. GENRE MATCH: Does this track match the intended style tags above? Rate 1-5 and explain briefly.
3. MOOD MATCH: Does the emotional character match the intended mood? Rate 1-5 and explain.
4. PRODUCTION QUALITY: Is the audio clean, well-mixed, dynamic? Any artifacts, clipping, abrupt cuts? Rate 1-5.
5. ARTISTIC INTEREST: Is this track musically interesting and non-generic? Does it have distinctive character that would make someone remember it, or does it sound like generic royalty-free stock music? Consider: are the sounds unique or default presets? Is the arrangement predictable or surprising? Rate 1-5.{lyrics_check}
6. ENDING QUALITY: Does the track end naturally (fade out, musical resolution, intentional silence) or does it cut off abruptly mid-phrase? If it cuts off, does it sound like the track was truncated/cropped?
7. INSTRUMENTS: What specific instruments or sounds can you identify? List them (e.g., "electric guitar, 808 bass, hi-hats, pad synth, vocal chops").
8. DESCRIPTION: In 2-3 sentences, describe what this track sounds like to a listener who hasn't heard it. Include tempo feel, energy arc, key sonic textures, and emotional character.

Respond ONLY with valid JSON in this exact format (no markdown, no code fences):
{{
  "vocal_contamination": true/false,
  "vocal_notes": "description if vocals detected, empty string if clean",
  "genre_match": 1-5,
  "genre_notes": "brief explanation",
  "mood_match": 1-5,
  "mood_notes": "brief explanation",
  "production_quality": 1-5,
  "production_notes": "brief explanation",
  "artistic_interest": 1-5,
  "artistic_notes": "brief explanation",
  "ending_quality": "natural" or "abrupt" or "truncated",
  "ending_notes": "brief explanation",
  "instruments": ["list", "of", "instruments", "detected"],
  "description": "2-3 sentence sonic description of the track",
  "overall_score": 1-5,
  "verdict": "Keep" or "Regenerate" or "Marginal",
  "summary": "One sentence overall impression"
}}"""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[prompt, audio_file],
        )
    except Exception as e:
        # Clean up uploaded file on error
        try:
            client.files.delete(name=audio_file.name)
        except Exception:
            pass
        raise RuntimeError(f"Gemini API call failed: {e}") from e

    # Clean up uploaded file
    try:
        client.files.delete(name=audio_file.name)
    except Exception:
        pass

    # Parse the JSON response
    text = response.text.strip()
    # Clean up any markdown fencing (handles ```json and ``` variants)
    text = re.sub(r'^```\w*\n?', '', text)
    text = re.sub(r'\n?```$', '', text)
    text = text.strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        result = {
            "error": "Failed to parse Gemini response",
            "raw_response": text[:500],
            "verdict": "Marginal",
        }

    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: .venv/bin/python lib/gemini_audio.py <audio_path> [tags] [mood]")
        sys.exit(1)

    path = sys.argv[1]
    tags = sys.argv[2] if len(sys.argv) > 2 else ""
    mood = sys.argv[3] if len(sys.argv) > 3 else ""

    print(f"Evaluating: {path}")
    result = evaluate_track(path, tags=tags, mood=mood, title=Path(path).stem)
    print(json.dumps(result, indent=2))
