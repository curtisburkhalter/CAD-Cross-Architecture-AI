# ZGX AI Bridge -- Browser Extension

> **Disclaimer:** This is an educational proof-of-concept exploring browser-based context injection for AI assistants. Not affiliated with, endorsed by, or sponsored by PTC/Onshape or any ISV vendor. See Onshape documentation: https://cad.onshape.com/FsDoc Not intended for production use. Check vendor terms of service before deploying similar approaches against any ISV application.
# ZGX AI Bridge

AI-powered contextual assistant injected into unmodified x86 ISV web applications, with all inference running on ARM-based HP ZGX hardware. The application doesn't know it's talking to a different architecture. HTTP doesn't care. The data never leaves the building.

This is a cross-architecture connective layer: an x86 workstation runs the ISV application, an ARM64 ZGX Nano runs the AI, and a lightweight middleware bridges them over the local network. The ISV application requires zero modification. The user's data requires zero cloud exposure. The architecture gap is invisible.

**Tested with:** Onshape (PTC) -- browser-based professional CAD running on an x86 Windows laptop -- powered by Qwen3.6-35B-A3B with DFlash speculative decoding on an HP ZGX Nano AI Station (ARM64, NVIDIA GB10 Grace Blackwell).

## What It Does

A user opens their CAD application on their x86 workstation. A chat widget appears in the corner. They ask a question about the design they're looking at. The AI answers in under a second, grounded in the actual workspace context -- part names, assemblies, feature trees, documents.

What they don't see: their question left their x86 machine, crossed the local network to an ARM64 ZGX Nano, was processed by a 35-billion-parameter model running on a Grace Blackwell superchip, and the response came back -- all in under a second. Two completely different CPU architectures, seamlessly connected by a simple HTTP bridge. Their design data never touched the internet. Their IT department never had to modify the ISV application. Their cloud provider never saw a token.

## Architecture

```
x86 Workstation (Windows/Linux)    ARM64 On-Prem (ZGX Nano)
+---------------------------+      +---------------------------+
|   Onshape (ISV App)       |      |   Bridge (FastAPI)        |
|   +-------------------+   |      |   - context injection     |
|   | Widget Extension  |---+----->|   - session management    |
|   | (content script)  |   | HTTP |   - token/latency metrics |
|   +-------------------+   |      |   - API key auth          |
+---------------------------+      +-------------+-------------+
  Browser on x86 hardware                        |
  ISV app is UNMODIFIED                          v
  Zero code changes               +---------------------------+
                                  |   vLLM                    |
                                  |   Qwen3.6-35B-A3B         |
                                  |   + DFlash spec decoding  |
                                  |   ARM64 / GB10 / sm_121   |
                                  +---------------------------+
```

The architecture boundary between x86 and ARM64 is invisible to every layer. The widget makes an HTTP call. The Bridge forwards it. vLLM returns tokens. No architecture translation, no compatibility shims, no middleware complexity. HTTP is the universal connector.

Three components:

1. **Widget** -- Chrome/Edge extension that injects a chat panel into the ISV web app, scrapes page context (document name, workspace tabs, feature tree), and sends it with each message
2. **Bridge** -- FastAPI middleware that receives chat requests, validates context, assembles a context-aware system prompt, forwards to vLLM, streams responses back, and tracks usage metrics
3. **vLLM** -- OpenAI-compatible inference server running Qwen3.6-35B-A3B (MoE, 3B active params) with DFlash block diffusion speculative decoding

## Performance

Measured on HP ZGX Nano AI Station (NVIDIA GB10 Grace Blackwell, ARM64, 128GB unified memory):

| Metric | Value |
|---|---|
| Model | Qwen3.6-35B-A3B (35B total, 3B active) |
| Speculative decoding | DFlash (z-lab/Qwen3.6-35B-A3B-DFlash) |
| Short response (~67 tokens) | 980ms |
| Medium response (~160 tokens) | 5.0s |
| First request (cold CUDA graphs) | ~36s (subsequent requests are fast) |
| Cloud cost equivalent | $0.00 marginal vs. GPT-4o pricing |

## Quick Start

### Prerequisites

- HP ZGX Nano or Fury with NVIDIA GPU
- Docker + Docker Compose + nvidia-container-toolkit
- HuggingFace account (models are Apache 2.0, no gated access)

### Deploy

**Important:** Start the services in order. vLLM must be fully healthy before the Bridge will connect. First run downloads ~70GB of model weights and compiles CUDA graphs, which can take 10-20 minutes.

```bash
git clone https://github.com/curtburk/CAD-Cross-Architecture-AI.git
cd CAD-Cross-Architecture-AI

# Optional: set HF token for faster downloads
export HF_TOKEN=your_token_here

# Step 1: Start vLLM and wait for it to be healthy
docker compose up -d vllm
docker compose logs -f vllm
# Wait until you see: "Application startup complete"
# Then Ctrl+C out of the logs

# Step 2: Verify vLLM is healthy
curl http://localhost:8090/v1/models

# Step 3: Start the Bridge
docker compose up -d bridge
docker compose logs -f bridge
# Wait until you see: "vLLM connection verified"
```

Verify both services are running:

```bash
docker compose ps
```

You should see two containers, both healthy:
- `zgx-bridge-vllm` -- vLLM inference server on port 8090
- `zgx-bridge-app` -- Bridge middleware on port 8080

Quick health check:

```bash
curl http://localhost:8080/api/health
```

### Subsequent Startups

After the first run, models are cached and startup is faster. You can bring everything up at once, but always verify both containers are running:

```bash
docker compose up -d
docker compose ps

# If only vLLM is running and Bridge didn't start:
docker compose up -d bridge
```

### Install the Browser Extension

1. Unzip `zgx-bridge-ext-v2.zip`
2. Open `edge://extensions/` (or `chrome://extensions/`)
3. Enable Developer mode
4. Click "Load unpacked", select the inner `zgx-bridge-ext-v2` folder
5. Navigate to any Onshape document at `https://cad.onshape.com`
6. Click the green ⚡ button in the bottom-right corner

### Configure

The extension needs to reach the Bridge. How you configure this depends on your network setup.

#### Option A: Same LAN (recommended for demos)

If your laptop and the ZGX Nano are on the same network, point the extension directly at the Nano's LAN IP.

Edit `background.js` line 6:

```javascript
const BRIDGE_URL = "http://<YOUR_ZGX_NANO_IP>:8080";
```

Edit `manifest.json` to match:

```json
"host_permissions": [
    "http://<YOUR_ZGX_NANO_IP>:8080/*"
]
```

Find your Nano's IP with `hostname -I` on the Nano. Use the first address (e.g., `192.168.x.x`).

#### Option B: Remote access via Tailscale + SSH tunnel

If you're accessing the Nano remotely over Tailscale, direct HTTP to the Tailscale IP may not work due to port restrictions. Use an SSH tunnel instead.

**Step 1: Open the tunnel from your laptop (PowerShell)**

```powershell
ssh -L 19080:localhost:8080 -o ServerAliveInterval=60 curtburk@<YOUR_TAILSCALE_IP>
```

Keep this window open. The tunnel maps your laptop's `localhost:19080` to the Nano's `localhost:8080`.

**Step 2: Configure the extension**

Edit `background.js`:

```javascript
const BRIDGE_URL = "http://localhost:19080";
```

Edit `manifest.json`:

```json
"host_permissions": [
    "http://localhost:19080/*"
]
```

**Step 3: Reload and test**

Reload the extension in `edge://extensions/`, reload the Onshape tab, and click the ⚡ button.

**Troubleshooting Tailscale:**
- If `ssh -L` gives "Permission denied" on the port bind, another process is using that port. Pick a different local port (e.g., 29080).
- If the health check works but chat fails with "Failed to fetch," check the service worker console (`edge://extensions/` → click "service worker") for CORS errors. Ensure `host_permissions` in `manifest.json` matches the `BRIDGE_URL` exactly.
- The SSH tunnel must stay open for the duration of your session. If the window closes or the connection drops, the extension will show "Bridge offline."

## Configuration

All Bridge settings via environment variables (set in `docker-compose.yml`):

| Variable | Default | Description |
|---|---|---|
| `VLLM_BASE_URL` | `http://vllm:8000/v1` | vLLM endpoint (use container name in compose) |
| `VLLM_MODEL` | `Qwen/Qwen3-14B-AWQ` | Model name (must match what vLLM is serving) |
| `BRIDGE_API_KEYS` | `dev-test-key` | Comma-separated API keys |
| `BRIDGE_PORT` | `8080` | Bridge listen port |
| `SESSION_TTL_MINUTES` | `30` | Session expiry |
| `SESSION_MAX_TURNS` | `50` | Max conversation depth |
| `SYSTEM_PROMPT_BASE` | (see config.py) | Base system prompt |
| `CONTEXT_MAX_SIZE_BYTES` | `32768` | Max context payload size |

## API Endpoints

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/health` | GET | No | Bridge + vLLM status |
| `/api/chat` | POST | Yes | Send message, receive SSE stream |
| `/api/chat/{session_id}` | GET | Yes | Get conversation history |
| `/api/sessions` | GET | Yes | List active sessions |
| `/api/sessions/{session_id}` | DELETE | Yes | End a session |
| `/api/metrics` | GET | No | Token counts, latency, cloud cost comparison |

Auth: `Authorization: Bearer <api-key>` header.

## File Structure

```
zgx-ai-bridge/
  bridge/
    main.py          # FastAPI app, all endpoints
    config.py        # Environment variable loading
    context.py       # Context validation + prompt assembly
    inference.py     # Async vLLM client with SSE streaming
    sessions.py      # In-memory session store with TTL
    metrics.py       # Token/latency/cost tracking
    auth.py          # API key middleware
  docker-compose.yml          # vLLM (DFlash) + Bridge
  docker-compose.no-dflash.yml  # Fallback without speculative decoding
  Dockerfile                  # Bridge container
  requirements.txt
  start.sh                    # Run Bridge without Docker
  tasks/
    todo.md
    lessons.md
```

## Fallback (No DFlash)

If DFlash speculative decoding causes issues on your hardware:

```bash
docker compose down
docker compose -f docker-compose.no-dflash.yml up -d
```

Same model, same Bridge, same widget. Just standard autoregressive decoding.

## Running Bridge Without Docker

For development or when vLLM is already running separately:

```bash
pip install -r requirements.txt
VLLM_BASE_URL=http://localhost:8090/v1 VLLM_MODEL=Qwen/Qwen3.6-35B-A3B bash start.sh
```

## The Demo Narrative

**Beat 1: "It's just a browser extension."**
Show Onshape running on a standard x86 Windows laptop with the widget. Point out the ISV application is completely unmodified. No plugins, no SDK, no code changes.

**Beat 2: "It knows what you're looking at."**
Ask a question about the current design. The AI answers using workspace context. Switch to a different part. Ask the same question. Different answer. This is where the audience feels something.

**Beat 3: "Where did the data go?"**
Hit `/api/metrics`. Show the token counts, latency, cost comparison. Point at the two machines: "This x86 laptop is running the CAD application. This ARM64 box under the table is running the AI. Two different architectures, connected by nothing more than HTTP on the local network. The design data never left this room. And you didn't pay OpenAI a cent for that answer."

## What This Is Not

- Not a product. It's a technical demo for HP ZGX hardware positioning.
- Not multi-tenant. One Bridge instance serves one ISV.
- Not persistent. Sessions live in memory and die with the process.
- Not bidirectional. The AI reads context but cannot take actions in the host app.

## License

Internal HP demo. Not for distribution.
