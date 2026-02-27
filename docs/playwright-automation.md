# Playwright Browser Automation Guide

This documents how `playwright-cli` works under the hood, how we use it for Gemini and Suno automation, and hard-won lessons about downloads, sessions, and React forms.

---

## Architecture

`playwright-cli` is a thin CLI wrapper around Playwright's MCP (Model Context Protocol) backend.

```
playwright-cli (CLI)
  └─ @playwright/cli (npm package, shim)
       └─ playwright/lib/cli/client/program.js  (client — parses args, connects to daemon)
            └─ daemon process (spawned on `open`, runs until `close`)
                 └─ BrowserServerBackend (MCP tool executor)
                      └─ playwright-core (controls Chrome/Firefox/WebKit)
```

### Key source paths (in `node_modules/@playwright/cli/node_modules/playwright/`)
| File | What it does |
|------|-------------|
| `lib/cli/client/session.js` | Client session management, daemon spawn |
| `lib/cli/daemon/daemon.js` | Daemon server, receives CLI commands via socket |
| `lib/cli/daemon/commands.js` | CLI command → MCP tool mapping |
| `lib/mcp/browser/tab.js` | Page event handling (downloads, dialogs, console) |
| `lib/mcp/browser/config.js` | Output directory resolution, file paths |
| `lib/mcp/browser/response.js` | Formats tool results back to CLI output |

### Command → MCP Tool Mapping

Each `playwright-cli` command is a thin wrapper around an MCP tool call:

| CLI Command | MCP Tool |
|-------------|----------|
| `click <ref>` | `browser_click` |
| `fill <ref> <text>` | `browser_type` |
| `snapshot` | `browser_snapshot` |
| `screenshot` | `browser_take_screenshot` |
| `eval <func>` | `browser_evaluate` |
| `run-code <code>` | `browser_run_code` |
| `press <key>` | `browser_press_key` |

Source repo: https://github.com/microsoft/playwright-cli

---

## Downloads

### How downloads work

When `playwright-cli click <ref>` triggers a browser download, Playwright **automatically intercepts** it:

1. `tab.js` listens for `page.on('download')` events
2. Calls `download.saveAs()` to save to the output directory
3. Reports in CLI output: `"Downloaded file X to .playwright-cli/X"`

Downloads are saved to `.playwright-cli/` in the current working directory by default.

### Finding downloaded files

```bash
# List all Gemini images (sorted newest first)
ls -t .playwright-cli/Gemini-Generated-Image-*.png | head -1

# Generic: find newest download
ls -t .playwright-cli/ | head -5
```

### Configuring the download directory

The output directory is resolved in `config.js`:

```javascript
function outputDir(config, clientInfo) {
  if (config.outputDir)                    // 1. Config file setting
    return path.resolve(config.outputDir);
  const rootPath = firstRootPath(clientInfo);
  if (rootPath)                            // 2. CWD + .playwright-cli (default)
    return path.resolve(rootPath, ".playwright-cli");
  return path.resolve(os.tmpdir(), ...);   // 3. Temp dir fallback
}
```

To change: create `.playwright/cli.config.json` with `"outputDir": "/path/to/downloads"`.

### CRITICAL: Do NOT use `run-code` for downloads

```bash
# BAD — unreliable with Gemini's blob URLs, often times out:
playwright-cli run-code "async page => {
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.click('a.download-link')
  ]);
  await download.saveAs('./file.pdf');
}"

# GOOD — just click and the file auto-saves:
playwright-cli click <ref>
sleep 5
ls -t .playwright-cli/Gemini-Generated-Image-*.png | head -1
```

The `run-code` approach works for simple `<a href>` links but fails with Gemini because:
- Gemini uses blob URLs for image downloads
- The download event timing is unpredictable
- `waitForEvent('download')` has a default timeout that's too short for large images

---

## Gemini Image Generation

### Setup

```bash
playwright-cli open --headed --persistent --profile=.refrakt/playwright-profile "https://gemini.google.com"
```

- Must use `--headed` (Gemini blocks headless)
- `--persistent --profile=` keeps login state across sessions
- Verify "Thinking" model is selected (model picker in top area)

### Prompting

**ALL image prompts MUST start with `"Generate an image:"`** — without this prefix, the Thinking model analyzes/discusses the prompt rather than generating.

#### Square (1:1 album art)
```
Generate an image: [concept description]. Square 1:1 aspect ratio.
Include the text "TITLE" in a clean modern sans-serif font in the lower third,
and "ARTIST" in smaller text below it. Light/white text with subtle glow.
```

#### Widescreen (16:9 YouTube)
```
Generate an image: Create a WIDESCREEN LANDSCAPE image that is much wider
than it is tall, like a YouTube banner (approximately 2752 pixels wide by
1536 pixels tall). [concept]. Include the text "TITLE" and "ARTIST".
The image MUST be wider than it is tall - landscape orientation, not square.
```

**Widescreen tip:** Gemini often ignores simple "16:9" requests. Use explicit dimensions and emphasis: "WIDESCREEN LANDSCAPE, NOT SQUARE, much wider than tall."

### Finding the textbox

The Gemini input is a `contenteditable` div, not an `<input>`. Use role-based selectors:

```
getByRole('textbox', { name: 'Enter a prompt for Gemini' })
```

The ref ID changes between page navigations — always take a fresh `playwright-cli snapshot` to get the current ref.

### Waiting for generation

Gemini image generation takes 30-90 seconds.

```bash
sleep 30
playwright-cli snapshot  # Look for "Download full size image" button
# If not found:
sleep 15
playwright-cli snapshot  # Retry
```

Max 3 polls before reporting failure.

### Download flow

```bash
# 1. Record existing files before clicking
ls .playwright-cli/Gemini-Generated-Image-*.png 2>/dev/null

# 2. Click the download button (use ref from snapshot)
playwright-cli click <REF>

# 3. Wait for save, find the file
sleep 5
ls -t .playwright-cli/Gemini-Generated-Image-*.png | head -1

# 4. Verify dimensions (Gemini = ~2048px, DALL-E = 1024px)
.venv/bin/python -c "
import struct, os
def png_dims(path):
    with open(path, 'rb') as f:
        f.read(16)
        w = struct.unpack('>I', f.read(4))[0]
        h = struct.unpack('>I', f.read(4))[0]
    return w, h
w, h = png_dims('FILE')
print(f'{w}x{h}, {os.path.getsize(\"FILE\")//1024}KB')
"

# 5. Move immediately (Playwright reuses filenames)
mv ".playwright-cli/Gemini-Generated-Image-*.png" "output_dir/cover.png"
```

### Expected dimensions
| Type | Dimensions | Size |
|------|-----------|------|
| Square | ~2048x2048 | 8-12 MB |
| Widescreen | ~2752x1536 or ~3168x1344 | 8-12 MB |
| Wrong (DALL-E) | 1024x1024 | ~2 MB |

---

## Suno Browser Automation

### Form filling

Suno uses React components, NOT raw HTML inputs. CSS selectors for placeholders fail.

```bash
# Role-based selectors work (reads accessibility tree):
getByRole('textbox', { name: /pattern/ })

# Styles textbox has rotating placeholder — match by exclusion
```

**React state quirk:** `fill()` works for empty fields but does NOT update React state when overwriting. For Title and Styles fields, use:

```javascript
// click + select all + delete + insertText
await field.click();
await page.keyboard.press('Meta+a');
await page.keyboard.press('Backspace');
await page.keyboard.insertText(newValue);
```

### Submission pattern (proven reliable)

```bash
# MUST reload between submissions to clear form state
playwright-cli reload
sleep 3
bin/suno-fill-form --index N
sleep 1
playwright-cli run-code "async page => {
  await page.getByRole('button', { name: 'Create song' }).click();
  return 'ok';
}"
sleep 5
bin/suno feed | grep "TITLE"  # verify in feed
```

### Session management

- Persistent profile at `.refrakt/playwright-profile/` avoids hCaptcha visual challenges
- Suno cookies injected from `.refrakt/suno_session.json`
- `bin/suno submit` handles the full flow: open → inject → fill → submit → close

---

## Browser Session Conflicts

**Gemini art and Suno submit share the same Playwright profile.** Never run them in parallel.

- `bin/suno submit` calls `playwright-cli close` at the end
- If Gemini is also open, the close kills both sessions
- **Always run art stage FIRST**, then submit (or vice versa, never concurrent)

---

## Troubleshooting

### Download button click doesn't trigger download
- Take a fresh snapshot — ref IDs change between navigations
- Make sure you're clicking the actual "Download full size image" button ref
- Check `.playwright-cli/` anyway — the file may have saved even if the CLI didn't report it

### Gemini generates text discussion instead of image
- Prompt MUST start with "Generate an image:" (the prefix triggers image mode)
- Verify "Thinking" model is selected

### Stale browser session
```bash
playwright-cli close
playwright-cli kill-all  # if close doesn't work
playwright-cli open --headed --persistent --profile=.refrakt/playwright-profile "https://gemini.google.com"
```

### React form not updating
- Reload the page between submissions: `playwright-cli reload`
- Use `insertText` instead of `fill()` for overwriting existing values
- Verify with snapshot after filling — check the field shows the new value
