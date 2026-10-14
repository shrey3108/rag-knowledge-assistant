document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const uploadStatus = document.getElementById("upload-status");
  const docList = document.getElementById("doc-list");
  const docCount = document.getElementById("doc-count");
  const statChunks = document.getElementById("stat-chunks");
  const refreshDocsBtn = document.getElementById("refresh-docs-btn");
  const chatForm = document.getElementById("chat-form");
  const queryInput = document.getElementById("query-input");
  const sendBtn = document.getElementById("send-btn");
  const messagesContainer = document.getElementById("messages-container");
  const clearChatBtn = document.getElementById("clear-chat-btn");
  const modelBadge = document.getElementById("model-badge");
  const healthBadge = document.getElementById("health-badge");
  const suggestionChips = document.querySelectorAll(".chip");
  const docFilterSelect = document.getElementById("doc-filter-select");

  // Session ID for multi-turn conversational memory
  let currentSessionId = localStorage.getItem("rag_session_id") || "sess_" + Date.now();
  localStorage.setItem("rag_session_id", currentSessionId);

  // Initial Load
  checkHealth();
  loadDocuments();

  // --- Health Check ---
  async function checkHealth() {
    try {
      const res = await fetch("/api/v1/health");
      if (!res.ok) throw new Error("Health check failed");
      const data = await res.json();
      modelBadge.textContent = `Model: ${data.model}`;
      healthBadge.textContent = `● Online`;
      healthBadge.style.color = "#6ee7b7";
      statChunks.textContent = `${data.total_indexed_chunks} Chunks Indexed`;
    } catch (err) {
      healthBadge.textContent = `● Offline`;
      healthBadge.style.color = "#f87171";
    }
  }

  // --- Documents Management ---
  async function loadDocuments() {
    try {
      const res = await fetch("/api/v1/documents");
      if (!res.ok) throw new Error("Failed to load documents");
      const data = await res.json();
      renderDocuments(data.documents);
      docCount.textContent = data.total_documents;
    } catch (err) {
      console.error(err);
    }
  }

  function renderDocuments(docs) {
    // Populate document filter dropdown
    if (docFilterSelect) {
      const currentSelected = docFilterSelect.value;
      docFilterSelect.innerHTML = `<option value="">🔍 All Documents</option>` +
        (docs || []).map(d => `<option value="${escapeHtml(d.document_name)}" ${currentSelected === d.document_name ? "selected" : ""}>📄 ${escapeHtml(d.document_name)}</option>`).join("");
    }

    if (!docs || docs.length === 0) {
      docList.innerHTML = `<li class="empty-state">No documents indexed yet. Upload one above!</li>`;
      return;
    }


    docList.innerHTML = docs
      .map(
        (d) => `
        <li class="doc-item">
          <div>
            <div class="doc-title" title="${escapeHtml(d.document_name)}">📄 ${escapeHtml(d.document_name)}</div>
            <div class="doc-meta">${d.chunk_count} chunk(s) &bull; ${d.total_pages} page(s)</div>
          </div>
          <button class="btn-delete-doc" data-doc="${escapeHtml(d.document_name)}" title="Delete document">🗑️</button>
        </li>
      `
      )
      .join("");

    // Attach delete listeners
    document.querySelectorAll(".btn-delete-doc").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        const docName = e.currentTarget.getAttribute("data-doc");
        if (confirm(`Remove '${docName}' from the knowledge base?`)) {
          await deleteDocument(docName);
        }
      });
    });
  }

  async function deleteDocument(docName) {
    try {
      const res = await fetch(`/api/v1/documents/${encodeURIComponent(docName)}`, {
        method: "DELETE",
      });
      if (res.ok) {
        showStatus(`Deleted '${docName}'`, "success");
        await loadDocuments();
        await checkHealth();
      } else {
        const err = await res.json();
        showStatus(`Failed to delete: ${err.detail}`, "error");
      }
    } catch (e) {
      showStatus(`Delete error: ${e.message}`, "error");
    }
  }

  // --- Upload Handler ---
  dropZone.addEventListener("click", () => fileInput.click());

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files.length > 0) {
      handleFiles(fileInput.files);
    }
  });

  async function handleFiles(files) {
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append("files", files[i]);
    }

    showStatus("Uploading and indexing documents...", "");

    try {
      const res = await fetch("/api/v1/documents/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();

      if (res.ok) {
        const msg = `Successfully indexed ${data.successful_count} file(s).`;
        showStatus(msg, "success");
        fileInput.value = "";
        await loadDocuments();
        await checkHealth();
      } else {
        showStatus(`Upload failed: ${data.detail || "Error"}`, "error");
      }
    } catch (err) {
      showStatus(`Upload error: ${err.message}`, "error");
    }
  }

  function showStatus(msg, type) {
    uploadStatus.textContent = msg;
    uploadStatus.className = `status-msg ${type}`;
    if (!msg) {
      uploadStatus.classList.add("hidden");
    }
  }

  refreshDocsBtn.addEventListener("click", async () => {
    await loadDocuments();
    await checkHealth();
  });

  // --- Chat & Query Handler ---
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = queryInput.value.trim();
    if (!query) return;

    submitQuery(query);
  });

  queryInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const query = queryInput.value.trim();
      if (query) submitQuery(query);
    }
  });

  suggestionChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const q = chip.getAttribute("data-q");
      queryInput.value = q;
      submitQuery(q);
    });
  });

  clearChatBtn.addEventListener("click", () => {
    currentSessionId = "sess_" + Date.now();
    localStorage.setItem("rag_session_id", currentSessionId);
    messagesContainer.innerHTML = "";
  });

  async function submitQuery(question) {
    // Append User Message
    appendUserMessage(question);
    queryInput.value = "";
    sendBtn.disabled = true;

    // Append Loading Assistant Message
    const loadingId = "loading-" + Date.now();
    appendLoadingMessage(loadingId);
    scrollToBottom();

    const selectedDoc = docFilterSelect ? docFilterSelect.value || null : null;
    const payload = {
      question: question,
      document_name: selectedDoc,
      session_id: currentSessionId,
    };

    try {
      const res = await fetch("/api/v1/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      removeMessage(loadingId);

      if (res.ok) {
        appendAssistantMessage(data);
      } else {
        appendErrorMessage(data.detail || "Failed to retrieve response from assistant.");
      }

    } catch (err) {
      removeMessage(loadingId);
      appendErrorMessage(`Network error: ${err.message}`);
    } finally {
      sendBtn.disabled = false;
      scrollToBottom();
    }
  }

  function appendUserMessage(text) {
    const el = document.createElement("div");
    el.className = "message user-message";
    el.innerHTML = `
      <div class="msg-avatar">👤</div>
      <div class="msg-body">
        <p>${escapeHtml(text)}</p>
      </div>
    `;
    messagesContainer.appendChild(el);
  }

  function appendLoadingMessage(id) {
    const el = document.createElement("div");
    el.className = "message assistant-message";
    el.id = id;
    el.innerHTML = `
      <div class="msg-avatar">🤖</div>
      <div class="msg-body">
        <div class="typing-indicator">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
    `;
    messagesContainer.appendChild(el);
  }

  function removeMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function appendErrorMessage(errorText) {
    const el = document.createElement("div");
    el.className = "message assistant-message";
    el.innerHTML = `
      <div class="msg-avatar">⚠️</div>
      <div class="msg-body" style="border-color: rgba(239, 68, 68, 0.4);">
        <p style="color: #fca5a5;">${escapeHtml(errorText)}</p>
      </div>
    `;
    messagesContainer.appendChild(el);
  }

  function appendAssistantMessage(data) {
    const el = document.createElement("div");
    el.className = "message assistant-message";

    const isAnswered = data.is_answered;
    const tagClass = isAnswered ? "tag-grounded" : "tag-unavailable";
    const tagText = isAnswered ? "✓ Grounded & Verified" : "⚠ Missing Information";
    const confidencePct = Math.round(data.confidence_score * 100);

    let evidenceHtml = "";
    if (data.evidence && data.evidence.length > 0) {
      const toggleId = "evidence-box-" + Date.now();
      const itemsHtml = data.evidence
        .map(
          (e, idx) => `
          <div class="evidence-card">
            <div class="evidence-header">
              <span class="evidence-source">#${idx + 1} ${escapeHtml(e.document_name)} (Page ${e.page_number})</span>
              <span class="evidence-score">Similarity: ${Math.round(e.similarity_score * 100)}%</span>
            </div>
            <div class="evidence-excerpt">"${escapeHtml(e.excerpt)}"</div>
          </div>
        `
        )
        .join("");

      evidenceHtml = `
        <div class="evidence-section">
          <button class="evidence-toggle" type="button" onclick="toggleEvidence('${toggleId}')">
            <span>📑 Evidence Sources (${data.evidence.length})</span>
            <span id="arrow-${toggleId}">▼</span>
          </button>
          <div class="evidence-content" id="${toggleId}" style="display: none !important; margin-top: 8px; flex-direction: column; gap: 8px;">
            ${itemsHtml}
          </div>
        </div>
      `;
    }

    el.innerHTML = `
      <div class="msg-avatar">🤖</div>
      <div class="msg-body">
        <p>${formatAnswer(data.answer)}</p>
        <div class="msg-meta-row">
          <span class="grounding-tag ${tagClass}">${tagText}</span>
          ${data.cached ? `<span class="grounding-tag tag-cached">⚡ Redis Cached</span>` : ""}
          <span class="confidence-indicator">Confidence: ${confidencePct}% &bull; ${data.retrieved_chunks_count} chunk(s)</span>
        </div>
        ${evidenceHtml}
      </div>
    `;
    messagesContainer.appendChild(el);
  }

  window.toggleEvidence = function (id) {
    const box = document.getElementById(id);
    const arrow = document.getElementById("arrow-" + id);
    if (!box) return;
    const isHidden = box.style.getPropertyValue("display") === "none" || box.style.display === "none";
    if (isHidden) {
      box.style.setProperty("display", "flex", "important");
      if (arrow) arrow.textContent = "▲";
    } else {
      box.style.setProperty("display", "none", "important");
      if (arrow) arrow.textContent = "▼";
    }
  };

  function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatAnswer(text) {
    if (!text) return "";

    // Convert in-text source citations into sleek badges
    let formatted = text.replace(/\[Source\s*#?(\d+)[,\s]+Page\s*(\d+)\]/gi, (match, src, pg) => {
      return `<span class="source-pill">📄 Source #${src} (P. ${pg})</span>`;
    });
    formatted = formatted.replace(/【Document:\s*([^,]+),\s*Page:\s*(\d+)】/gi, (match, doc, pg) => {
      return `<span class="source-pill">📄 ${escapeHtml(doc.trim())} (P. ${pg})</span>`;
    });

    // If marked.js is available via CDN
    if (window.marked && typeof window.marked.parse === "function") {
      try {
        return marked.parse(formatted);
      } catch (e) {
        console.warn("marked.parse error, using fallback:", e);
      }
    }

    // Built-in offline markdown fallback (tables, bold, lists, headings)
    return parseMarkdownFallback(formatted);
  }

  function parseMarkdownFallback(text) {
    const lines = text.split("\n");
    let inTable = false;
    let tableHtml = "";
    let result = [];

    for (let i = 0; i < lines.length; i++) {
      let rawLine = lines[i];
      let line = rawLine.trim();

      // Check table row
      if (line.startsWith("|") && line.endsWith("|")) {
        // Table separator row |---|---|
        if (/^\|[\s\-:|]+\|$/.test(line)) {
          continue;
        }
        const cells = line.slice(1, -1).split("|").map(c => c.trim());
        if (!inTable) {
          inTable = true;
          tableHtml = "<table><thead><tr>" + cells.map(c => `<th>${formatInline(c)}</th>`).join("") + "</tr></thead><tbody>";
        } else {
          tableHtml += "<tr>" + cells.map(c => `<td>${formatInline(c)}</td>`).join("") + "</tr>";
        }
        continue;
      } else {
        if (inTable) {
          tableHtml += "</tbody></table>";
          result.push(tableHtml);
          inTable = false;
          tableHtml = "";
        }
      }

      if (line.startsWith("### ")) {
        result.push(`<h3>${formatInline(line.slice(4))}</h3>`);
      } else if (line.startsWith("## ")) {
        result.push(`<h2>${formatInline(line.slice(3))}</h2>`);
      } else if (line.startsWith("# ")) {
        result.push(`<h1>${formatInline(line.slice(2))}</h1>`);
      } else if (line.startsWith("* ") || line.startsWith("- ")) {
        result.push(`<ul><li>${formatInline(line.slice(2))}</li></ul>`);
      } else if (line === "") {
        result.push("<br>");
      } else {
        result.push(`<p>${formatInline(line)}</p>`);
      }
    }

    if (inTable) {
      tableHtml += "</tbody></table>";
      result.push(tableHtml);
    }

    return result.join("");
  }

  function formatInline(str) {
    return str
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/<br>/gi, "<br>");
  }
});
