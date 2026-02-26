# Suno AI Prompting Research

Best practices and pitfalls for Suno AI music generation, compiled from community testing (r/SunoAI, Discord), wiki resources (sunoaiwiki.com, openmusicprompt.com), dedicated guides (howtopromptsuno.com, hookgenius.app, skywork.ai, yeb.to), and Suno's own help documentation. Focused on our pipeline's specific problems.

Last updated: Feb 2026. Applicable to Suno v5 (chirp-crow).

---

## Table of Contents

1. [Problem 1: Generic-Sounding Electronic/Ambient Tracks](#problem-1-generic-sounding-electronicambient-tracks)
2. [Problem 2: Tracks That Sound Identical in a Batch](#problem-2-tracks-that-sound-identical-in-a-batch)
3. [Problem 3: Truncation at 8 Minutes](#problem-3-truncation-at-8-minutes)
4. [Problem 4: Vocal Delivery Issues](#problem-4-vocal-delivery-issues)
5. [Style Tags Field: Mechanics and Best Practices](#style-tags-field-mechanics-and-best-practices)
6. [Lyrics Metatags: How They Work](#lyrics-metatags-how-they-work)
7. [BPM Tags: Do They Actually Work?](#bpm-tags-do-they-actually-work)
8. [Negative Tags: Do They Reliably Prevent Things?](#negative-tags-do-they-reliably-prevent-things)
9. [Instrumental Toggle vs Instrumental Tag](#instrumental-toggle-vs-instrumental-tag)
10. [Artist References in Tags](#artist-references-in-tags)
11. [Suno v5 vs v4 Prompting Differences](#suno-v5-vs-v4-prompting-differences)
12. [Actionable Recommendations for Our Pipeline](#actionable-recommendations-for-our-pipeline)

---

## Problem 1: Generic-Sounding Electronic/Ambient Tracks

### The Root Cause

When Suno receives vague electronic tags like `"synthwave, electronic, atmospheric"`, it defaults to the most common patterns in its training data. The result: cookie-cutter stock music with predictable progressions, generic pad sounds, and no distinguishing character.

Community consensus (HookGenius, ChangelyricGuide, multiple Reddit threads): **specificity is the single most important factor** in avoiding generic output. Broad genre terms activate Suno's "safest" interpretation.

### Strategies That Produce Distinctive Results

#### 1. Use Specific Subgenres, Not Parent Genres

Replace broad terms with narrow subgenres that carry stronger sonic identity:

| Generic (avoid) | Specific (use instead) |
|-----------------|----------------------|
| `electronic` | `Berlin school, kosmische, sequencer-driven` |
| `ambient` | `dark ambient, microsound, fourth world, isolationist` |
| `synthwave` | `darksynth, outrun, Italo-futurism, coldwave` |
| `atmospheric` | `hauntological, spectral, vaporous drift` |
| `IDM` | `glitch, braindance, post-digital, granular` |
| `downtempo` | `psybient, trip-hop, dub techno, abstract hip-hop` |
| `electronic ambient` | `tape loop drone, modular synthesis, processed field recordings` |

#### 2. Describe Sonic Texture, Not Just Genre

Sensory language guides Suno's interpretation far more than genre labels alone:

- `"warm analog synths, dusty vinyl crackle, tape saturation"` -- not just `"lo-fi"`
- `"crystalline digital bells, granular cloud textures, ice-cold reverb tails"` -- not just `"ambient electronic"`
- `"heavy sub-bass pressure, industrial machinery rhythms, corroded metal textures"` -- not just `"dark electronic"`
- `"foggy shoreline field recordings, distant foghorn drones, salt-weathered piano"` -- not just `"atmospheric"`

The openmusicprompt.com guide calls this the **"Sonic Texture" strategy**: use sensory language that evokes physical qualities rather than abstract categories.

#### 3. Reference Production Eras and Techniques

Production descriptors anchor the sound to a specific aesthetic:

- `"late 90s trip-hop production, downtempo breakbeats, filtered vinyl samples"`
- `"early 80s BBC Radiophonic Workshop, oscillator drones, ring-modulated textures"`
- `"bedroom-produced lo-fi, cassette four-track warmth, accidental noise"`
- `"pristine Warp Records digital clarity, microsound clicks, sterile precision"`

#### 4. Name Specific Instruments and Synthesis Methods

Generic `"synth"` produces generic synth sounds. Be precise:

| Generic | Specific |
|---------|----------|
| `synth` | `Moog bass, Juno-106 pads, Prophet-5 brass, TB-303 acid line` |
| `drums` | `Roland TR-808, LinnDrum, hand percussion, processed room mics` |
| `piano` | `prepared piano, Fender Rhodes, tack piano, honky-tonk upright` |
| `guitar` | `e-bow sustained guitar, reverse-delay guitar, microtonal guitar` |
| `bass` | `fretless bass, dub bass, detuned sub-bass, picked Rickenbacker` |

#### 5. Combine Unexpected Elements

Genre-blending pushes Suno out of default patterns:

- `"Balinese gamelan meets Berlin techno, metallic percussion, hypnotic polyrhythm"`
- `"Appalachian dulcimer drone, synthesizer swells, post-rock dynamics"`
- `"North African Gnawa bass, industrial noise, trance-inducing repetition"`

The changelyric.com guide emphasizes: **"Mix unexpected genres to push into less predictable territory."**

---

## Problem 2: Tracks That Sound Identical in a Batch

### Why It Happens

Suno generates two clips per request. With similar prompts, the model gravitates toward the same synth patches, chord progressions, and arrangements. Community reports confirm this is "VERY possible and somewhat likely" -- users frequently get eerily similar melodies across generations.

The core issue: Suno has limited sonic variety within its latent space for any given prompt configuration. Similar inputs produce similar traversals through that space.

### Strategies to Force Variety

#### 1. Vary the Dominant Genre Tag (Position 1)

Since the first tag carries the most weight (~50% reduction per subsequent position per community observation), changing just the lead tag produces the most dramatic sonic shift:

```
Track 1: "dark ambient, synthesizer drones, cavernous reverb, slow decay"
Track 2: "tape loop drone, synthesizer drones, cavernous reverb, slow decay"
Track 3: "microsound, synthesizer drones, cavernous reverb, slow decay"
```

Same supporting tags, different lead genre = different sonic palette.

#### 2. Vary BPM and Tempo Descriptors

Even though BPM tags are imprecise (see section below), combining them with tempo descriptors nudges variety:

```
Track 1: "...glacial, barely moving, 60 BPM"
Track 2: "...mid-tempo pulse, hypnotic, 100 BPM"
Track 3: "...driving, relentless, 140 BPM"
```

#### 3. Vary Key Instruments

Swap the lead instrument/texture between tracks:

```
Track 1: "...Moog bass leads, analog warmth"
Track 2: "...prepared piano, acoustic resonance"
Track 3: "...processed cello, bowed metal"
```

#### 4. Vary Production Era/Aesthetic

```
Track 1: "...70s Tangerine Dream, vintage analog"
Track 2: "...2020s Oneohtrix Point Never, digital maximal"
Track 3: "...90s The Orb, dub-influenced, echo chamber"
```

#### 5. Use Different Lyrics Metatag Structures

For instrumental tracks, the metatag structure in the lyrics field still affects arrangement:

```
Track 1: [Intro] [Slow Build] [Main Theme] [Deconstruction] [Fade]
Track 2: [Cold Open] [Loop A] [Loop B] [Collision] [Silence] [Reprise]
Track 3: [Drone] [Texture Layer] [Pulse Emerges] [Crescendo] [Dissolve]
```

Different section names = different structural interpretation = different arrangement.

#### 6. Personas (v5 Feature)

Suno v5 supports Personas -- saved vocal/energy profiles from existing tracks. For instrumental work, uploading a reference audio clip as a Persona can anchor the sonic palette to a specific sound. This is the strongest variety lever for batches of similar genre.

#### 7. Generate More, Select Best

Community consensus: generate 4-6 versions per prompt concept. "Later generations often capture what earlier ones missed." Treat generation as exploratory, not one-shot.

---

## Problem 3: Truncation at 8 Minutes

### Hard Limits by Version

| Model | Max Length |
|-------|-----------|
| V2 | 1:20 |
| V3 | 2:00 |
| V3.5 / V4 | 4:00 |
| V4.5 / V5 | 8:00 |

Source: help.suno.com/en/articles/2409473

The 8-minute cap on v5 is absolute. Tracks that hit 7:59 get abruptly cut off, often mid-phrase, with poor endings and potential audio artifacts.

### What Causes Tracks to Run Long

1. **Too many sections in lyrics metatags** -- each `[Verse]`, `[Chorus]`, `[Bridge]` adds time. More sections = longer track = higher truncation risk.
2. **Slow tempo + many sections** -- a 60 BPM track with 8 sections will be much longer than a 140 BPM track with 8 sections.
3. **Verbose lyrics** -- more words per section means longer sections, especially at slow tempos.
4. **Instrumental sections without lyrics** -- `[Instrumental Break]` or `[Guitar Solo]` tags can generate surprisingly long sections since the model has no lyrics to constrain duration.

### Strategies to Avoid Truncation

1. **Plan for shorter than 8 minutes** -- target 6-7 minutes max to leave buffer.
2. **Limit section count** -- 8-10 sections for a 4-minute track, 12-14 for a 6-minute track. Each section averages 20-40 seconds.
3. **Include explicit `[Outro]` or `[Outro: Fade out]`** -- gives the model a clear ending signal rather than letting it wander.
4. **Use `[End]` or `[Fade Out]` as final metatag** -- community reports these help signal termination.
5. **For instrumental tracks**: use fewer, longer section labels rather than many short ones. `[Movement 1]` through `[Movement 3]` instead of eight separate sections.
6. **Use the Extend feature** for tracks that need to be longer than 8 minutes -- generate the core track at 6-7 minutes, then extend with additional sections.

### Community Workaround for Long Compositions

Reddit users report a reliable pattern for tracks that must exceed 8 minutes:
- Generate the first 6-7 minutes with a clean ending point
- Use the Extend feature to add the remaining sections
- Stitch in post-production if the extend doesn't flow naturally

---

## Problem 4: Vocal Delivery Issues

### The Polished/Generic Problem

Suno's default vocal model produces clean, polished, radio-ready vocals. When you want raw, gritty, or idiosyncratic delivery (like our Pinned Under Glass problem), standard tags often get overridden by the model's preference for "nice" singing.

### Tag Placement Strategy for Vocal Character

Community research (r/SunoAI "Character Prompt" method, openmusicprompt.com "Layered Persona" strategy) identifies a three-layer approach:

#### Layer 1: Style Tags (Global Identity)

Position vocal descriptors **first** in the style tag string. Suno weights by position.

```
GOOD:  "raw gritty male baritone, unpolished garage recording, post-punk, angular guitars"
BAD:   "post-punk, angular guitars, male vocals"
```

The vocal identity must come before genre tags. In the BAD example, `post-punk` dominates and the vocal character is diluted.

#### Layer 2: Lyrics Metatags (Section Reinforcement)

Reinforce the global style with section-specific metatags:

```
[Verse 1] [Raspy, strained delivery]
These walls keep pushing closer every night...

[Chorus] [Shouting, desperate intensity]
I can't breathe under all this glass!

[Bridge] [Whispered, barely audible]
Maybe if I stop moving...
```

Community reports 70-90% success rate when Style tags and Lyrics metatags reinforce each other.

#### Layer 3: Character Context (Advanced)

The "Character Prompt" method (from r/SunoAI advanced techniques): instead of keyword-only descriptions, write mini-biographies that place the singer in a context:

```
Style: "weathered voice singing from a dimly lit garage, raw unprocessed vocals
recorded on a cheap microphone, post-punk frustration, angular guitars, 90 BPM"
```

This approach ("write literal stories in your tags") produces more distinctive vocal character than keyword lists because it activates narrative associations in the model.

#### Pipe Delimiter Stacking

Metatags support pipe-delimited compound instructions:

```
[Chorus | anthemic chorus | stacked harmonies | belt to breaking point]
[Verse | hushed confession | close-mic intimacy | cracking voice]
```

This concentrates multiple vocal directives on a single section.

### Specific Tags for Raw/Gritty vs Polished

| Want Raw/Gritty | Use These Tags |
|----------------|----------------|
| Rough texture | `raspy, gravelly, gritty, weathered, sandpaper voice` |
| Low production value | `lo-fi recording, room mic, garage recording, unpolished` |
| Emotional exposure | `raw, anguished, vulnerable, voice cracking, strained` |
| Aggressive delivery | `shouting, growling, snarling, punk delivery, screaming` |

| Want to Avoid | Negative Tags |
|---------------|---------------|
| Over-polished | `smooth, polished, pristine, studio-quality, auto-tune` |
| Too-clean production | `pop production, radio-ready, overproduced` |

### Production Context Matters

Vocal delivery is heavily influenced by production/genre tags. A `"raw gritty male vocals"` tag paired with `"pop, modern production"` will still trend polished. Pair raw vocal descriptors with raw production descriptors:

```
GOOD: "raw gritty male baritone, lo-fi garage recording, punk, distorted, 4-track cassette"
BAD:  "raw gritty male baritone, pop, clean production, modern"
```

---

## Style Tags Field: Mechanics and Best Practices

### Character Limit

- Pre-2025: 120 characters
- 2025+: **1,000 characters** (current as of v5)

Despite the increased limit, community consensus: shorter is better. Quality over quantity.

### Tag Ordering (Critical)

**The first tag carries the greatest weight.** Community observation suggests roughly 50% weight reduction per position, though Suno hasn't confirmed exact mechanics.

```
Position 1: ~100% influence (dominant character)
Position 2: ~50% influence
Position 3: ~25% influence
Position 4+: diminishing returns
```

**Implication**: Put the single most important descriptor first. If vocal character matters most, lead with it. If genre matters most, lead with genre.

Recommended order:
```
[vocal character], [primary genre/subgenre], [secondary genre], [instrumentation], [mood/atmosphere], [production style], [tempo]
```

For instrumental tracks:
```
[primary genre/subgenre], [secondary genre], [lead instrument/texture], [production style], [mood/atmosphere], [tempo]
```

### Optimal Tag Count

| Tag Count | Effect |
|-----------|--------|
| 1-2 | Too sparse; model fills in generic defaults |
| 3-5 | **Sweet spot.** Clear direction without dilution |
| 6-8 | Acceptable but influence of later tags is weak |
| 9+ | Diminishing returns; tags compete and confuse the model |

HookGenius specifically recommends: "Three to five well-chosen tags outperform ten scattered ones."

### Effective Tag String Length

Our current pipeline targets 120-200 characters (from `suno-vocal-prompting.md`). With the new 1,000-char limit, we have room to be more descriptive, but the **effective processing window** for Suno is still concentrated in the first ~200 characters. Additional characters are read but carry less weight.

**Recommendation**: 150-300 characters. Long enough to be specific, short enough to avoid dilution.

### Syntax

- Comma-separated values
- No quotation marks or brackets needed in the style field
- Case-insensitive (`Rock` = `rock`)
- Multi-word terms as continuous phrases: `Lo fi`, `Hip hop`, `Dark ambient`

### What Makes Tags "Work"

Tags that correspond to well-represented concepts in Suno's training data produce the most reliable results. Mainstream genres (rock, pop, jazz) are highly reliable. Niche subgenres (kosmische, zeuhl, hauntology) may work but with less consistency.

**Tip**: When using niche terms, pair with a mainstream parent genre as backup: `"kosmische, electronic, sequencer-driven, Berlin school"` -- if Suno doesn't recognize `kosmische`, the supporting tags still guide it.

---

## Lyrics Metatags: How They Work

### Syntax

Metatags are bracketed instructions placed in the **lyrics field** (not the style field):

```
[Section Name]
[Section Name: Modifier]
[Section Name | modifier 1 | modifier 2]
[Effect or Instruction]
```

### Core Structural Tags

These reliably define song sections:

| Tag | Function |
|-----|----------|
| `[Intro]` | Opening section, sets atmosphere |
| `[Verse 1]`, `[Verse 2]` | Narrative/storytelling sections |
| `[Pre-Chorus]` | Tension builder before hook |
| `[Chorus]` | Main hook, energy peak |
| `[Bridge]` | Emotional/stylistic pivot |
| `[Outro]` | Closing section |
| `[Interlude]` | Musical break between sections |
| `[End]` | Signals track termination |

### Instrumental/Performance Tags

| Tag | Function |
|-----|----------|
| `[Instrumental]` | Purely instrumental section (no vocals) |
| `[Instrumental Break]` | Brief instrumental interlude |
| `[Guitar Solo]` | Self-explanatory |
| `[Synthesizer Solo]` | Electronic lead break |
| `[Piano Solo]` | Piano feature section |
| `[Drum Break]` | Percussion feature |
| `[Build]` or `[Build-up]` | Tension/energy increase |
| `[Drop]` | Energy release (EDM convention) |
| `[Break]` | Energy decrease, stripping back |
| `[Fade Out]` | Gradual volume decrease |

### Vocal Modifier Tags

| Tag | Effect |
|-----|--------|
| `[Whispered]` | Soft, intimate near-speaking |
| `[Spoken Word]` | Non-melodic speech |
| `[Falsetto]` | High head voice |
| `[Belting]` | Loud, powerful chest voice |
| `[Shout]` / `[Shouting]` | Forceful projection |
| `[Raspy]` | Rough texture |
| `[Breathy]` | Airy, intimate |
| `[Growling]` | Aggressive low vocalization |
| `[Screaming]` | Extreme metal vocals |
| `[Narration]` | Narrator-style delivery |
| `[Harmony]` | Multi-part vocal harmony |
| `[Vocal Ad-libs]` | Scattered interjections |
| `[Choir: Gospel]` | Rich backing vocals |
| `[Voice: Auto-tune]` | Modern vocal processing effect |

### Modifier Syntax

Tags can be modified with colons or pipes:

```
[Intro: Acoustic guitar]           -- instrument-specific intro
[Outro: Fade out]                  -- ending style
[Outro: Big finish]                -- ending style
[Verse | hushed, intimate]         -- delivery modifiers via pipe
[Chorus | anthemic | stacked harmonies]  -- multiple modifiers
```

### Mood/Atmosphere Metatags

| Tag | Effect |
|-----|--------|
| `[Mood: Euphoric]` | Happy, uplifting energy |
| `[Mood: Melancholic]` | Sad, wistful |
| `[Mood: Aggressive]` | Intense, combative |
| `[Mood: Nostalgic]` | Wistful, looking back |
| `[Atmosphere: Dreamy]` | Hazy, floating |
| `[Atmosphere: Cyberpunk]` | Dark futuristic |
| `[Energy: Explosive]` | Maximum intensity |
| `[Energy: Building]` | Gradual increase |

### Production Effect Metatags

| Tag | Effect |
|-----|--------|
| `[Effect: Lo-fi]` | Degraded quality aesthetic |
| `[Effect: Reverb: Hall]` | Large-space reverb |
| `[Effect: Delay: Ping-pong]` | Stereo bouncing delay |
| `[Effect: Distortion]` | Signal distortion |
| `[Effect: Sidechain]` | Pumping compression |
| `[Effect: Bitcrusher]` | Digital degradation |
| `[Effect: Radio Filter]` | Bandpass telephone effect |
| `[Texture: Grainy]` | Rough, noisy texture |

### How Metatags Interact with Style Tags

The style field sets the **global** sonic identity. Lyrics metatags **modulate** that identity per section.

- Style tags = the instrument you're playing
- Lyrics metatags = how you play it in each section

**Style and metatags reinforce each other**: if your style says `"raspy vocals"` and your lyrics include `[Raspy]`, the effect is stronger than either alone. Community reports ~70-90% success when both align.

**Metatags can override style locally**: `[Whispered]` in the lyrics will temporarily override a `"powerful vocals"` style tag for that section.

**Warning**: Putting production cues (genre, BPM, instruments) in the lyrics field alongside metatags is discouraged. Keep sonic identity in the style field, structural/performance direction in the lyrics metatags. Clean field separation produces better results.

### Reliability

Not all metatags work equally:
- **High reliability**: `[Intro]`, `[Verse]`, `[Chorus]`, `[Bridge]`, `[Outro]`, `[End]`, `[Instrumental]`
- **Medium reliability**: `[Whispered]`, `[Falsetto]`, `[Belting]`, `[Guitar Solo]`, `[Drop]`, `[Build]`
- **Low reliability**: `[Mood: ...]`, `[Atmosphere: ...]`, `[Effect: ...]` -- these are suggestions, not commands
- **Experimental**: Compound pipe-delimited tags, callback phrasing, persona references

---

## BPM Tags: Do They Actually Work?

### Short Answer: Unreliably

Community consensus is clear: **BPM tags have limited and inconsistent effectiveness.**

Key findings from Reddit:
- Users report requesting 100 BPM and getting 120 BPM output
- "Suno is really bad at following tempo instructions" regardless of phrasing
- BPM tags are treated as suggestions, not constraints
- The model tends to default to genre-appropriate tempos regardless of explicit BPM

### What Works Better Than Numeric BPM

**Descriptive tempo terms** produce more consistent results than numbers:

| Desired Tempo | Use Instead of BPM |
|--------------|-------------------|
| Very slow (40-60) | `glacial, meditative, barely moving, deep drone` |
| Slow (60-80) | `slow, languid, downtempo, funeral pace` |
| Mid-tempo (80-110) | `mid-tempo, steady groove, walking pace` |
| Moderate (110-130) | `moderate, danceable, steady pulse` |
| Fast (130-160) | `driving, uptempo, energetic, relentless` |
| Very fast (160+) | `breakneck, frantic, blast-beat, thrash` |

**Genre anchors** implicitly set tempo better than BPM tags. `"doom metal"` implies slow (~60-70 BPM). `"drum and bass"` implies fast (~170 BPM). The genre tag does more tempo work than any BPM number.

### Recommendation for Our Pipeline

Continue including BPM as a hint (it occasionally helps), but **always pair with descriptive tempo terms and genre anchors** that naturally imply the desired tempo. Don't rely on BPM alone.

```
OK:    "ambient, 70 BPM"
BETTER: "ambient, glacial, barely moving, deep drone, 70 BPM"
```

---

## Negative Tags: Do They Reliably Prevent Things?

### Mixed Effectiveness

The Exclude Styles field (negative tags) has **inconsistent results** based on extensive community testing.

### What Works (~80-90% reliable)

- **Gender exclusion**: `female vocals` in negative tags when wanting male voice (~85-99% effective when combined with positive `male vocals` tag)
- **Vocal suppression for instrumentals**: `vocals, singing, voice, spoken word` (~80%+ when combined with the instrumental toggle)
- **Specific instrument exclusion**: `electric guitar` or `drums` to suppress specific instruments (~70-80%)

### What Doesn't Work Reliably

- **Genre exclusion**: `country` or `pop` in negative tags often still bleeds through
- **Mood exclusion**: `happy` or `upbeat` as negative tags is unreliable
- **Abstract concept exclusion**: `generic` or `boring` has no effect

### The Pink Elephant Paradox

Multiple community members reference this: **negative prompts sometimes reinforce unwanted elements.** The model processes the concept (e.g., "guitar") in order to exclude it, but the processing itself activates that concept in the latent space. This is analogous to "don't think of a pink elephant" -- the instruction requires thinking about the thing.

### Practical Recommendations

1. **Use negative tags for vocal control** -- this is their strongest use case
2. **For instruments**: prefer specifying what you WANT rather than what you don't want
3. **Keep negative tags short** -- 200 character limit; 2-4 specific exclusions max
4. **Always combine with strong positive tags** -- positive direction is more reliable than negative suppression
5. **For our instrumental pipeline**: continue using `"vocals, singing, voice, spoken word"` as negative tags + instrumental toggle (belt and suspenders approach)

---

## Instrumental Toggle vs Instrumental Tag

### They Do Different Things

| Feature | Function | Scope |
|---------|----------|-------|
| **Instrumental Toggle** (UI) | Sets the entire generation to instrumental mode | Global -- entire track |
| **`[Instrumental]` metatag** (lyrics) | Marks a specific section as instrumental | Local -- one section |

### When to Use Which

- **Fully instrumental track**: Use the toggle (`make_instrumental: true` in API). This is the strongest signal.
- **Track with some vocal and some instrumental sections**: Leave toggle off, use `[Instrumental Break]` or `[Instrumental]` metatags in specific sections.
- **Belt and suspenders for instrumental**: Toggle ON + `"instrumental"` in style tags + `"vocals, singing, voice"` in negative tags. Our pipeline already does this, which is correct.

### Does "instrumental" in Style Tags Add Anything Over the Toggle?

Community reports suggest: **marginally yes.** The toggle is the primary mechanism, but adding `"instrumental"` to style tags provides a secondary reinforcement signal. Our pipeline's approach of using both is optimal.

---

## Artist References in Tags

### Filtered and Blocked

Suno actively filters direct artist references:
- `"sounds like Radiohead"` -- triggers generic results, not Radiohead-like music
- `"Elvis Presley style"` -- filtered for copyright protection
- `"in the style of [Artist]"` -- same

This filtering is by design (copyright/legal protection).

### What to Do Instead

**Describe the sonic characteristics** rather than naming the artist:

| Instead of... | Write... |
|---------------|----------|
| `"Boards of Canada style"` | `"lo-fi analog warmth, detuned synths, nostalgic haze, tape deterioration, pastoral electronics"` |
| `"Aphex Twin"` | `"intricate IDM breakbeats, acid squelch, glitchy textures, playful complexity, drill-and-bass"` |
| `"Brian Eno ambient"` | `"generative ambient, slowly evolving pads, oceanic reverb, minimal movement, systems music"` |
| `"Nine Inch Nails"` | `"industrial rock, distorted synths, aggressive, machine rhythms, angst-driven"` |
| `"Massive Attack"` | `"dark trip-hop, heavy sub-bass, paranoid atmosphere, sparse drums, dub influence"` |

This approach actually produces **better** results than artist names would, because it gives Suno concrete sonic parameters rather than a filtered reference.

### Era/Scene References (Partially Work)

While artist names are blocked, era and scene references are generally accepted:

- `"90s Bristol trip-hop scene"` -- works
- `"early 80s Manchester post-punk"` -- works
- `"2010s Berlin minimal techno"` -- works
- `"1970s Dusseldorf electronic"` -- works (implies Kraftwerk-adjacent without naming them)

---

## Suno v5 vs v4 Prompting Differences

### What Changed in v5 (chirp-crow)

Based on community reports and the openmusicprompt.com guide:

1. **Maximum generation length**: 4 minutes (v4) -> 8 minutes (v5)
2. **Natural language understanding**: v5 supports "evocative natural language" in style prompts, not just keyword lists. Descriptive phrases work better than in v4.
3. **Vocal persona stability**: v5 "remembers the character of the voice better across extensions" -- less vocal drift in extended tracks.
4. **Callback phrasing**: v5 supports `[Callback: Chorus melody]` to reference earlier sections.
5. **Style tag character limit**: Expanded to 1,000 characters (was 120).
6. **Complex section handling**: v5 handles more varied metatag structures without confusion.
7. **Personas feature**: v5 introduces Personas -- saved vocal/energy profiles from existing tracks.
8. **Studio features**: Stem separation, waveform editing, section regeneration (not directly prompting, but affects workflow).

### Prompting Implications for v5

- **Use more descriptive, narrative-style tags** -- v5 understands them better than v4 did
- **Longer tag strings are less risky** -- v5 processes 1,000 chars better than v4 did with 120
- **Callback metatags available** -- useful for thematic cohesion in longer tracks
- **Persona upload** -- strongest lever for consistent sonic identity across tracks

### What Didn't Change

- Tag order still matters (first position = highest weight)
- BPM tags still unreliable
- Negative tags still inconsistent
- Artist name filtering still active
- Genre tags still dominate sonic character

---

## Actionable Recommendations for Our Pipeline

### For `generate_prompts.py` / `bin/generate-prompts`

1. **Replace generic electronic parent genres** with specific subgenres in tag generation.
   - Maintain a lookup table: when Perplexity research returns `"electronic"`, map to appropriate subgenre based on other research context.

2. **Always include at least one sonic texture descriptor** alongside genre tags.
   - `"warm analog pads"` not just `"ambient"`
   - `"crystalline digital arpeggios"` not just `"electronic"`

3. **Target 150-300 characters** for style tag strings (up from current 120-200). The v5 1,000-char limit gives us room.

4. **Ensure the most important descriptor is first** -- vocal character for Refrakt, primary subgenre for instrumental.

### For Batch Variety (Multiple Tracks from Same Playlist)

5. **Vary Position 1 tag across tracks in a batch** -- never submit two tracks with the same lead tag.

6. **Vary lyrics metatag structures** -- use different section names/patterns for each track. Keep a pool of alternative section vocabularies:
   - Standard: `[Intro] [Verse] [Chorus] [Verse] [Bridge] [Chorus] [Outro]`
   - Ambient: `[Emergence] [Drift] [Texture Shift] [Convergence] [Dissolution]`
   - Cinematic: `[Opening Shot] [Rising Action] [Climax] [Denouement] [Credits]`
   - Electronic: `[Cold Open] [Loop A] [Build] [Drop] [Breakdown] [Loop B] [Fade]`

7. **Vary at least one instrument per track** -- swap the lead texture element.

8. **Vary production era references** across tracks in a batch.

### For Song Length Control

9. **Cap instrumental metatag sections at 5-6** for target length of 4-5 minutes.
10. **Always end with `[Outro]` or `[Fade Out]`** -- never leave the ending undefined.
11. **For tracks that must be long**: generate 6 minutes, use Extend feature for the rest.

### For Vocal Tracks (Refrakt)

12. **Vocal descriptors must be the first 2-3 tags** in the style string.
13. **Reinforce vocal character in lyrics metatags** -- if style says `raspy`, add `[Raspy]` before key sections.
14. **Pair raw vocal tags with raw production tags** -- `"lo-fi garage recording"` alongside `"gritty vocals"`.
15. **Use the Character Prompt method** for distinctive vocal character -- narrative context in style tags, not just keyword lists.
16. **Use pipe-delimited compound metatags** for vocal sections: `[Chorus | belt to breaking point | desperate intensity | stacked raw harmonies]`

### For Negative Tags

17. **Instrumental tracks**: Keep current approach (`vocals, singing, voice, spoken word` + toggle).
18. **Vocal tracks**: Use negative tags primarily for gender control.
19. **Don't rely on negative tags for genre/mood exclusion** -- use strong positive tags instead.

### Tag String Template (Updated)

For instrumental tracks:
```
[specific subgenre], [secondary genre influence], [lead instrument/synthesis], [sonic texture descriptor], [production era/aesthetic], [mood], [tempo descriptor]
```

Example:
```
dark ambient, isolationist drone, modular synthesizer pulses, corroded metal textures, industrial decay aesthetic, oppressive dread, glacial tempo
```

For vocal tracks (Refrakt):
```
[gender] [texture] [range/delivery], [production context], [primary genre], [secondary genre], [key instrument], [mood], [tempo descriptor]
```

Example:
```
male vocals, gravelly strained baritone, raw garage recording on cheap microphone, post-punk, angular noise-rock, jagged guitar, frustrated desperation, mid-tempo pulse
```
