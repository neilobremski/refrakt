---
name: youtube-upload
description: Upload a video/album to YouTube via browser automation. Creates an MP4 from audio + cover art, fills metadata, and publishes.
---

# /youtube-upload — Upload to YouTube

Upload an album or single track to YouTube as a video with album art.

## Arguments

- `--folder <path>` — folder containing the MP3s and cover art (default: most recent album in `output/`)
- `--title <title>` — YouTube video title (default: folder name)
- `--visibility <public|unlisted|private>` — (default: unlisted)

---

## Step 1 — Create the Video

### Cover Art
**IMPORTANT: Use a 16:9 widescreen image (1920x1080) for YouTube.** Square album art crops badly in YouTube's player and thumbnails. If only a square image exists, either:
- Ask the user to provide a widescreen version
- Pad the square image with black bars: `ffmpeg -i square.jpeg -vf "pad=1920:1080:(1920-iw)/2:(1080-ih)/2:black" wide.jpeg`

### Concatenate Tracks (if multiple)
Build a concat list from the individual MP3s in track order:
```bash
ls folder/*.mp3 | sort | while read f; do echo "file '$f'"; done > /tmp/concat.txt
ffmpeg -f concat -safe 0 -i /tmp/concat.txt -c copy -y "Full Album.mp3"
```

### Create MP4
```bash
ffmpeg -loop 1 -i cover-wide.jpeg -i "Full Album.mp3" \
  -c:v libx264 -tune stillimage -c:a aac -b:a 320k \
  -pix_fmt yuv420p -shortest -y output.mp4
```

### Tag the Full Album MP3
Set artist, album, title, cover art, genre, year using mutagen.

---

## Step 2 — Generate Description

Read each individual MP3's duration and accumulate timestamps:
```python
offset = 0
for mp3 in sorted_tracks:
    duration = MP3(mp3).info.length
    print(f"{int(offset)//60}:{int(offset)%60:02d} — {track_name}")
    offset += duration
```

Build a YouTube description with:
- Album title and artist
- One-paragraph concept/story summary
- Full tracklist with timestamps (YouTube auto-creates chapter markers)
- Genre, runtime
- Credits
- Hashtags

Save to `_youtube_description.txt` in the album folder.

---

## Step 3 — Upload via Browser

### Open YouTube Studio
```bash
playwright-cli open --headed --persistent --profile=.playwright-profile "https://studio.youtube.com"
```
User logs in if needed. Wait for dashboard.

### Upload the Video
1. Click `Create` button (exact match): `getByRole('button', { name: 'Create', exact: true })`
2. Click `Upload videos` from dropdown
3. Set file via hidden input: `page.locator('input[type="file"]').setInputFiles(absPath)`
4. Wait for upload to complete (~30s for 100MB)

### Fill Details
- **Title**: `page.locator('#textbox').first()` — click + Cmd+A + insertText
- **Description**: `page.locator('#description-textarea #textbox')` — click + insertText
- **Audience**: Scroll down, select "No, it's not made for kids" radio button
- Click **Next** three times (Details → Video elements → Checks → Visibility)

### Set Visibility & Publish
- Select visibility radio: `getByRole('radio', { name: 'Public' })` or Unlisted
- Click **Publish** (not "Save" — button changes name when Public is selected)
- Confirm "Video published" dialog — note the video link

### Close
```bash
playwright-cli close
```

---

## Troubleshooting

### "Create" button resolves to multiple elements
Use `{ exact: true }` to match only the top-bar Create button.

### "Publish" button not found as "Save"
When visibility is set to Public, the button changes from "Save" to "Publish". Search the snapshot for `button "Publish"`.

### Upload stalls
The file input approach works reliably. If it stalls, check that the file path is absolute and the MP4 is valid.
