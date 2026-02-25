# Suno Vocal Prompting Guide

Reference doc for controlling vocal characteristics in Suno AI generation. Sourced from community testing (r/SunoAI, Suno Discord), Perplexity research, and live API experimentation.

---

## Vocal Descriptor Taxonomy

### Gender
| Tag | Notes |
|-----|-------|
| `male vocals` | Most reliable gender tag (~80% override in v4) |
| `female vocals` | Most reliable gender tag |
| `male singer` / `female singer` | Also works, slightly less reliable |
| `male voice` / `female voice` | Works but weaker signal |
| `deep male vocals` | Combines gender + range hint |

### Vocal Range
| Tag | Description |
|-----|-------------|
| `bass` / `deep bass` | Lowest male range |
| `baritone` | Low-mid male (most common male singing range) |
| `tenor` | Mid-high male |
| `countertenor` | Very high male (rare, less reliable) |
| `alto` | Lower female |
| `mezzo-soprano` | Mid female |
| `soprano` | High female |

Classical range terms (`countertenor`, `mezzo-soprano`) are less reliably interpreted by Suno than simpler descriptors like `deep` or `high`.

### Texture
| Tag | Character |
|-----|-----------|
| `raspy` | Rough, worn edge |
| `gravelly` | Deeper roughness (Tom Waits territory) |
| `gritty` | Slightly raw, rock-adjacent |
| `breathy` | Airy, intimate quality |
| `smooth` | Clean, polished tone |
| `silky` | Warm smoothness |
| `husky` | Low, slightly rough warmth |
| `warm` | Rich, full mid-range |
| `nasal` | Brighter, forward-placed |
| `airy` | Light, floating quality |
| `clear` | Pure, unaffected tone |
| `powerful` | Strong projection, volume |
| `ethereal` | Otherworldly, floating |

### Delivery Style
| Tag | Character |
|-----|-----------|
| `belting` | Loud, powerful, chest voice |
| `crooning` | Soft, intimate, Sinatra-style |
| `falsetto` | Light head voice above natural range |
| `whispered` | Soft, intimate near-speaking |
| `spoken word` | Rhythmic speech, not singing |
| `growling` | Aggressive low vocalization |
| `shouting` | Raw, forceful projection |
| `soulful` | Emotive, gospel-influenced melisma |

### Emotional Quality
| Tag | Character |
|-----|-----------|
| `anguished` | Pain, distress |
| `tender` | Gentle, caring |
| `raw` | Unpolished, emotionally exposed |
| `intimate` | Close, personal |
| `passionate` | Intense emotion |
| `haunting` | Eerie, lingering |
| `melancholic` | Sad, wistful |

---

## What Works Where

### Style Tags Field (Global Voice Identity)
The Style/Tags field sets the **overall** vocal identity for the entire track. Vocal descriptors placed here apply to all sections.

**Key rule: put vocal descriptors early.** Suno weights tags by position — tags at the start of the string have more influence than those at the end.

```
male vocals, raspy baritone, raw intensity, grunge, distorted guitars, 95 BPM
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
vocal identity first
```

### Lyrics Metatags (Section-Specific Changes)
Bracket metatags in the Lyrics field apply vocal effects to specific sections:

```
[Verse 1] [Whispered]
Soft shadows fall across the floor...

[Chorus] [Belting]
Rise up and break through the walls!

[Bridge] [Falsetto]
Floating above it all...

[Outro] [Spoken Word]
And so it ends, quietly...
```

**Working metatags:**
- `[Whispered]`, `[Spoken Word]`, `[Falsetto]`, `[Belting]`, `[Shout]`
- `[Raspy]`, `[Breathy]`, `[Growling]`, `[Narration]`
- `[Gospel Choir]`, `[Harmony]`, `[Adlibs]`, `[Vocal Run]`

**Combining works:** `[Whispered Verse]`, `[Powerful Chorus]`, `[Falsetto Bridge]`, `[Gospel Choir Harmony]`

### Reinforcement Strategy (Use Both)
Lyrics metatags take **priority** for their section, modulating the Style tags. Overlapping reinforces:

- Style: `husky male vocals` + Lyrics: `[Raspy]` → intensifies the texture
- Style: `male vocals` + Lyrics: `[Falsetto]` → high male falsetto
- Style: `female vocals, powerful alto` + Lyrics: `[Belting]` → strong female belt

Community reports 70-90% success rate when combining Style tags with Lyrics metatags for dynamic vocal shifts.

---

## Negative Tags for Vocal Control

Use the Negative Tags field to suppress unwanted vocal characteristics.

### Gender Exclusion (Most Important Use)
| Want | Negative Tags |
|------|--------------|
| Male voice | `female vocals` |
| Female voice | `male vocals` |

Combine with positive Style tags for strongest effect:
- Style: `male vocals, gritty baritone, rock` + Negative: `female vocals` → ~85% male in v4

### Other Useful Negative Tags
| Suppress | Negative Tag |
|----------|-------------|
| Choir/backing vocals | `choir, harmonies` |
| High-pitched vocals | `high pitch, falsetto` |
| Auto-tune effect | `auto-tune, robotic` |
| Any vocals (instrumental) | `vocals, singing, voice, spoken word` |

Gender negative tags shift probability ~60-80% alone, ~85%+ when combined with positive gender tags.

---

## Reliable Patterns

Community-tested tag combinations with approximate success rates (v4/chirp-crow model):

### Deep Raspy Male (~90%)
```
Style: deep male baritone, husky raspy vocals, gritty, [genre], [mood]
Negative: female vocals, high pitch
Metatags: [Low Growl] for verses, [Powerful] for chorus
```

### Ethereal Breathy Female (~85%)
```
Style: female vocals, breathy soprano, ethereal airy, [genre], [mood]
Negative: male vocals, low vocals
Metatags: [Falsetto] for bridges, [Whispered] for intros
```

### Soulful Warm Male (~85%)
```
Style: male vocals, warm tenor, soulful crooning, [genre], [mood]
Negative: female vocals
Metatags: [Vocal Run] for choruses
```

### Powerful Alto Female (~85%)
```
Style: female vocals, powerful alto, belting, [genre], [mood]
Negative: male vocals
Metatags: [Belting] for chorus, [Breathy] for verses
```

### Gentle Intimate Male (~80%)
```
Style: male vocals, soft intimate tenor, whispered delivery, [genre], [mood]
Negative: female vocals, powerful
Metatags: [Whispered] for verses
```

### Raw Aggressive Male (~90%)
```
Style: male vocals, gritty raspy, shouting, raw, [genre], [mood]
Negative: female vocals, smooth
Metatags: [Shout] for chorus, [Growling] for bridges
```

---

## Known Limitations

### Gender Switching Mid-Song
Unreliable (<30% success). Metatags like `[Male Verse]` followed by `[Female Chorus]` usually result in blending or ignoring. If you need gender changes, generate sections separately and extend.

### Classical Range Terms
`countertenor`, `mezzo-soprano` are less reliably interpreted than plain descriptors. Prefer `high male voice` over `countertenor`, `low female voice` over `contralto`.

### Accent Control
Poor support (~10-20% success). Tags like `British accent`, `Southern drawl` rarely produce distinct accents. Genre anchors provide indirect influence (e.g., `British pop` mildly influences toward British pronunciation).

### Artist Voice Mimicry
Blocked by Suno policies. Tags like `sounds like [Artist]` trigger generic results, not mimicry. Instead, describe the voice characteristics: `deep gravelly baritone, whiskey-soaked, world-weary delivery` instead of referencing a specific artist.

### Stochastic Nature
Even with precise tags, Suno may produce unexpected results ~10-20% of the time. Plan for re-rolls — generate, evaluate, regenerate if the voice doesn't match. The `weirdness_constraint` slider (when available) at 50-70% can help push toward more distinctive vocal choices.

### Tag Overload
More than 5 vocal descriptors dilute effectiveness. Stick to 2-3 vocal tags that work together.

---

## Tag Construction Rules

1. **Vocal descriptors first** — position = weight. Put gender + tone + texture before genre anchors
2. **2-3 vocal tags max** — more dilutes the signal
3. **No contradictions** — don't combine `breathy` with `belting`, or `soprano` with `baritone`
4. **Pair with genre anchors** — vocal tags work best when grounded by 2-3 genre terms
5. **Total tag string 120-200 chars** — Suno's effective processing window
6. **Use descriptive phrases** — `husky raspy baritone` > just `baritone`
7. **Gender + negative tags together** — e.g., `male vocals` in Style + `female vocals` in Negative
8. **Reinforce with metatags** — if you want raspy vocals, put `raspy` in Style AND `[Raspy]` in Lyrics sections

### Tag String Template
```
[gender] [range/texture] [delivery], [genre 1], [genre 2], [sonic textures], [mood], [BPM]
```

Example:
```
male vocals, deep raspy baritone, raw anguished delivery, grunge, alternative rock, heavy distorted guitars, dark brooding atmosphere, 95 BPM
```
