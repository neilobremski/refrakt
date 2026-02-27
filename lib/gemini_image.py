"""
gemini_image.py — Album art generation via Google Gemini 2.0 Flash.

Generates square (1:1) and widescreen (16:9) album cover art
from a text prompt. Returns the saved file paths.

Requires GEMINI_API_KEY in .env.
"""

import base64
import os
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


def generate_album_art(
    title: str,
    artist: str,
    concept: str,
    output_dir: str | Path,
    square: bool = True,
    widescreen: bool = True,
) -> dict[str, str]:
    """
    Generate album cover art using Gemini 2.5 Flash.

    Args:
        title: Track or album title to display on artwork.
        artist: Artist name to display on artwork.
        concept: Text description of the desired artwork mood/theme/visual direction.
        output_dir: Directory to save the images.
        square: Generate ~2048x2048 square version (for MP3 metadata).
        widescreen: Generate ~2752x1536 widescreen version (for YouTube).

    Returns:
        Dict with keys 'square' and/or 'widescreen' mapping to file paths.
    """
    api_key = _load_api_key()
    client = genai.Client(api_key=api_key)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    if not square and not widescreen:
        raise ValueError("At least one of square or widescreen must be True")

    # Generate square image
    if square:
        print(f"  Generating square (1:1) image...")
        prompt = f"""Generate an image: {concept}

Square 1:1 aspect ratio. Include the text "{title}" in a clean modern sans-serif font in the lower third, and "{artist}" in smaller text below it. Light/white text with subtle glow for readability."""

        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[prompt],
            )
        except Exception as e:
            raise RuntimeError(f"Gemini image generation failed (square): {e}") from e

        if not response.candidates or not response.candidates[0].content.parts:
            raise RuntimeError("Gemini returned empty response for square image — possible content policy filter")

        # Extract image from response
        image_data = None
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'mime_type') and part.mime_type.startswith('image/'):
                if hasattr(part, 'data'):
                    image_data = part.data
                    break

        if not image_data:
            raise RuntimeError("No image data found in Gemini response for square")

        filepath = output_dir / "cover.png"
        with open(filepath, "wb") as f:
            f.write(image_data)

        results['square'] = str(filepath)
        print(f"  Saved: {filepath} ({len(image_data)//1024} KB)")

    # Generate widescreen image
    if widescreen:
        print(f"  Generating widescreen (16:9) image...")
        prompt = f"""Generate an image: {concept}

Widescreen 16:9 aspect ratio. Keep the title text "{title}" and artist "{artist}" in the same position as before."""

        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[prompt],
            )
        except Exception as e:
            raise RuntimeError(f"Gemini image generation failed (widescreen): {e}") from e

        if not response.candidates or not response.candidates[0].content.parts:
            raise RuntimeError("Gemini returned empty response for widescreen image — possible content policy filter")

        # Extract image from response
        image_data = None
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'mime_type') and part.mime_type.startswith('image/'):
                if hasattr(part, 'data'):
                    image_data = part.data
                    break

        if not image_data:
            raise RuntimeError("No image data found in Gemini response for widescreen")

        filepath = output_dir / "cover-wide.png"
        with open(filepath, "wb") as f:
            f.write(image_data)

        results['widescreen'] = str(filepath)
        print(f"  Saved: {filepath} ({len(image_data)//1024} KB)")

    return results


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: .venv/bin/python lib/gemini_image.py <output_dir> <title> <artist> <concept>")
        sys.exit(1)

    output_dir = sys.argv[1]
    title = sys.argv[2]
    artist = sys.argv[3]
    concept = sys.argv[4]

    print(f"Generating album art for '{title}' by {artist}...")
    results = generate_album_art(title, artist, concept, output_dir)
    for label, path in results.items():
        print(f"  {label}: {path}")
