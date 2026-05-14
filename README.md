# ZGX AI Bridge -- Browser Extension

> **Disclaimer:** This is an educational proof-of-concept exploring browser-based context injection for AI assistants. Not affiliated with, endorsed by, or sponsored by PTC/Onshape or any ISV vendor. See Onshape documentation: https://cad.onshape.com/FsDocNot intended for production use. Check vendor terms of service before deploying similar approaches against any ISV application.

## What This Is

A Chrome/Edge extension that injects an AI chat widget into web-based ISV applications and routes inference to an on-prem [ZGX AI Bridge](https://github.com/curtburk/CAD-Cross-Architecture-AI) backend. The extension scrapes contextual data from the host application (document names, workspace tabs, feature trees) and sends it with each message so the AI can answer questions grounded in what the user is currently looking at.

The host application is completely unmodified. No plugins, no SDK integration, no code changes on the ISV side.

## How It Works

```
ISV Web App (e.g., Onshape)          Extension                    ZGX Nano (ARM64)
+------------------------+     +------------------+     +-------------------------+
| Browser tab (HTTPS)    |     | content.js       |     | Bridge (FastAPI :8080)  |
|                        |     |  - injects widget|     |  - context injection    |
|  [chat widget overlay] |<--->|  - scrapes context|     |  - session management   |
|                        |     | background.js    |---->|  - token tracking       |
+------------------------+     |  - proxies HTTP  |     +------------+------------+
                               |  (bypasses mixed |                  |
                               |   content block) |                  v
                               +------------------+     +-------------------------+
                                                        | vLLM (:8090)            |
                                                        | Qwen3.6-35B-A3B         |
                                                        | + DFlash spec decoding  |
                                                        +-------------------------+
```

The extension uses a background service worker to proxy all HTTP requests to the Bridge. This is necessary because ISV apps run on HTTPS, and browsers block mixed-content requests from HTTPS pages to HTTP endpoints on the local network. The background script has no such restriction.

## Context Scraping

The content script captures whatever it can from the host application's DOM on each message:

| Field | Source | Example |
|---|---|---|
| `documentName` | Page title | "Part Feeding Machine" |
| `documentId` | URL path | `17a3ee2f861222e6c091b4f3` |
| `pageType` | URL pattern | `document` or `dashboard` |
| `tabInfo` | DOM elements matching tab selectors | Pallet, Gantry, Guarding, Rendering |
| `featureTree` | DOM elements matching feature selectors | (requires per-app selector tuning) |

The Bridge receives this context and injects it into the LLM's system prompt as natural language. The model answers using this context without the user having to explain what they're looking at.

## Installation

1. Download or clone this repository
2. Open `edge://extensions/` or `chrome://extensions/`
3. Enable **Developer mode**
4. Click **Load unpacked** and select this folder
5. Navigate to the target ISV application

## Configuration

Edit `background.js` lines 6-7:

```javascript
const BRIDGE_URL = "http://<YOUR_ZGX_NANO_IP>:8080";
const API_KEY = "dev-test-key";
```

After editing, reload the extension from the extensions page.

## File Structure

```
zgx-bridge-ext-v2/
  manifest.json     # MV3 manifest, targets *.onshape.com
  background.js     # Service worker, proxies HTTP to Bridge
  content.js        # Injected into ISV app, renders widget, scrapes context
  widget.css        # Chat panel styles
```

## Targeting a Different ISV App

To inject into a different web application, change two things:

1. **manifest.json** -- update the `matches` pattern in `content_scripts`:
   ```json
   "matches": ["https://*.your-isv-app.com/*"]
   ```

2. **content.js** -- update the CSS selectors in `scrapeContext()` to match the target app's DOM structure for tabs, feature trees, or other contextual elements.

## Limitations

- **Read-only.** The AI can see application context but cannot take actions in the host app.
- **No streaming.** Responses arrive in full after inference completes (MV3 service worker limitation with `sendMessage`). A port-based connection would enable token-by-token streaming.
- **DOM selectors are brittle.** ISV app updates can break context scraping. Selectors need periodic maintenance per target app.
- **Single ISV target.** The manifest targets one domain. Supporting multiple ISV apps requires either multiple extensions or a configurable matches pattern.

## Related

- [ZGX AI Bridge](https://github.com/curtburk/CAD-Cross-Architecture-AI) -- the FastAPI middleware and vLLM deployment that powers this extension

## License

Educational proof-of-concept. Not affiliated with or endorsed by PTC/Onshape or any ISV vendor.
