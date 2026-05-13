// Background service worker — proxies HTTP requests to the Bridge.
// Content scripts on HTTPS pages can't fetch HTTP endpoints (mixed content).
// The background script has no such restriction.

const BRIDGE_URL = "http://192.168.xx.xxx:8080";
const API_KEY = "dev-test-key";

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "bridge-health") {
    fetchHealth().then(sendResponse);
    return true; // keep channel open for async response
  }

  if (msg.type === "bridge-chat") {
    fetchChat(msg.payload).then(sendResponse);
    return true;
  }
});

async function fetchHealth() {
  try {
    const res = await fetch(`${BRIDGE_URL}/api/health`, {
      method: "GET",
      signal: AbortSignal.timeout(5000),
    });
    if (res.ok) {
      const data = await res.json();
      return { ok: true, data };
    }
    return { ok: false, error: `HTTP ${res.status}` };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

async function fetchChat(payload) {
  try {
    const res = await fetch(`${BRIDGE_URL}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${API_KEY}`,
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      return { ok: false, error: `HTTP ${res.status}` };
    }

    // Read the full SSE stream and return it as text.
    // We can't stream from background to content script via sendResponse,
    // so we buffer the full response and parse SSE events.
    const text = await res.text();
    const events = [];

    for (const line of text.split("\n")) {
      if (!line.startsWith("data: ")) continue;
      const data = line.slice(6).trim();
      if (!data) continue;
      try {
        events.push(JSON.parse(data));
      } catch {
        // skip non-JSON
      }
    }

    return { ok: true, events };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}
