"""
dalle_art.py — Album art generation via DALL-E 3.

Generates square (1024x1024) and widescreen (1792x1024) album cover art
from a text prompt. Returns the saved file paths.

Requires OPENAI_API_KEY in .env.
"""

import base64
import os
import sys
from pathlib import Path

from openai import OpenAI

BASE_DIR = Path(__file__).parent.parent


def _load_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip()
    print("ERROR: OPENAI_API_KEY not found in environment or .env", file=sys.stderr)
    sys.exit(1)


def generate_album_art(
    prompt: str,
    output_dir: str | Path,
    name: str = "album-cover",
    square: bool = True,
    widescreen: bool = True,
) -> dict[str, str]:
    """
    Generate album cover art using DALL-E 3.

    Args:
        prompt: Text description of the desired artwork.
        output_dir: Directory to save the images.
        name: Base filename (without extension).
        square: Generate 1024x1024 square version (for MP3 metadata).
        widescreen: Generate 1792x1024 widescreen version (for YouTube).

    Returns:
        Dict with keys 'square' and/or 'widescreen' mapping to file paths.
    """
    api_key = _load_api_key()
    client = OpenAI(api_key=api_key)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    if not square and not widescreen:
        raise ValueError("At least one of square or widescreen must be True")

    sizes = []
    if square:
        sizes.append(("1024x1024", f"{name}.png", "square"))
    if widescreen:
        sizes.append(("1792x1024", f"{name}-wide.png", "widescreen"))

    for size, filename, label in sizes:
        print(f"  Generating {label} ({size})...")
        try:
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality="hd",
                n=1,
                response_format="b64_json",
            )
        except Exception as e:
            raise RuntimeError(f"DALL-E image generation failed ({label}): {e}") from e

        if not response.data:
            raise RuntimeError(f"DALL-E returned empty data for {label} — possible content policy filter")

        img_data = base64.b64decode(response.data[0].b64_json)
        filepath = output_dir / filename
        with open(filepath, "wb") as f:
            f.write(img_data)

        results[label] = str(filepath)
        print(f"  Saved: {filepath} ({len(img_data)//1024} KB)")

    return results


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: .venv/bin/python lib/dalle_art.py <output_dir> <prompt>")
        sys.exit(1)

    output_dir = sys.argv[1]
    prompt = sys.argv[2]

    print(f"Generating album art...")
    results = generate_album_art(prompt, output_dir)
    for label, path in results.items():
        print(f"  {label}: {path}")
