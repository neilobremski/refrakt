# Audio Analysis Tools Research

Research into Python audio analysis tools for detecting generic/samey tracks,
truncated endings, and improving evaluation quality in the Refrakt pipeline.

**Date:** 2026-02-26

---

## Table of Contents

1. [Problem Summary](#problem-summary)
2. [Library Overview](#library-overview)
3. [Problem 1: Detecting Generic/Samey Tracks](#problem-1-detecting-genericsamey-tracks)
4. [Problem 2: Truncated Track Detection](#problem-2-truncated-track-detection)
5. [Problem 3: Better Audio Evaluation](#problem-3-better-audio-evaluation)
6. [Recommended Stack](#recommended-stack)
7. [Pipeline Integration Plan](#pipeline-integration-plan)

---

## Problem Summary

Three issues with Suno AI output quality:

1. **Generic/samey tracks** -- many tracks in a batch sound nearly identical (same synth
   patches, same progressions, same energy curve). Need similarity detection, novelty
   measurement, and timbral variety analysis.

2. **Truncated tracks** -- Suno has an 8-minute hard limit. Tracks near 7:50+ get
   abruptly chopped mid-phrase. Need duration checks and abrupt ending detection.

3. **Evaluation gaps** -- Gemini 2.5 Flash eval works for individual track quality but
   misses cross-track similarity and truncation. Need complementary signal-level tools.

---

## Library Overview

### librosa (Recommended -- Primary Tool)

- **What:** Python library for music and audio analysis (MIR)
- **Version:** 0.11.0 (March 2025)
- **Install:** `pip install librosa`
- **Python:** 3.8--3.13
- **Dependencies:** numpy, scipy, soundfile, audioread (needs ffmpeg for MP3)
- **License:** ISC (permissive)
- **Performance:** Pure Python + NumPy. Fast enough for batch processing 20 clips.
  Loading a 4-minute M4A takes ~1s, feature extraction ~0.5s per track.
- **Strengths:** Best-documented MIR library, huge community, stable API, covers all
  our feature extraction needs. Self-similarity matrices, cross-similarity, onset
  detection, spectral features, RMS energy -- everything in one package.

### essentia (Recommended -- Complementary)

- **What:** C++ library with Python bindings for audio analysis and MIR (by MTG/UPF)
- **Version:** 2.1b6.dev1389 (July 2025)
- **Install:** `pip install essentia` (or `pip install essentia-tensorflow` for DL models)
- **Python:** 3.9--3.13
- **macOS:** Wheels for x86_64 (macOS 13+) and ARM64 (macOS 15+)
- **License:** AGPL-3.0 (copyleft -- fine for internal pipeline, not for distribution)
- **Strengths:** Pre-trained DL embedding models (Discogs-EffNet, MAEST) for music
  similarity, FadeDetection algorithm, DynamicComplexity, MusicExtractor for bulk
  feature extraction. Faster than librosa for some operations (C++ core).

### madmom (Skip)

- **What:** Beat/onset detection focused library
- **Version:** 0.16.1 (November 2018 -- stale)
- **Python:** 2.7 and 3.3--3.7 (outdated)
- **Verdict:** Not recommended. Last release was 2018, Python version support is ancient.
  librosa covers the same beat/onset features with active maintenance.

### pyAudioAnalysis (Skip)

- **What:** Audio feature extraction, classification, segmentation
- **Version:** 0.3.14 (February 2022 -- stale)
- **Verdict:** Not recommended. No updates since 2022, limited documentation, and
  librosa + essentia cover all the same ground with better APIs.

### pyacoustid / Chromaprint (Niche Use)

- **What:** Audio fingerprinting via Chromaprint + AcoustID web service
- **Install:** `pip install pyacoustid` + install Chromaprint (`brew install chromaprint`)
- **Key function:** `chromaprint.compare_fingerprints()` for similarity between two files
- **Verdict:** Useful but limited. Fingerprints are designed for exact-match identification
  (is this the same recording?), not for measuring stylistic/timbral similarity. Two
  completely different Suno tracks in the same style would NOT match on fingerprint.
  Better to use MFCC/embedding-based similarity instead. Could be useful as a fast
  pre-filter to catch literal duplicates (Suno occasionally generates near-identical
  clips from the same prompt).

---

## Problem 1: Detecting Generic/Samey Tracks

### Approach A: MFCC-Based Pairwise Similarity (librosa)

The most practical approach. Extract mean MFCC vectors per track, compute cosine
similarity between all pairs in a batch.

**How MFCCs work:** Mel-Frequency Cepstral Coefficients capture the "shape" of the
frequency spectrum as perceived by human hearing. They encode timbral characteristics --
what instruments sound like, the texture of the sound. Two tracks with similar MFCC
profiles sound alike.

```python
import librosa
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

def extract_track_embedding(audio_path, n_mfcc=20):
    """Extract a fixed-size feature vector from an audio file."""
    y, sr = librosa.load(audio_path, sr=22050)

    # MFCCs -- timbral fingerprint (20 coefficients)
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
    mfcc_mean = np.mean(mfccs, axis=1)
    mfcc_std = np.std(mfccs, axis=1)

    # Chroma -- harmonic/pitch content (12 pitch classes)
    chroma = librosa.feature.chroma_cens(y=y, sr=sr)
    chroma_mean = np.mean(chroma, axis=1)

    # Spectral contrast -- timbral brightness/variety (7 bands)
    contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
    contrast_mean = np.mean(contrast, axis=1)

    # Concatenate into one feature vector (20+20+12+7 = 59 dimensions)
    return np.concatenate([mfcc_mean, mfcc_std, chroma_mean, contrast_mean])


def batch_similarity(audio_paths):
    """Compute pairwise similarity for a batch of tracks."""
    embeddings = [extract_track_embedding(p) for p in audio_paths]
    matrix = cosine_similarity(embeddings)
    return matrix  # NxN matrix, values 0-1 (1 = identical)
```

**Similarity thresholds (empirical, needs tuning):**
- `> 0.95` -- Very similar, likely same prompt with minimal variation. Flag for review.
- `0.85 - 0.95` -- Similar feel, might be acceptable depending on batch purpose.
- `< 0.85` -- Sufficiently different.

**Features to include in the embedding:**
| Feature | Dimensions | What it captures |
|---------|-----------|-----------------|
| MFCC mean | 20 | Average timbral character |
| MFCC std | 20 | Timbral variation over time |
| Chroma mean | 12 | Average harmonic content (key/pitch) |
| Spectral contrast mean | 7 | Brightness profile across frequency bands |
| **Total** | **59** | |

**Why mean + std for MFCCs:** The mean captures overall timbre; the std captures how
much the timbre changes over time. A track that is one synth loop for 3 minutes will
have low MFCC std. A track with distinct sections (intro, build, drop) will have higher
MFCC std. This directly addresses the "one loop for 3 minutes" problem.

### Approach B: Deep Learning Embeddings (essentia)

More powerful but heavier. Uses pre-trained models that learned music similarity from
millions of tracks.

**Discogs-EffNet** -- trained on Discogs metadata. The `multi_embeddings` variant
jointly optimizes for artist, label, release, and track similarity. Produces a 1280-dim
embedding vector per track.

**MAEST** (Music Audio Efficient Spectrogram Transformer) -- transformer-based model
that produces rich embeddings from 5-30 second audio windows.

```python
# Requires: pip install essentia-tensorflow
from essentia.standard import MonoLoader, TensorflowPredictEffnetDiscogs
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

def extract_effnet_embedding(audio_path):
    """Extract Discogs-EffNet embedding for similarity comparison."""
    audio = MonoLoader(filename=audio_path, sampleRate=16000)()

    model = TensorflowPredictEffnetDiscogs(
        graphFilename="discogs-effnet-bs1.pb",
        output="PartitionedCall:1"  # embedding layer
    )
    embeddings = model(audio)
    # Average over time frames to get single vector
    return np.mean(embeddings, axis=0)


def batch_similarity_effnet(audio_paths):
    """Pairwise similarity using deep embeddings."""
    embeddings = [extract_effnet_embedding(p) for p in audio_paths]
    matrix = cosine_similarity(embeddings)
    return matrix
```

**Pros over MFCC approach:**
- Captures higher-level musical concepts (genre, style, mood)
- More robust to surface-level differences (different key, slight tempo change)
- Trained on real music -- understands what "similar" means musically

**Cons:**
- Requires downloading model files (~80MB for EffNet, ~600MB for MAEST)
- Slower inference (still fast enough -- ~2s per track on CPU)
- AGPL license on essentia (fine for internal use)
- More complex setup

**Recommendation:** Start with MFCC approach (Approach A). It is simpler, lighter, and
likely sufficient for catching same-batch sameyness. If it misses cases where tracks
are structurally different but stylistically identical, add EffNet embeddings.

### Approach C: Timbral Variety Within a Single Track (librosa)

Separate from pairwise similarity -- this measures whether a single track has enough
internal variety or is just one loop repeated.

```python
def measure_timbral_variety(audio_path):
    """Measure how much timbral variety exists within a track."""
    y, sr = librosa.load(audio_path, sr=22050)

    # MFCCs over time
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)

    # Standard deviation across time for each coefficient
    # High std = lots of timbral change; low std = monotonous
    mfcc_temporal_std = np.std(mfccs, axis=1)
    variety_score = np.mean(mfcc_temporal_std)

    # Spectral centroid variance -- does the brightness change?
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
    centroid_cv = np.std(centroid) / (np.mean(centroid) + 1e-8)

    # Onset density -- how many events per second?
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units='time')
    duration = librosa.get_duration(y=y, sr=sr)
    onset_density = len(onsets) / duration if duration > 0 else 0

    return {
        'variety_score': float(variety_score),
        'centroid_cv': float(centroid_cv),     # coefficient of variation
        'onset_density': float(onset_density),  # events per second
        'num_onsets': len(onsets),
    }
```

**Interpreting results:**
| Metric | Low value means | High value means |
|--------|----------------|-----------------|
| `variety_score` | Same timbre throughout (one synth loop) | Rich timbral changes (sections, layering) |
| `centroid_cv` | Constant brightness (monotonous) | Brightness changes (builds, drops, transitions) |
| `onset_density` | Few events (ambient drone, sparse) | Many events (busy, rhythmic) |

**Note on onset_density:** Low onset density is not always bad -- ambient tracks are
intentionally sparse. Context matters. But if the prompt asked for "driving electronic"
and onset density is 0.5/sec, something is wrong.

### Approach D: Self-Similarity Matrix / Structure Detection (librosa)

Detect whether a track has actual musical structure (intro, build, climax, outro) or is
just one section repeated.

```python
def analyze_structure(audio_path):
    """Analyze track structure via self-similarity."""
    y, sr = librosa.load(audio_path, sr=22050)

    # Extract chroma features (captures harmonic content)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

    # Build recurrence (self-similarity) matrix
    # High values on diagonal = track repeating itself
    # Off-diagonal blocks = recurring sections
    rec = librosa.segment.recurrence_matrix(
        chroma, mode='affinity', metric='cosine', sym=True
    )

    # Structural segmentation via agglomerative clustering
    # Groups frames into k segments
    bounds = librosa.segment.agglomerative(chroma, k=6)
    bound_times = librosa.frames_to_time(bounds, sr=sr)

    # Measure structural complexity:
    # How different are consecutive segments?
    segment_features = []
    for i in range(len(bounds) - 1):
        seg = chroma[:, bounds[i]:bounds[i+1]]
        if seg.shape[1] > 0:
            segment_features.append(np.mean(seg, axis=1))

    if len(segment_features) > 1:
        seg_matrix = cosine_similarity(segment_features)
        # Average off-diagonal similarity -- lower = more varied sections
        n = seg_matrix.shape[0]
        off_diag = seg_matrix[np.triu_indices(n, k=1)]
        avg_section_similarity = float(np.mean(off_diag))
    else:
        avg_section_similarity = 1.0  # only one section = maximum repetition

    return {
        'num_segments': len(bounds) - 1,
        'segment_boundaries': bound_times.tolist(),
        'avg_section_similarity': avg_section_similarity,
        # 1.0 = all sections sound the same (looped)
        # lower = more structural variety
    }
```

**When to use:** This is the most direct detector for "one loop repeated for 3 minutes."
If `avg_section_similarity > 0.92`, the track is essentially one section looped.

---

## Problem 2: Truncated Track Detection

### Check 1: Duration Threshold

Simple but essential. Suno hard-caps at ~8 minutes.

```python
def check_duration(audio_path, warn_threshold=470, danger_threshold=475):
    """Flag tracks that are suspiciously close to Suno's 8-minute limit."""
    y, sr = librosa.load(audio_path, sr=22050)
    duration = librosa.get_duration(y=y, sr=sr)

    status = 'ok'
    if duration >= danger_threshold:  # 7:55+
        status = 'likely_truncated'
    elif duration >= warn_threshold:  # 7:50+
        status = 'warning'

    return {
        'duration_seconds': float(duration),
        'duration_display': f"{int(duration // 60)}:{int(duration % 60):02d}",
        'status': status,
    }
```

### Check 2: Abrupt Ending Detection (librosa -- RMS Energy)

Analyze the final seconds. A natural ending fades out or resolves to silence gradually.
A truncation is a sudden drop from full energy to nothing.

```python
def detect_abrupt_ending(audio_path):
    """Detect if audio ends abruptly (truncation) vs natural fade/resolution."""
    y, sr = librosa.load(audio_path, sr=22050)
    duration = librosa.get_duration(y=y, sr=sr)

    # Compute RMS energy for the whole track
    rms = librosa.feature.rms(y=y, hop_length=512)[0]
    times = librosa.frames_to_time(range(len(rms)), sr=sr, hop_length=512)

    # Average RMS of the track body (skip first/last 10%)
    body_start = int(len(rms) * 0.1)
    body_end = int(len(rms) * 0.9)
    body_rms = np.mean(rms[body_start:body_end])

    # RMS of the last 2 seconds
    last_2s_start = np.searchsorted(times, duration - 2.0)
    last_2s_rms = rms[last_2s_start:]

    if len(last_2s_rms) < 4:
        return {'truncated': False, 'confidence': 0, 'reason': 'track too short'}

    # RMS of the very last 500ms
    last_500ms_start = np.searchsorted(times, duration - 0.5)
    last_500ms_rms = rms[last_500ms_start:]

    # RMS of 2s-to-0.5s-before-end window
    pre_end_rms = rms[last_2s_start:last_500ms_start]

    if len(pre_end_rms) == 0 or len(last_500ms_rms) == 0:
        return {'truncated': False, 'confidence': 0, 'reason': 'insufficient data'}

    avg_pre_end = np.mean(pre_end_rms)
    avg_last_500ms = np.mean(last_500ms_rms)

    # Key metric: ratio of final 500ms energy to pre-end energy
    # Natural fade: ratio drops gradually (0.3-0.7)
    # Natural resolution: ratio is moderate (0.2-0.5)
    # Abrupt cut: ratio is high (>0.7) -- still loud, then nothing
    # Silent ending: ratio is very low (<0.1) -- already faded

    if avg_pre_end < body_rms * 0.1:
        # Already very quiet -- natural fade or silence
        return {
            'truncated': False,
            'confidence': 0.8,
            'reason': 'natural_fade',
            'final_energy_ratio': float(avg_last_500ms / (body_rms + 1e-8)),
        }

    energy_ratio = avg_last_500ms / (avg_pre_end + 1e-8)

    # Also check: does the last frame have significant energy?
    final_frame_energy = rms[-1] / (body_rms + 1e-8)

    truncated = energy_ratio > 0.7 and final_frame_energy > 0.3
    confidence = min(1.0, energy_ratio * final_frame_energy * 2)

    return {
        'truncated': truncated,
        'confidence': float(confidence),
        'reason': 'abrupt_cutoff' if truncated else 'natural_ending',
        'energy_ratio': float(energy_ratio),
        'final_frame_energy': float(final_frame_energy),
        'body_rms': float(body_rms),
    }
```

**Key insight:** In a truncated track, the audio is still at normal volume in the very
last frame. In a natural ending, the energy tapers off. We check two things:
1. Is the energy in the last 500ms still close to the energy at 2s-before-end?
2. Is the very last frame still loud relative to the track body?

If both are true, the track was chopped.

### Check 3: Zero-Crossing Rate in Final Segment (librosa)

Complementary signal. A natural ending resolves harmonically (lower ZCR as the sound
decays). A truncation cuts mid-waveform (ZCR stays high until the last sample).

```python
def check_final_zcr(audio_path):
    """Check zero-crossing rate in final segment for truncation signs."""
    y, sr = librosa.load(audio_path, sr=22050)
    duration = librosa.get_duration(y=y, sr=sr)

    # Last 1 second of audio
    last_1s = y[int((duration - 1.0) * sr):]

    # Split into 4 quarter-second chunks
    chunk_size = len(last_1s) // 4
    chunks = [last_1s[i*chunk_size:(i+1)*chunk_size] for i in range(4)]

    zcr_values = [
        float(np.mean(librosa.feature.zero_crossing_rate(y=c)))
        for c in chunks if len(c) > 0
    ]

    # In a natural fade, ZCR typically decreases in the final chunks
    # In a truncation, ZCR stays roughly constant until abrupt stop
    if len(zcr_values) >= 3:
        trend = zcr_values[-1] - zcr_values[0]  # negative = fading, positive = still active
    else:
        trend = 0

    return {
        'final_zcr_values': zcr_values,
        'zcr_trend': float(trend),
        'suggests_truncation': trend > 0,
    }
```

### Check 4: Essentia FadeDetection (essentia)

Essentia has a dedicated FadeDetection algorithm that analyzes RMS over time to find
fade-in/fade-out regions. If a track near 8 minutes has no detected fade-out, that is
suspicious.

```python
import essentia.standard as es

def check_fade_detection(audio_path):
    """Use Essentia's FadeDetection to check for proper fade-out."""
    audio = es.MonoLoader(filename=audio_path, sampleRate=44100)()

    fade = es.FadeDetection(
        minLength=1.5,    # minimum 1.5s to count as a fade
        cutoffHigh=0.85,
        cutoffLow=0.2,
    )
    fade_in, fade_out = fade(audio)

    duration = len(audio) / 44100.0
    has_fade_out = len(fade_out) > 0

    # Check if any fade-out starts in the last 10 seconds
    late_fade = any(
        fo[0] > duration - 10.0
        for fo in fade_out
    ) if has_fade_out else False

    return {
        'has_fade_out': has_fade_out,
        'late_fade_out': late_fade,
        'fade_outs': fade_out.tolist() if has_fade_out else [],
        'duration': float(duration),
    }
```

### Combined Truncation Detector

```python
def is_truncated(audio_path):
    """Combined truncation detection using multiple signals."""
    dur = check_duration(audio_path)
    ending = detect_abrupt_ending(audio_path)

    signals = []

    # Signal 1: Duration near limit
    if dur['status'] == 'likely_truncated':
        signals.append(('duration', 0.8))
    elif dur['status'] == 'warning':
        signals.append(('duration', 0.4))

    # Signal 2: Abrupt ending
    if ending['truncated']:
        signals.append(('abrupt_ending', ending['confidence']))

    # Combined verdict
    if not signals:
        return {'truncated': False, 'signals': []}

    max_confidence = max(s[1] for s in signals)
    # Both duration AND abrupt ending = very confident
    combined = min(1.0, sum(s[1] for s in signals))

    return {
        'truncated': combined > 0.6,
        'confidence': float(combined),
        'signals': signals,
        'duration': dur,
        'ending': ending,
    }
```

---

## Problem 3: Better Audio Evaluation

### Enhancement A: Gemini Multi-Track Comparison

Gemini can accept multiple audio files in a single prompt. We can upload two tracks and
ask for a comparative analysis. Cost: ~$0.008 for comparing two 4-minute tracks (each
track is ~32 tokens/sec * 240 sec = 7,680 tokens).

```python
def compare_tracks_gemini(audio_path_a, audio_path_b, client):
    """Ask Gemini to compare two tracks for similarity."""
    file_a = client.files.upload(file=open(audio_path_a, 'rb'),
                                  config={"mime_type": "audio/mp4"})
    file_b = client.files.upload(file=open(audio_path_b, 'rb'),
                                  config={"mime_type": "audio/mp4"})

    prompt = """You are comparing two AI-generated music tracks.

Listen to BOTH tracks carefully and evaluate:

1. OVERALL SIMILARITY: How similar do these tracks sound? (1=completely different,
   5=nearly identical)
2. TIMBRAL SIMILARITY: Do they use similar synth sounds/patches? (1-5)
3. STRUCTURAL SIMILARITY: Do they follow the same energy curve/arrangement? (1-5)
4. HARMONIC SIMILARITY: Similar keys, chord progressions, scales? (1-5)
5. RHYTHMIC SIMILARITY: Similar tempo, beat patterns, groove? (1-5)

Respond ONLY with valid JSON:
{
  "overall_similarity": 1-5,
  "timbral_similarity": 1-5,
  "structural_similarity": 1-5,
  "harmonic_similarity": 1-5,
  "rhythmic_similarity": 1-5,
  "notes": "What specifically makes them similar or different?"
}"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt, file_a, file_b],
    )
    # ... parse JSON response ...
```

**Limitations:**
- Total audio must be under 9.5 hours combined (not an issue for us)
- Cost scales with number of comparisons: N tracks = N*(N-1)/2 pairs
  - 6 tracks (one batch) = 15 comparisons = ~$0.12
  - 20 tracks = 190 comparisons = ~$1.52
- For large batches, use librosa MFCC similarity first as a pre-filter, then send
  only high-similarity pairs to Gemini for confirmation.

### Enhancement B: Gemini Truncation Detection

Add a specific truncation check to the existing Gemini eval prompt.

```
Additional addition to existing evaluate_track() prompt:

6. ENDING QUALITY: Does the track end naturally (fade out, musical resolution,
   intentional silence) or does it cut off abruptly mid-phrase? If it cuts off,
   does it sound like the track was truncated/cropped?
   Answer: "natural" / "abrupt" / "truncated" with explanation.
```

This is cheap (no additional audio upload -- just extend the existing prompt) and
Gemini is quite good at hearing abrupt endings.

### Enhancement C: Gemini "Generic Stock Music" Detection

Add to the existing Gemini eval:

```
Additional evaluation criterion:

7. ORIGINALITY: Does this sound like generic royalty-free stock music, or does it have
   distinctive character? Consider: Are the synth patches and sounds unique or are they
   default presets? Is the arrangement predictable or surprising? Would you remember
   this track after hearing it once?
   Rate 1-5 (1=very generic, 5=highly distinctive).
```

### Enhancement D: Spectral Quality Metrics (librosa)

Quantitative metrics that complement Gemini's subjective evaluation.

```python
def compute_quality_metrics(audio_path):
    """Compute objective audio quality metrics."""
    y, sr = librosa.load(audio_path, sr=22050)

    # 1. Dynamic range (difference between loud and quiet parts in dB)
    rms = librosa.feature.rms(y=y)[0]
    rms_db = librosa.amplitude_to_db(rms)
    dynamic_range = float(np.percentile(rms_db, 95) - np.percentile(rms_db, 5))

    # 2. Spectral flatness (mean) -- how "noisy" vs "tonal"
    flatness = librosa.feature.spectral_flatness(y=y)[0]
    mean_flatness = float(np.mean(flatness))
    # 0.0 = pure tone, 1.0 = white noise
    # Typical music: 0.01-0.15. Above 0.3 = very noisy/artifact-heavy

    # 3. Spectral centroid statistics -- brightness and its variation
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    centroid_mean = float(np.mean(centroid))
    centroid_std = float(np.std(centroid))

    # 4. Onset density
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units='time')
    duration = librosa.get_duration(y=y, sr=sr)
    onset_density = len(onsets) / duration if duration > 0 else 0

    # 5. Tempo stability
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    if len(beats) > 2:
        beat_times = librosa.frames_to_time(beats, sr=sr)
        ibis = np.diff(beat_times)  # inter-beat intervals
        tempo_stability = 1.0 - float(np.std(ibis) / (np.mean(ibis) + 1e-8))
    else:
        tempo_stability = 0.0

    return {
        'dynamic_range_db': dynamic_range,
        'spectral_flatness': mean_flatness,
        'spectral_centroid_mean': centroid_mean,
        'spectral_centroid_std': centroid_std,
        'onset_density': float(onset_density),
        'estimated_tempo': float(tempo) if np.isscalar(tempo) else float(tempo[0]),
        'tempo_stability': tempo_stability,
        'duration': float(duration),
    }
```

**Interpreting quality metrics:**
| Metric | Red flag value | What it means |
|--------|---------------|---------------|
| `dynamic_range_db` < 6 | Overly compressed / flat dynamics |
| `spectral_flatness` > 0.3 | Too noisy, possible artifacts |
| `centroid_std` < 200 | Brightness never changes (monotonous) |
| `onset_density` < 0.3 | Very sparse (could be fine for ambient) |
| `tempo_stability` < 0.7 | Tempo is unstable (could indicate artifacts) |

### Enhancement E: Essentia DynamicComplexity

Essentia has a dedicated DynamicComplexity algorithm that quantifies loudness
fluctuations -- a direct measure of whether a track has dynamic movement or is just
a flat wall of sound.

```python
import essentia.standard as es

def measure_dynamic_complexity(audio_path):
    """Measure dynamic complexity using Essentia."""
    audio = es.MonoLoader(filename=audio_path, sampleRate=44100)()
    dc = es.DynamicComplexity()
    complexity, loudness = dc(audio)

    return {
        'dynamic_complexity': float(complexity),
        'loudness_db': float(loudness),
        # Higher complexity = more dynamic variation
        # Typical values: 2-8 for pop/electronic, <2 for static/droning
    }
```

---

## Recommended Stack

### Tier 1: Must Have (librosa only)

Install: `pip install librosa scikit-learn`

Covers:
- Pairwise track similarity via MFCC + chroma + spectral contrast embeddings
- Timbral variety measurement within a track
- Truncation detection via RMS energy analysis
- Onset density, spectral flatness, dynamic range
- Self-similarity matrix for structure detection
- Zero-crossing rate for ending analysis

**This is sufficient to solve all three problems.** Start here.

### Tier 2: Nice to Have (add essentia)

Install: `pip install essentia`

Adds:
- FadeDetection algorithm (cleaner truncation detection)
- DynamicComplexity (better dynamic range measurement)
- MusicExtractor (bulk feature extraction with 100+ features)
- Pre-trained classifiers for mood, genre, voice/instrumental

### Tier 3: Advanced (add essentia-tensorflow)

Install: `pip install essentia-tensorflow`

Adds:
- Discogs-EffNet embeddings for music similarity (better than MFCCs)
- MAEST transformer embeddings
- Genre classifiers trained on 400+ categories

Only needed if MFCC-based similarity proves insufficient.

### Gemini Enhancements (no new dependencies)

Extend existing `lib/gemini_audio.py`:
- Add truncation detection to the evaluation prompt (free -- just extend text)
- Add originality/generic detection criterion (free)
- Add multi-track comparison function for flagged pairs (~$0.008 per pair)

---

## Pipeline Integration Plan

### Where It Fits

```
[Suno Generate] -> [Download M4A] -> [NEW: Audio Analysis] -> [Gemini Eval] -> [User Review]
                                            |
                                            v
                                   lib/audio_analysis.py
                                   - truncation_check()
                                   - quality_metrics()
                                   - batch_similarity()
```

### Post-Download Analysis (runs on every track)

1. **Duration check** -- instant, flag anything >= 7:50
2. **Truncation detection** -- RMS energy analysis of final 2s (~0.5s per track)
3. **Quality metrics** -- spectral flatness, onset density, dynamic range (~1s per track)
4. **Timbral variety** -- MFCC temporal std, centroid CV (~0.5s per track)

Total per track: ~2 seconds. For a batch of 10 tracks: ~20 seconds.

### Batch Similarity (runs after all tracks in a batch are downloaded)

1. **Extract embeddings** -- MFCC/chroma/contrast vectors (~1s per track)
2. **Compute pairwise similarity** -- cosine similarity matrix (instant for 20 tracks)
3. **Flag high-similarity pairs** -- threshold > 0.95
4. **(Optional)** Send flagged pairs to Gemini for detailed comparison

Total for 10-track batch: ~12 seconds + optional Gemini calls.

### Enhanced Gemini Eval (extend existing prompt)

Add to `lib/gemini_audio.py` `evaluate_track()` prompt:
- Ending quality check (natural/abrupt/truncated)
- Originality rating (1-5, is this generic stock music?)
- No additional cost -- same API call, just a longer prompt.

### New Function: `compare_tracks_gemini()`

Add to `lib/gemini_audio.py`:
- Upload two audio files, ask for similarity assessment
- Only called for pairs flagged by MFCC similarity pre-filter
- Cost: ~$0.008 per comparison

### Output Format

The analysis results should be saved alongside the Gemini eval results, either as
additional fields in the same JSON or as a separate `_analysis.json` per track:

```json
{
  "truncation": {
    "truncated": false,
    "confidence": 0.1,
    "duration_seconds": 237.5,
    "ending_type": "natural_fade"
  },
  "quality": {
    "dynamic_range_db": 12.3,
    "spectral_flatness": 0.08,
    "onset_density": 2.1,
    "timbral_variety": 4.7,
    "centroid_cv": 0.35
  },
  "similarity": {
    "most_similar_track": "20260226_glass_tide__abc123.m4a",
    "similarity_score": 0.87,
    "flagged": false
  }
}
```

---

## Feature Reference Quick Table

| Feature | Library | API Call | What It Tells Us |
|---------|---------|----------|-----------------|
| MFCC (mean) | librosa | `librosa.feature.mfcc(y, sr, n_mfcc=20)` | Timbral character (for similarity) |
| MFCC (std over time) | librosa | `np.std(mfccs, axis=1)` | Timbral variety (monotonous vs varied) |
| Chroma CENS | librosa | `librosa.feature.chroma_cens(y, sr)` | Harmonic content / key |
| Spectral contrast | librosa | `librosa.feature.spectral_contrast(y, sr)` | Tonal vs noisy, brightness profile |
| Spectral flatness | librosa | `librosa.feature.spectral_flatness(y)` | Noise-like (1.0) vs tonal (0.0) |
| Spectral centroid | librosa | `librosa.feature.spectral_centroid(y, sr)` | Average brightness |
| RMS energy | librosa | `librosa.feature.rms(y)` | Loudness per frame (for truncation) |
| Zero-crossing rate | librosa | `librosa.feature.zero_crossing_rate(y)` | Waveform activity (for truncation) |
| Onset detection | librosa | `librosa.onset.onset_detect(y, sr, units='time')` | Event density |
| Beat tracking | librosa | `librosa.beat.beat_track(y, sr)` | Tempo and tempo stability |
| Self-similarity | librosa | `librosa.segment.recurrence_matrix(data, mode='affinity')` | Track structure |
| Cross-similarity | librosa | `librosa.segment.cross_similarity(data, ref)` | Inter-track similarity |
| Structural segments | librosa | `librosa.segment.agglomerative(data, k=6)` | Section boundaries |
| FadeDetection | essentia | `es.FadeDetection()(audio)` | Fade-in/fade-out detection |
| DynamicComplexity | essentia | `es.DynamicComplexity()(audio)` | Loudness variation |
| NoveltyCurve | essentia | `es.NoveltyCurve()(bands)` | Novelty/change over time |
| Discogs-EffNet | essentia-tf | `TensorflowPredictEffnetDiscogs()(audio)` | Deep music embeddings |

---

## Cost Summary

| Component | Cost | Notes |
|-----------|------|-------|
| librosa analysis (per track) | $0 | Local computation, ~2s |
| librosa batch similarity (10 tracks) | $0 | Local computation, ~12s |
| essentia analysis (per track) | $0 | Local computation, ~2s |
| Gemini eval (existing, per track) | ~$0.004 | Already in pipeline |
| Gemini comparison (per pair) | ~$0.008 | Only for flagged pairs |
| Gemini eval with extended prompt | ~$0.005 | Slight increase from more output tokens |

For a typical 10-track batch: ~$0.05 Gemini + $0 local analysis = ~$0.05 total.
