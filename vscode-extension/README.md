# Local Copilot (VS Code extension)

Thin TypeScript client for the [Local Copilot](../README.md) offline code review engine. All
review logic still runs in the Python/Ollama backend — this extension just captures a diff from
the open workspace, POSTs it to the FastAPI server, and renders the structured result in a panel.

## 1. Install Ollama and pull a model

1. Download and install Ollama from [ollama.com](https://ollama.com) (Windows/macOS/Linux).
2. Confirm it's running — on Windows it starts automatically and sits in the system tray; you can
   also check from a terminal:
   ```bash
   ollama --version
   ```
3. Pull the default model (~2GB download, CPU-friendly):
   ```bash
   ollama pull granite4:3b
   ```
   Optionally pull a larger/more accurate model too:
   ```bash
   ollama pull mistral:7b
   ```
4. Sanity-check the model actually responds before wiring up anything else:
   ```bash
   ollama run granite4:3b "hi"
   ```
   If this hangs for more than a few seconds on the first token, see
   [Troubleshooting](#troubleshooting) below — it's a known issue with some model pulls on this
   project, not the extension.

## 2. Set up and run the Python backend

From the `LocalCopilot` project root (one level up from this folder):

```bash
python -m venv .venv
.venv\Scripts\activate        # .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
```

Start the API server (leave this running in its own terminal):

```bash
uvicorn app.api:app --reload
```

Verify it's up:

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

The extension talks to this server over HTTP — it must be running whenever you use the extension.

## 3. Install the extension

Pick one:

**A. Run from source (for development/testing):**

```bash
cd vscode-extension
npm install
npm run compile
```

Open the `vscode-extension` folder itself in VS Code, then press `F5` (or Run → Start Debugging).
This opens a second window titled `[Extension Development Host]` with the extension loaded — that
window is where you test it, not the one you pressed F5 in. If the window doesn't come up, use
`Ctrl+Shift+P` → "Developer: Reload Window" in the extension host window once it appears, and check
the **Debug Console** in your original window for any load errors.

**B. Install as a packaged extension (for regular day-to-day use):**

```bash
cd vscode-extension
npm install
npm run compile
npx vsce package
```

This produces `local-copilot-0.1.0.vsix`. Install it into your normal VS Code via Command Palette →
"Extensions: Install from VSIX..." → select the file. No F5 needed afterward — it behaves like any
other installed extension and stays installed across restarts.

## 4. Use it

Open any git repository in the window where the extension is loaded (the Dev Host window if you
used option A, or your regular VS Code if you used option B). Make sure the repo has some
uncommitted or staged changes to review, then open the Command Palette (`Ctrl+Shift+P`) and run one
of:

- **Local Copilot: Review Uncommitted Changes** — reviews `git diff HEAD`
- **Local Copilot: Review Staged Changes** — reviews `git diff --staged`
- **Local Copilot: Review Diff Against Ref...** — prompts for a ref (e.g. `HEAD~1`, `main`) and
  reviews the diff against it

All three are also pinned to the Source Control view's title bar (the compare icon).

A progress notification appears while the model runs, then a panel opens beside your editor with
the change-type badge, a color-coded risk badge, the summary, suggested tests, and a metrics
footer (model, latency, tokens/sec, retries).

## Settings

Configure via `Ctrl+,` → search "Local Copilot", or directly in `settings.json`:

| Setting | Default | Description |
|---|---|---|
| `localCopilot.serverUrl` | `http://127.0.0.1:8000` | Base URL of the running API server |
| `localCopilot.model` | `granite4:3b` | Ollama model tag |
| `localCopilot.temperature` | `0.0` | Sampling temperature |

## Troubleshooting

**"Local Copilot server is not reachable"** — the FastAPI server (step 2) isn't running, crashed,
or is on a different port than `localCopilot.serverUrl`. Click "Copy start command" on the error
notification for the exact command to run.

**Port 8000 already in use** — something else is already bound to it (possibly a previous
`uvicorn` you forgot was running). Find it and reuse it instead of starting a second copy:
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object OwningProcess
```

**"Select debugger" prompt on F5** — shouldn't happen since `.vscode/launch.json` is committed in
this folder, but if VS Code still asks, choose "VS Code Extension Development".

**Opening a folder in the Extension Development Host seems to do nothing** — check for a hidden
"Do you trust the authors of files in this folder?" dialog (can open behind the main window), and
note that VS Code reloads the whole window when switching folders — this is normal, not a hang.
Confirm the title bar still shows `[Extension Development Host]` after it settles.

**A specific model hangs indefinitely** — confirmed on this project with `qwen3.5:0.8b`; unrelated
to the extension or backend code (reproduces with a bare `ollama run <model> "hi"`). Re-pull the
model (`ollama rm <model> && ollama pull <model>`) and confirm it responds via `ollama run` before
selecting it in `localCopilot.model`. See the main [README](../README.md#known-issues--debugging-notes)
for the root-cause writeup (an oversized default context window/KV-cache).

**Review request fails with a 400/500 from the server directly (not via the extension)** — if
you're calling the API with a different HTTP client (e.g. PowerShell's `Invoke-RestMethod`), make
sure the request body is sent as UTF-8 bytes — some clients default to Latin-1 for string bodies,
which corrupts non-ASCII characters in the diff. The extension's own HTTP client (`reviewClient.ts`)
already handles this correctly.

## Development

```bash
npm install
npm run watch     # recompiles on save; reload the Dev Host window (Ctrl+R) to pick up changes
```

## Architecture

- `src/gitDiff.ts` — runs `git diff` in the open workspace (working tree / staged / ref)
- `src/reviewClient.ts` — talks to the FastAPI server over Node's built-in `http`/`https`
- `src/panel.ts` — renders the result as a Webview panel
- `src/extension.ts` — registers the three commands and wires the above together
