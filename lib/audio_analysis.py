"""
Audio analysis for Refrakt pipeline — detect generic tracks, truncation, and quality issues.

Uses librosa for signal-level analysis. Complements Gemini's subjective evaluation
with quantitative metrics.

Usage:
    from lib.audio_analysis import analyze_track, batch_similarity, full_critique

    # Single track analysis
    report = analyze_track("output/track.m4a")

    # Batch similarity (flag same-sounding tracks)
    sim_matrix, flags = batch_similarity(["track1.m4a", "track2.m4a", ...])

    # Full critique (all checks combined)
    critique = full_critique("output/track.m4a", tags="dubstep, heavy bass, ...")
"""

import librosa
import numpy as np
from pathlib import Path

# Essentia is optional — used for enhanced fade detection and dynamic complexity
try:
    import essentia.standard as es
    HAS_ESSENTIA = True
except ImportError:
    HAS_ESSENTIA = False


# --- Feature Extraction ---

def extract_embedding(audio_path, n_mfcc=20):
    """Extract a 59-dimensional feature vector for similarity comparison."""
    y, sr = librosa.load(str(audio_path), sr=22050)

    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
    mfcc_mean = np.mean(mfccs, axis=1)
    mfcc_std = np.std(mfccs, axis=1)

    chroma = librosa.feature.chroma_cens(y=y, sr=sr)
    chroma_mean = np.mean(chroma, axis=1)

    contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
    contrast_mean = np.mean(contrast, axis=1)

    return np.concatenate([mfcc_mean, mfcc_std, chroma_mean, contrast_mean])


# --- Truncation Detection ---

def detect_truncation(audio_path):
    """Detect if a track was truncated by Suno's 8-minute limit.

    Returns dict with:
        truncated: bool
        confidence: float (0-1)
        reason: str
        duration_seconds: float
    """
    y, sr = librosa.load(str(audio_path), sr=22050)
    duration = librosa.get_duration(y=y, sr=sr)

    result = {
        "duration_seconds": float(duration),
        "duration_display": f"{int(duration // 60)}:{int(duration % 60):02d}",
    }

    # Check 1: Duration threshold
    if duration >= 475:  # 7:55+
        result["truncated"] = True
        result["confidence"] = 0.95
        result["reason"] = "duration_exceeds_limit"
        return result
    elif duration >= 470:  # 7:50+
        result["duration_warning"] = True

    # Check 2: Abrupt ending via RMS energy
    rms = librosa.feature.rms(y=y, hop_length=512)[0]
    times = librosa.frames_to_time(range(len(rms)), sr=sr, hop_length=512)

    body_start = int(len(rms) * 0.1)
    body_end = int(len(rms) * 0.9)
    body_rms = np.mean(rms[body_start:body_end]) if body_end > body_start else np.mean(rms)

    last_2s_idx = np.searchsorted(times, duration - 2.0)
    last_500ms_idx = np.searchsorted(times, duration - 0.5)

    if last_2s_idx >= len(rms) - 4:
        result["truncated"] = False
        result["confidence"] = 0.0
        result["reason"] = "track_too_short_to_analyze"
        return result

    pre_end_rms = np.mean(rms[last_2s_idx:last_500ms_idx]) if last_500ms_idx > last_2s_idx else 0
    last_500ms_rms = np.mean(rms[last_500ms_idx:]) if last_500ms_idx < len(rms) else 0

    # Natural fade: pre-end is already quiet
    if pre_end_rms < body_rms * 0.1:
        result["truncated"] = False
        result["confidence"] = 0.8
        result["reason"] = "natural_fade"
        return result

    energy_ratio = last_500ms_rms / (pre_end_rms + 1e-8)
    final_frame_energy = float(rms[-1]) / (body_rms + 1e-8)

    truncated = energy_ratio > 0.7 and final_frame_energy > 0.3
    result["truncated"] = truncated
    result["confidence"] = float(min(1.0, energy_ratio * final_frame_energy * 2))
    result["reason"] = "abrupt_cutoff" if truncated else "natural_ending"
    result["energy_ratio"] = float(energy_ratio)
    result["final_frame_energy"] = float(final_frame_energy)

    return result


# --- Timbral Variety (single track) ---

def measure_variety(audio_path):
    """Measure timbral variety within a single track.

    Low variety = one synth loop for 3 minutes (generic).
    High variety = distinct sections, layering, dynamic changes.
    """
    y, sr = librosa.load(str(audio_path), sr=22050)
    duration = librosa.get_duration(y=y, sr=sr)

    # MFCC temporal variation
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
    mfcc_temporal_std = np.std(mfccs, axis=1)
    variety_score = float(np.mean(mfcc_temporal_std))

    # Spectral centroid coefficient of variation
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
    centroid_cv = float(np.std(centroid) / (np.mean(centroid) + 1e-8))

    # Onset density (events per second)
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    onset_density = len(onsets) / duration if duration > 0 else 0

    # Dynamic range (dB difference between loud and quiet sections)
    rms = librosa.feature.rms(y=y, hop_length=512)[0]
    rms_db = librosa.amplitude_to_db(rms + 1e-8)
    dynamic_range = float(np.percentile(rms_db, 95) - np.percentile(rms_db, 5))

    # Spectral flatness (how "noisy" vs "tonal" — high = white noise, low = pure tones)
    flatness = librosa.feature.spectral_flatness(y=y)
    avg_flatness = float(np.mean(flatness))

    return {
        "variety_score": variety_score,
        "centroid_cv": centroid_cv,
        "onset_density": float(onset_density),
        "dynamic_range_db": dynamic_range,
        "spectral_flatness": avg_flatness,
        "duration_seconds": float(duration),
    }


# --- Structural Analysis ---

def analyze_structure(audio_path, n_segments=6):
    """Detect whether a track has actual sections or is one loop repeated.

    Returns avg_section_similarity (high = repetitive, low = varied).
    """
    y, sr = librosa.load(str(audio_path), sr=22050)

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

    # Structural segmentation
    bounds = librosa.segment.agglomerative(chroma, k=min(n_segments, chroma.shape[1] - 1))

    segment_features = []
    for i in range(len(bounds) - 1):
        seg = chroma[:, bounds[i]:bounds[i + 1]]
        if seg.shape[1] > 0:
            segment_features.append(np.mean(seg, axis=1))

    if len(segment_features) < 2:
        return {"avg_section_similarity": 1.0, "num_sections": 1, "is_looped": True}

    from sklearn.metrics.pairwise import cosine_similarity
    seg_matrix = cosine_similarity(segment_features)
    n = seg_matrix.shape[0]
    off_diag = seg_matrix[np.triu_indices(n, k=1)]
    avg_sim = float(np.mean(off_diag))

    return {
        "avg_section_similarity": avg_sim,
        "num_sections": len(segment_features),
        "is_looped": bool(avg_sim > 0.92),
    }


# --- Essentia Enhanced Analysis ---

def _essentia_load(audio_path):
    """Load audio via essentia's MonoLoader, falling back to MP3 companion if M4A fails.

    Essentia's MonoLoader crashes (SIGABRT) on Opus-in-M4A containers from Suno.
    If the input is .m4a and a .mp3 companion exists, use that instead.
    """
    path = str(audio_path)
    if path.endswith(".m4a"):
        mp3_path = path.replace(".m4a", ".mp3")
        if Path(mp3_path).exists():
            path = mp3_path
    return es.MonoLoader(filename=path, sampleRate=44100)()


def detect_fade(audio_path):
    """Use Essentia's FadeDetection for proper fade-out detection.

    More accurate than RMS heuristics for distinguishing natural endings
    from truncation. Returns None if essentia is not installed.
    """
    if not HAS_ESSENTIA:
        return None

    try:
        audio = _essentia_load(audio_path)
        fade = es.FadeDetection(minLength=1.5, cutoffHigh=0.85, cutoffLow=0.2)
        fade_in, fade_out = fade(audio)

        duration = len(audio) / 44100.0
        has_fade_out = len(fade_out) > 0
        late_fade = any(fo[0] > duration - 10.0 for fo in fade_out) if has_fade_out else False

        return {
            "has_fade_out": has_fade_out,
            "late_fade_out": late_fade,
            "fade_out_count": len(fade_out),
            "duration": float(duration),
        }
    except Exception as e:
        return {"error": str(e)}


def measure_dynamic_complexity(audio_path):
    """Use Essentia's DynamicComplexity for loudness fluctuation analysis.

    Better than simple dB range — measures actual loudness variation over time.
    Returns None if essentia is not installed.
    """
    if not HAS_ESSENTIA:
        return None

    try:
        audio = _essentia_load(audio_path)
        dc = es.DynamicComplexity()
        complexity, loudness = dc(audio)

        return {
            "dynamic_complexity": float(complexity),
            "loudness_db": float(loudness),
            # Typical: 2-8 for pop/electronic, <2 for static/droning
        }
    except Exception as e:
        return {"error": str(e)}


# --- Batch Similarity ---

def batch_similarity(audio_paths, threshold=0.93):
    """Compute pairwise similarity for a batch. Flag pairs above threshold.

    Returns (similarity_matrix, flagged_pairs).
    """
    from sklearn.metrics.pairwise import cosine_similarity

    embeddings = []
    for p in audio_paths:
        try:
            emb = extract_embedding(p)
            embeddings.append(emb)
        except Exception as e:
            print(f"  Warning: could not process {p}: {e}")
            embeddings.append(np.zeros(59))

    matrix = cosine_similarity(embeddings)
    n = len(audio_paths)

    flagged = []
    for i in range(n):
        for j in range(i + 1, n):
            if matrix[i][j] > threshold:
                flagged.append({
                    "track_a": str(audio_paths[i]),
                    "track_b": str(audio_paths[j]),
                    "similarity": float(matrix[i][j]),
                })

    return matrix, flagged


# --- Combined Analysis ---

def analyze_track(audio_path):
    """Run all analyses on a single track. Returns combined report."""
    path = str(audio_path)

    truncation = detect_truncation(path)
    variety = measure_variety(path)
    structure = analyze_structure(path)

    report = {
        "file": Path(path).name,
        "truncation": truncation,
        "variety": variety,
        "structure": structure,
    }

    # Essentia enhancements (optional — gracefully absent)
    fade = detect_fade(path)
    if fade:
        report["fade_detection"] = fade

    dynamics = measure_dynamic_complexity(path)
    if dynamics:
        report["dynamic_complexity"] = dynamics

    return report


def full_critique(audio_path, tags="", is_instrumental=True, expected_duration=None):
    """Generate a human-readable critique with pass/fail flags.

    Args:
        audio_path: path to .m4a or .mp3 file
        tags: Suno style tags string (for context-aware checks)
        is_instrumental: True if no vocals expected
        expected_duration: optional target duration in seconds. If None, uses
            sensible defaults (120s min for standard tracks, 90s for intros/outros)

    Returns dict with 'issues' list and 'verdict' (pass/warn/fail).
    """
    report = analyze_track(audio_path)
    issues = []

    # Truncation (too long)
    if report["truncation"].get("truncated"):
        issues.append(f"TRUNCATED: Track cut off at {report['truncation']['duration_display']} "
                      f"(Suno 8-min limit). Confidence: {report['truncation']['confidence']:.0%}")

    dur = report["truncation"]["duration_seconds"]
    dur_display = report["truncation"]["duration_display"]

    if dur >= 470 and not report["truncation"].get("truncated"):
        issues.append(f"DURATION WARNING: {dur_display} — dangerously close to 8-min limit")

    # Duration check (too short)
    tags_lower = tags.lower()

    if expected_duration is not None:
        # Explicit target — flag if less than 60% of expected
        if dur < expected_duration * 0.6:
            issues.append(f"SHORT: {dur_display} is only {dur/expected_duration:.0%} of "
                          f"expected {int(expected_duration//60)}:{int(expected_duration%60):02d}")
    else:
        # Heuristic thresholds based on context
        # Intro/outro segments can be shorter
        is_intro_outro = any(w in tags_lower for w in ["intro", "outro", "interlude", "transition"])
        min_duration = 90 if is_intro_outro else 120  # 1:30 for intros, 2:00 for standard

        if dur < min_duration:
            issues.append(f"SHORT: {dur_display} — under {min_duration//60}:{min_duration%60:02d} minimum "
                          f"{'(intro/outro threshold)' if is_intro_outro else '(standard track threshold)'}")

    # Low variety (generic loop)
    v = report["variety"]
    if v["variety_score"] < 8.0:
        issues.append(f"LOW VARIETY: Timbral variety score {v['variety_score']:.1f} (threshold: 8.0) — "
                      f"track may be one synth loop repeated")

    if v["centroid_cv"] < 0.15:
        issues.append(f"FLAT BRIGHTNESS: Spectral centroid CV {v['centroid_cv']:.3f} — "
                      f"no brightness variation (same texture throughout)")

    if v["dynamic_range_db"] < 6.0:
        issues.append(f"LOW DYNAMICS: Only {v['dynamic_range_db']:.1f}dB dynamic range — "
                      f"over-compressed or monotonous energy")

    # Structural repetition
    s = report["structure"]
    if s["is_looped"]:
        issues.append(f"LOOPED: Section similarity {s['avg_section_similarity']:.2f} — "
                      f"track is essentially one section repeated")

    # Essentia: fade detection (strengthens truncation verdict)
    fade = report.get("fade_detection")
    if fade and not fade.get("error"):
        if dur >= 450 and not fade["has_fade_out"]:
            issues.append(f"NO FADE-OUT: Track is {dur_display} with no detected fade — "
                          f"likely truncated")

    # Essentia: dynamic complexity
    dc = report.get("dynamic_complexity")
    if dc and not dc.get("error"):
        if dc["dynamic_complexity"] < 2.0 and "ambient" not in tags_lower and "drone" not in tags_lower:
            issues.append(f"STATIC: Dynamic complexity {dc['dynamic_complexity']:.1f} — "
                          f"track lacks dynamic movement (typical: 2-8 for pop/electronic)")

    # Context-aware checks
    tags_lower = tags.lower()
    if is_instrumental and "ambient" not in tags_lower and "drone" not in tags_lower:
        # Non-ambient instrumentals should have reasonable onset density
        if v["onset_density"] < 0.5:
            issues.append(f"SPARSE: Only {v['onset_density']:.1f} events/sec for a non-ambient track")

    # Verdict
    critical = [i for i in issues if i.startswith(("TRUNCATED", "LOOPED"))]
    warnings = [i for i in issues if not i.startswith(("TRUNCATED", "LOOPED"))]
    # SHORT on its own is a WARN, but SHORT + another warning = stronger signal

    if critical:
        verdict = "FAIL"
    elif len(warnings) >= 2:
        verdict = "WARN"
    elif warnings:
        verdict = "WARN"
    else:
        verdict = "PASS"

    return {
        "file": Path(audio_path).name,
        "verdict": verdict,
        "issues": issues,
        "metrics": report,
    }
