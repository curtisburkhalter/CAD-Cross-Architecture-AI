# ZGX AI Bridge - TODO

## Phase 1: Bridge Core (current)
- [x] config.py - env var loading with defaults
- [x] sessions.py - in-memory session store with TTL
- [x] context.py - validation, serialization, prompt assembly
- [x] inference.py - async vLLM client with SSE streaming
- [x] metrics.py - token/latency/session counters + cloud cost comparison
- [x] auth.py - API key middleware
- [x] main.py - FastAPI app, all endpoints
- [x] start.sh
- [ ] Test against live vLLM on Nano

## Phase 2: Widget v1
- [ ] Update Chrome extension content.js to use real Bridge
- [ ] Or: build standalone zgx-bridge-widget.js served by Bridge
- [ ] Streaming token display
- [ ] Context passing from Onshape DOM

## Phase 3: Observability
- [ ] Token counting badges in widget
- [ ] Latency badges per response
- [ ] /api/metrics dashboard page (HTML served by Bridge)
- [ ] Cloud cost comparison display

## Phase 4: Demo Polish
- [ ] Mock ISV app (if not using Onshape directly)
- [ ] Network topology visualization
- [ ] One-click demo reset
- [ ] Pre-baked golden path responses

## Phase 5: Containerization
- [ ] Dockerfile (linux/arm64 for Nano)
- [ ] docker-compose.yml (Bridge + vLLM co-located)
