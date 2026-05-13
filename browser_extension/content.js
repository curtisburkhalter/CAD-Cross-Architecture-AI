// ZGX Bridge Test Extension v2 — content script
// All HTTP requests go through the background service worker
// to avoid mixed content (HTTPS page -> HTTP bridge) blocks.

(function () {
  "use strict";

  let panelOpen = false;
  let sessionId = crypto.randomUUID();
  let bridgeStatus = "unknown";
  let currentContext = {};

  // ── Build DOM ───────────────────────────────────────────────────
  function buildWidget() {
    const root = document.createElement("div");
    root.id = "zgx-bridge-widget";

    root.innerHTML = `
      <div id="zgx-bridge-panel">
        <div id="zgx-bridge-header">
          <h3>ZGX AI Bridge</h3>
          <div class="zgx-status">
            <span class="zgx-status-label" id="zgx-status-text">checking...</span>
            <span class="zgx-status-dot" id="zgx-status-dot"></span>
          </div>
        </div>
        <div id="zgx-bridge-messages"></div>
        <div id="zgx-bridge-context">
          <details>
            <summary>Context captured</summary>
            <pre id="zgx-context-json" style="margin:4px 0 0;white-space:pre-wrap;font-size:11px;color:#888;">none</pre>
          </details>
        </div>
        <div id="zgx-bridge-input-area">
          <textarea id="zgx-bridge-input" rows="1" placeholder="Ask something about your model..."></textarea>
          <button id="zgx-bridge-send">Send</button>
        </div>
      </div>
      <button id="zgx-bridge-toggle" title="ZGX AI Bridge">⚡</button>
    `;

    document.body.appendChild(root);

    document.getElementById("zgx-bridge-toggle").addEventListener("click", togglePanel);
    document.getElementById("zgx-bridge-send").addEventListener("click", sendMessage);
    document.getElementById("zgx-bridge-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }

  function togglePanel() {
    panelOpen = !panelOpen;
    const panel = document.getElementById("zgx-bridge-panel");
    panel.classList.toggle("open", panelOpen);

    if (panelOpen) {
      scrapeContext();
      document.getElementById("zgx-bridge-input").focus();
    }
  }

  // ── Messages ────────────────────────────────────────────────────
  function addMessage(text, type) {
    const container = document.getElementById("zgx-bridge-messages");
    const msg = document.createElement("div");
    msg.className = `zgx-msg ${type}`;
    msg.textContent = text;
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
  }

  // ── Bridge connectivity test ────────────────────────────────────
  async function checkBridge() {
    const dot = document.getElementById("zgx-status-dot");
    const label = document.getElementById("zgx-status-text");

    const result = await chrome.runtime.sendMessage({ type: "bridge-health" });

    if (result && result.ok) {
      bridgeStatus = "ok";
      dot.className = "zgx-status-dot ok";
      label.textContent = "Bridge connected";
      addMessage(
        `Bridge connected. vLLM: ${result.data?.vllm_status || "unknown"}`,
        "system"
      );
    } else {
      bridgeStatus = "fail";
      dot.className = "zgx-status-dot fail";
      label.textContent = "Bridge offline";
      addMessage(
        `Cannot reach Bridge. Error: ${result?.error || "unknown"}`,
        "system"
      );
    }
  }

  // ── Context scraping ────────────────────────────────────────────
  function scrapeContext() {
    const ctx = {
      url: window.location.href,
      timestamp: new Date().toISOString(),
      documentName: null,
      tabInfo: [],
      pageType: "unknown",
    };

    const title = document.title;
    if (title) {
      const parts = title.split("|").map((s) => s.trim());
      if (parts.length > 1) {
        ctx.documentName = parts[0];
      }
    }

    const path = window.location.pathname;
    if (path.includes("/documents/")) {
      ctx.pageType = "document";
      const urlParts = path.split("/").filter(Boolean);
      const docIdx = urlParts.indexOf("documents");
      if (docIdx !== -1 && urlParts[docIdx + 1]) {
        ctx.documentId = urlParts[docIdx + 1];
      }
    } else if (path === "/" || path === "") {
      ctx.pageType = "dashboard";
    }

    const tabs = document.querySelectorAll(
      '[class*="tab-name"], [class*="tab-label"], [data-testid*="tab"]'
    );
    tabs.forEach((tab) => {
      const text = tab.textContent?.trim();
      if (text) ctx.tabInfo.push(text);
    });

    const featureItems = document.querySelectorAll(
      '[class*="feature-name"], [class*="tree-item-label"]'
    );
    if (featureItems.length > 0) {
      ctx.featureTree = [];
      featureItems.forEach((item, i) => {
        if (i < 20) {
          ctx.featureTree.push(item.textContent?.trim());
        }
      });
    }

    currentContext = ctx;
    const pre = document.getElementById("zgx-context-json");
    if (pre) {
      pre.textContent = JSON.stringify(ctx, null, 2);
    }

    return ctx;
  }

  // ── Send message to Bridge ──────────────────────────────────────
  async function sendMessage() {
    const input = document.getElementById("zgx-bridge-input");
    const sendBtn = document.getElementById("zgx-bridge-send");
    const message = input.value.trim();
    if (!message) return;

    addMessage(message, "user");
    input.value = "";
    sendBtn.disabled = true;

    scrapeContext();

    if (bridgeStatus !== "ok") {
      addMessage("Bridge is not connected.", "error");
      sendBtn.disabled = false;
      return;
    }

    // Send via background script to avoid mixed content
    const container = document.getElementById("zgx-bridge-messages");
    const msgEl = document.createElement("div");
    msgEl.className = "zgx-msg assistant";
    msgEl.textContent = "Thinking...";
    container.appendChild(msgEl);
    container.scrollTop = container.scrollHeight;

    const result = await chrome.runtime.sendMessage({
      type: "bridge-chat",
      payload: {
        session_id: sessionId,
        message: message,
        context: currentContext,
      },
    });

    if (!result || !result.ok) {
      msgEl.remove();
      addMessage(`Request failed: ${result?.error || "unknown error"}`, "error");
      sendBtn.disabled = false;
      return;
    }

    // Process the buffered SSE events
    let fullResponse = "";
    for (const event of result.events) {
      if (event.type === "token") {
        fullResponse += event.content;
      } else if (event.type === "done") {
        const usage = event.usage || {};
        addMessage(
          `tokens: ${usage.prompt_tokens || "?"}p / ${usage.completion_tokens || "?"}c` +
            ` | latency: ${event.latency_ms || "?"}ms`,
          "system"
        );
      } else if (event.type === "error") {
        addMessage(event.message || "Unknown error", "error");
      }
    }

    if (fullResponse) {
      msgEl.textContent = fullResponse;
    } else {
      msgEl.remove();
    }

    container.scrollTop = container.scrollHeight;
    sendBtn.disabled = false;
    document.getElementById("zgx-bridge-input").focus();
  }

  // ── Init ────────────────────────────────────────────────────────
  function init() {
    console.log("[ZGX Bridge] Injecting widget into Onshape...");
    buildWidget();

    addMessage("ZGX AI Bridge widget loaded.", "system");
    checkBridge();

    setInterval(scrapeContext, 5000);

    console.log("[ZGX Bridge] Widget injected. Check bottom-right corner.");
  }

  if (document.readyState === "complete") {
    init();
  } else {
    window.addEventListener("load", init);
  }
})();
