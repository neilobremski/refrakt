"""
music_analysis.py — ML-powered music analysis for the Refrakt pipeline.

Provides structured analysis of generated tracks using:
- CLAP (zero-shot audio→text matching) — compare intended tags vs actual audio
- Essentia MusicExtractor — 167 features including BPM, key, dynamics, spectral
- Combined report with tag accuracy scoring

Usage:
    from lib.music_analysis import analyze_music, match_tags, quick_report

    # Full analysis
    report = analyze_music("track.mp3", tags="melodic house, driving bass, 124 BPM")

    # Just tag matching
    scores = match_tags("track.mp3", ["melodic house", "driving bass", "shimmering pads"])

    # Quick text report
    text = quick_report("track.mp3", tags="melodic house, driving bass, 124 BPM")
"""

import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

# Suppress non-critical warnings during model loading
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, message=".*PySoundFile.*")

BASE_DIR = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# CLAP — Zero-shot audio→text matching
# ---------------------------------------------------------------------------

_clap_model = None


def _get_clap_model():
    """Lazy-load CLAP model (downloads ~600MB checkpoint on first use)."""
    global _clap_model
    if _clap_model is not None:
        return _clap_model

    import laion_clap
    model = laion_clap.CLAP_Module(enable_fusion=False, amodel="HTSAT-tiny")
    model.load_ckpt()  # downloads music_audioset_epoch_15_esc_90.14.pt
    _clap_model = model
    return model


def _ensure_wav(audio_path):
    """CLAP requires WAV input. Convert M4A/MP3 to temp WAV if needed."""
    path = str(audio_path)
    if path.endswith(".wav"):
        return path, False

    import subprocess
    import tempfile
    wav_path = tempfile.mktemp(suffix=".wav")
    result = subprocess.run(
        ["ffmpeg", "-i", path, "-ar", "48000", "-ac", "1", "-y", wav_path],
        capture_output=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed: {result.stderr[:200]}")
    return wav_path, True


def match_tags(audio_path, tag_labels):
    """Score how well an audio file matches a list of text descriptions.

    Args:
        audio_path: path to audio file (WAV, MP3, or M4A)
        tag_labels: list of text descriptions to match against

    Returns:
        list of (label, score) tuples sorted by score descending.
        Scores are cosine similarities in [-1, 1] range.
    """
    import torch

    model = _get_clap_model()

    wav_path, is_temp = _ensure_wav(audio_path)
    try:
        audio_embed = model.get_audio_embedding_from_filelist(
            [wav_path], use_tensor=True
        )
        text_embed = model.get_text_embedding(tag_labels, use_tensor=True)

        # Cosine similarity between audio and each text label
        audio_norm = audio_embed / audio_embed.norm(dim=-1, keepdim=True)
        text_norm = text_embed / text_embed.norm(dim=-1, keepdim=True)
        similarities = (audio_norm @ text_norm.T).squeeze(0)

        results = []
        for i, label in enumerate(tag_labels):
            results.append((label, float(similarities[i])))

        results.sort(key=lambda x: x[1], reverse=True)
        return results
    finally:
        if is_temp:
            os.unlink(wav_path)


def score_tag_accuracy(audio_path, intended_tags):
    """Score how well generated audio matches its intended Suno tags.

    Splits the comma-separated tags string, scores each individually,
    and returns an overall accuracy metric.

    Returns dict with per-tag scores and an aggregate.
    """
    # Split tags and clean up
    tags = [t.strip() for t in intended_tags.split(",") if t.strip()]
    if not tags:
        return {"error": "no tags provided", "overall": 0.0}

    # Also include some negative reference tags for calibration
    negative_refs = [
        "silence and nothing",
        "random noise static",
        "spoken word podcast",
    ]

    all_labels = tags + negative_refs
    scores = match_tags(audio_path, all_labels)
    score_dict = dict(scores)

    # Per-tag scores
    tag_scores = {t: score_dict.get(t, 0.0) for t in tags}

    # Aggregate: mean of intended tag scores
    intended_mean = float(np.mean([tag_scores[t] for t in tags]))

    # Negative reference mean (should be low)
    neg_mean = float(np.mean([score_dict.get(t, 0.0) for t in negative_refs]))

    # Tag accuracy = how much better intended tags score vs negative refs
    # Normalized to 0-1 range
    spread = intended_mean - neg_mean
    accuracy = max(0.0, min(1.0, (spread + 0.3) / 0.6))  # map [-0.3, 0.3] → [0, 1]

    return {
        "tag_scores": tag_scores,
        "overall_accuracy": round(accuracy, 3),
        "intended_mean": round(intended_mean, 4),
        "negative_mean": round(neg_mean, 4),
        "spread": round(spread, 4),
        "top_matching": scores[:5],
        "bottom_matching": scores[-3:],
    }


# ---------------------------------------------------------------------------
# Essentia MusicExtractor — Rich feature extraction
# ---------------------------------------------------------------------------

def extract_music_features(audio_path):
    """Extract 167 music features using Essentia's MusicExtractor.

    Returns a structured dict with BPM, key, scale, dynamics, spectral
    features, rhythm patterns, and tonal analysis.

    Note: Essentia crashes on Opus-in-M4A files. Falls back to MP3 companion.
    """
    try:
        import essentia.standard as es
    except ImportError:
        return {"error": "essentia not installed"}

    # Handle M4A → MP3 fallback
    path = str(audio_path)
    if path.endswith(".m4a"):
        mp3_path = path.replace(".m4a", ".mp3")
        if Path(mp3_path).exists():
            path = mp3_path

    try:
        me = es.MusicExtractor(
            lowlevelStats=["mean", "stdev"],
            rhythmStats=["mean", "stdev"],
            tonalStats=["mean", "stdev"],
        )
        features, _ = me(path)
    except Exception as e:
        return {"error": str(e)}

    # Extract the most useful features into a clean structure
    def safe_get(key, default=None):
        try:
            val = features[key]
            if isinstance(val, np.ndarray):
                return val.tolist()
            if isinstance(val, (np.floating, np.integer)):
                return float(val)
            return val
        except Exception:
            return default

    return {
        "rhythm": {
            "bpm": safe_get("rhythm.bpm"),
            "bpm_confidence": safe_get("rhythm.bpm_histogram_first_peak_bpm.mean"),
            "danceability": safe_get("rhythm.danceability"),
            "onset_rate": safe_get("rhythm.onset_rate"),
        },
        "tonal": {
            "key": safe_get("tonal.key_edma.key"),
            "scale": safe_get("tonal.key_edma.scale"),
            "key_strength": safe_get("tonal.key_edma.strength"),
            "tuning_frequency": safe_get("tonal.tuning_frequency"),
        },
        "dynamics": {
            "dynamic_complexity": safe_get("lowlevel.dynamic_complexity"),
            "loudness_ebu128": safe_get("lowlevel.loudness_ebu128.integrated"),
            "loudness_range": safe_get("lowlevel.loudness_ebu128.loudness_range"),
        },
        "spectral": {
            "centroid_mean": safe_get("lowlevel.spectral_centroid.mean"),
            "centroid_stdev": safe_get("lowlevel.spectral_centroid.stdev"),
            "flatness_mean": safe_get("lowlevel.spectral_flatness_db.mean"),
            "rolloff_mean": safe_get("lowlevel.spectral_rolloff.mean"),
            "mfcc_mean": safe_get("lowlevel.mfcc.mean"),
        },
        "metadata": {
            "duration": safe_get("metadata.audio_properties.length"),
            "sample_rate": safe_get("metadata.audio_properties.analysis.sample_rate"),
            "bit_rate": safe_get("metadata.audio_properties.bit_rate"),
        },
    }


# ---------------------------------------------------------------------------
# Combined Analysis
# ---------------------------------------------------------------------------

def analyze_music(audio_path, tags=""):
    """Run full ML analysis: CLAP tag matching + Essentia features.

    Args:
        audio_path: path to audio file
        tags: comma-separated Suno style tags

    Returns combined report dict.
    """
    report = {"file": Path(audio_path).name}

    # Essentia features (fast, ~3s)
    report["features"] = extract_music_features(audio_path)

    # CLAP tag accuracy (slower, ~5s, requires model download on first run)
    if tags:
        report["tag_accuracy"] = score_tag_accuracy(audio_path, tags)

    return report


def quick_report(audio_path, tags=""):
    """Generate a human-readable text report."""
    r = analyze_music(audio_path, tags)
    lines = [f"=== Music Analysis: {r['file']} ===\n"]

    # Features
    f = r.get("features", {})
    if "error" not in f:
        rhythm = f.get("rhythm", {})
        tonal = f.get("tonal", {})
        dynamics = f.get("dynamics", {})
        meta = f.get("metadata", {})

        dur = meta.get("duration", 0)
        lines.append(f"Duration: {int(dur//60)}:{int(dur%60):02d}")
        lines.append(f"BPM: {rhythm.get('bpm', '?'):.1f}")
        lines.append(f"Key: {tonal.get('key', '?')} {tonal.get('scale', '?')} "
                     f"(strength: {tonal.get('key_strength', 0):.2f})")
        lines.append(f"Danceability: {rhythm.get('danceability', '?'):.2f}")
        dc = dynamics.get("dynamic_complexity", 0)
        lines.append(f"Dynamic complexity: {dc:.1f} {'(static)' if dc < 2 else '(dynamic)' if dc > 5 else '(moderate)'}")
        lines.append("")

    # Tag accuracy
    ta = r.get("tag_accuracy", {})
    if ta and "error" not in ta:
        acc = ta["overall_accuracy"]
        emoji = "+++" if acc > 0.75 else "++" if acc > 0.5 else "+" if acc > 0.25 else "-"
        lines.append(f"Tag Accuracy: {acc:.0%} [{emoji}]")
        lines.append(f"  Intended mean: {ta['intended_mean']:.3f}")
        lines.append(f"  Negative mean: {ta['negative_mean']:.3f}")
        lines.append(f"  Spread: {ta['spread']:.3f}")
        lines.append("")
        lines.append("  Per-tag scores:")
        for tag, score in sorted(ta["tag_scores"].items(), key=lambda x: x[1], reverse=True):
            bar = "█" * int(max(0, (score + 0.3) * 15))
            lines.append(f"    {score:+.3f}  {bar}  {tag}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: .venv/bin/python lib/music_analysis.py <audio_path> [tags]")
        sys.exit(1)

    path = sys.argv[1]
    tags = sys.argv[2] if len(sys.argv) > 2 else ""

    print(quick_report(path, tags))
