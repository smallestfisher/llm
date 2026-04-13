function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderTable(metadata) {
  if (!metadata || !metadata.columns || !metadata.columns.length || !metadata.rows || !metadata.rows.length) {
    return "";
  }

  const head = metadata.columns.map((col) => `<th>${escapeHtml(col)}</th>`).join("");
  const body = metadata.rows
    .map(
      (row) =>
        `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`
    )
    .join("");
  const metaText = metadata.row_count
    ? `共 ${escapeHtml(metadata.row_count)} 条记录${metadata.truncated ? "，当前结果已截断" : ""}`
    : `查询返回 ${metadata.rows.length} 行`;

  return `
    <div class="result-meta">${metaText}</div>
    <div class="table-wrap">
      <table class="result-table">
        <thead><tr>${head}</tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>
  `;
}

function renderSql(metadata) {
  if (!metadata || !metadata.sql_query) {
    return "";
  }
  return `
    <details class="sql-box">
      <summary>查看 SQL</summary>
      <pre>${escapeHtml(metadata.sql_query)}</pre>
    </details>
  `;
}

function createMessageElement(role, content, metadata) {
  const article = document.createElement("article");
  article.className = `message message-${role}`;
  const label = role === "user" ? "你" : "BOE Data Copilot";
  const avatar = role === "user" ? "你" : "AI";
  const timestamp = new Date().toLocaleString();
  article.innerHTML = `
    <div class="message-head">
      <div class="message-identity">
        <span class="message-avatar">${avatar}</span>
        <span>${label}</span>
      </div>
      <span>${timestamp}</span>
    </div>
    <div class="message-body">${escapeHtml(content).replace(/\n/g, "<br>")}</div>
    ${role === "assistant" ? renderTable(metadata) : ""}
    ${role === "assistant" ? renderSql(metadata) : ""}
  `;
  return article;
}

function appendMessage(container, role, content, metadata) {
  const article = createMessageElement(role, content, metadata);
  container.appendChild(article);
  container.scrollTop = container.scrollHeight;
  return article;
}

function appendThinkingMessage(container) {
  const article = document.createElement("article");
  article.className = "message message-assistant message-thinking";
  article.innerHTML = `
    <div class="message-head">
      <div class="message-identity">
        <span class="message-avatar">AI</span>
        <span>BOE Data Copilot</span>
      </div>
      <span>思考中</span>
    </div>
    <div class="message-body thinking-status">正在启动工作流...</div>
  `;
  container.appendChild(article);
  container.scrollTop = container.scrollHeight;
  return article;
}

function updateThinkingMessage(article, message) {
  if (!article) {
    return;
  }
  const body = article.querySelector(".thinking-status");
  if (body) {
    body.textContent = message;
  }
  article.scrollIntoView({ block: "end" });
}

function removeThinkingMessage(article) {
  if (article && article.parentNode) {
    article.parentNode.removeChild(article);
  }
}

function handleStreamLine(line, handlers) {
  if (!line.trim()) {
    return;
  }
  const payload = JSON.parse(line);
  if (payload.type === "status") {
    handlers.onStatus?.(payload);
    return;
  }
  if (payload.type === "final") {
    handlers.onFinal?.(payload);
    return;
  }
  if (payload.type === "error") {
    handlers.onError?.(payload);
    return;
  }
  if (payload.type === "cancelled") {
    handlers.onCancelled?.(payload);
  }
}

function initDeleteForms() {
  const forms = document.querySelectorAll("[data-confirm-delete]");
  forms.forEach((form) => {
    form.addEventListener("submit", (event) => {
      const button = form.querySelector("button[type='submit']");
      if (button?.disabled) {
        event.preventDefault();
        return;
      }
      const confirmed = window.confirm("删除后将无法恢复，该对话下的全部消息都会被清除。确认删除吗？");
      if (!confirmed) {
        event.preventDefault();
        return;
      }
      if (button) {
        button.disabled = true;
        button.dataset.originalText = button.textContent;
        if (!button.querySelector("svg")) {
          button.textContent = "删除中...";
        }
      }
    });
  });
}

function initChat() {
  const root = document.querySelector("[data-chat-root]");
  if (!root) {
    return;
  }

  const form = document.getElementById("chat-form");
  const input = document.getElementById("question-input");
  const button = document.getElementById("send-button");
  const regenerateButton = document.getElementById("regenerate-button");
  const messages = document.getElementById("chat-messages");
  const threadId = root.getAttribute("data-thread-id");
  const promptButtons = document.querySelectorAll("[data-prompt]");
  let isComposing = false;
  let activeController = null;
  let runCompleted = true;

  const setDeleteActionsDisabled = (disabled) => {
    document.querySelectorAll(".thread-delete-button").forEach((el) => {
      el.disabled = disabled;
    });
  };

  const removeEmptyState = () => {
    const emptyState = messages.querySelector(".empty-state");
    if (emptyState) {
      emptyState.remove();
    }
  };

  const syncHeight = () => {
    input.style.height = "auto";
    input.style.height = `${Math.max(84, input.scrollHeight)}px`;
  };

  const setIdleState = () => {
    activeController = null;
    button.disabled = false;
    button.textContent = "发送";
    if (regenerateButton) {
      regenerateButton.disabled = false;
    }
    setDeleteActionsDisabled(false);
    input.focus();
  };

  const setBusyState = () => {
    button.disabled = false;
    button.textContent = "停止";
    if (regenerateButton) {
      regenerateButton.disabled = true;
    }
    setDeleteActionsDisabled(true);
  };

  const streamHandlers = (thinkingMessage) => ({
    onStatus(payload) {
      if (payload.thread_id && payload.thread_id !== threadId) {
        return;
      }
      updateThinkingMessage(thinkingMessage, payload.message || "正在处理中...");
    },
    onFinal(payload) {
      if (payload.thread_id !== threadId) {
        return;
      }
      runCompleted = true;
      removeThinkingMessage(thinkingMessage);
      appendMessage(messages, "assistant", payload.answer, payload.metadata);
      if (payload.thread_title) {
        document.title = `${payload.thread_title} | BOE Data Copilot`;
      }
    },
    onError(payload) {
      if (payload.thread_id && payload.thread_id !== threadId) {
        return;
      }
      runCompleted = true;
      removeThinkingMessage(thinkingMessage);
      appendMessage(messages, "assistant", payload.detail || "处理出错");
    },
    onCancelled(payload) {
      if (payload.thread_id && payload.thread_id !== threadId) {
        return;
      }
      runCompleted = true;
      removeThinkingMessage(thinkingMessage);
      appendMessage(messages, "assistant", "已停止本次回复。");
    },
  });

  async function consumeStream(response, thinkingMessage) {
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || `请求失败 (${response.status})`);
    }
    if (!response.body) {
      throw new Error("响应体为空");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    const handlers = streamHandlers(thinkingMessage);

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        handleStreamLine(line, handlers);
      }

      if (done) {
        if (buffer.trim()) {
          handleStreamLine(buffer, handlers);
        }
        break;
      }
    }
  }

  async function startRun({ url, question, appendUser = false }) {
    if (activeController) {
      return;
    }

    removeEmptyState();
    if (appendUser && question) {
      appendMessage(messages, "user", question);
    }
    const thinkingMessage = appendThinkingMessage(messages);
    runCompleted = false;
    activeController = new AbortController();
    setBusyState();

    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: question != null ? JSON.stringify({ question }) : null,
        signal: activeController.signal,
      });
      await consumeStream(response, thinkingMessage);
      removeThinkingMessage(thinkingMessage);
    } catch (error) {
      removeThinkingMessage(thinkingMessage);
      if (error.name === "AbortError") {
        if (!runCompleted) {
          appendMessage(messages, "assistant", "已停止本次回复。");
        }
      } else {
        appendMessage(messages, "assistant", `处理出错：${error.message}`);
      }
    } finally {
      runCompleted = true;
      setIdleState();
    }
  }

  syncHeight();
  input.addEventListener("input", syncHeight);
  input.addEventListener("compositionstart", () => {
    isComposing = true;
  });
  input.addEventListener("compositionend", () => {
    isComposing = false;
  });
  input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey || isComposing) {
      return;
    }
    event.preventDefault();
    form.requestSubmit();
  });

  promptButtons.forEach((buttonEl) => {
    buttonEl.addEventListener("click", () => {
      input.value = buttonEl.getAttribute("data-prompt") || "";
      syncHeight();
      input.focus();
    });
  });

  button.addEventListener("click", async (event) => {
    if (!activeController) {
      return;
    }
    event.preventDefault();
    runCompleted = true;
    activeController.abort();
    try {
      await fetch(`/api/chat/${threadId}/cancel`, { method: "POST" });
    } catch {
      // ignore cancel request errors
    }
  });

  if (regenerateButton) {
    regenerateButton.addEventListener("click", async () => {
      if (activeController) {
        return;
      }
      await startRun({ url: `/api/chat/${threadId}/regenerate`, question: null, appendUser: false });
    });
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (activeController) {
      return;
    }
    const question = input.value.trim();
    if (!question) {
      input.focus();
      return;
    }

    input.value = "";
    syncHeight();
    await startRun({ url: `/api/chat/${threadId}`, question, appendUser: true });
  });

  setIdleState();
}

document.addEventListener("DOMContentLoaded", () => {
  initDeleteForms();
  initChat();
});

  const removeEmptyState = () => {
    const emptyState = messages.querySelector(".empty-state");
    if (emptyState) {
      emptyState.remove();
    }
  };

  const syncHeight = () => {
    input.style.height = "auto";
    input.style.height = `${Math.max(84, input.scrollHeight)}px`;
  };

  const setIdleState = () => {
    activeController = null;
    button.disabled = false;
    button.textContent = "发送";
    regenerateButton.disabled = false;
    input.focus();
  };

  const setBusyState = () => {
    button.disabled = false;
    button.textContent = "停止";
    regenerateButton.disabled = true;
  };

  const streamHandlers = (thinkingMessage) => ({
    onStatus(payload) {
      if (payload.thread_id && payload.thread_id !== threadId) {
        return;
      }
      updateThinkingMessage(thinkingMessage, payload.message || "正在处理中...");
    },
    onFinal(payload) {
      if (payload.thread_id !== threadId) {
        return;
      }
      runCompleted = true;
      removeThinkingMessage(thinkingMessage);
      appendMessage(messages, "assistant", payload.answer, payload.metadata);
      if (payload.thread_title) {
        document.title = `${payload.thread_title} | BOE Data Copilot`;
      }
    },
    onError(payload) {
      if (payload.thread_id && payload.thread_id !== threadId) {
        return;
      }
      runCompleted = true;
      removeThinkingMessage(thinkingMessage);
      appendMessage(messages, "assistant", payload.detail || "处理出错");
    },
    onCancelled(payload) {
      if (payload.thread_id && payload.thread_id !== threadId) {
        return;
      }
      runCompleted = true;
      removeThinkingMessage(thinkingMessage);
      appendMessage(messages, "assistant", "已停止本次回复。");
    },
  });

  async function consumeStream(response, thinkingMessage) {
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || `请求失败 (${response.status})`);
    }
    if (!response.body) {
      throw new Error("响应体为空");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    const handlers = streamHandlers(thinkingMessage);

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        handleStreamLine(line, handlers);
      }

      if (done) {
        if (buffer.trim()) {
          handleStreamLine(buffer, handlers);
        }
        break;
      }
    }
  }

  async function startRun({ url, question, appendUser = false }) {
    if (activeController) {
      return;
    }

    removeEmptyState();
    if (appendUser && question) {
      appendMessage(messages, "user", question);
    }
    const thinkingMessage = appendThinkingMessage(messages);
    runCompleted = false;
    activeController = new AbortController();
    setBusyState();

    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: question != null ? JSON.stringify({ question }) : null,
        signal: activeController.signal,
      });
      await consumeStream(response, thinkingMessage);
      removeThinkingMessage(thinkingMessage);
    } catch (error) {
      removeThinkingMessage(thinkingMessage);
      if (error.name === "AbortError") {
        if (!runCompleted) {
          appendMessage(messages, "assistant", "已停止本次回复。");
        }
      } else {
        appendMessage(messages, "assistant", `处理出错：${error.message}`);
      }
    } finally {
      runCompleted = true;
      setIdleState();
    }
  }

  syncHeight();
  input.addEventListener("input", syncHeight);
  input.addEventListener("compositionstart", () => {
    isComposing = true;
  });
  input.addEventListener("compositionend", () => {
    isComposing = false;
  });
  input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey || isComposing) {
      return;
    }
    event.preventDefault();
    form.requestSubmit();
  });

  promptButtons.forEach((buttonEl) => {
    buttonEl.addEventListener("click", () => {
      input.value = buttonEl.getAttribute("data-prompt") || "";
      syncHeight();
      input.focus();
    });
  });

  button.addEventListener("click", async (event) => {
    if (!activeController) {
      return;
    }
    event.preventDefault();
    runCompleted = true;
    activeController.abort();
    try {
      await fetch(`/api/chat/${threadId}/cancel`, { method: "POST" });
    } catch {
      // ignore cancel request errors
    }
  });

  regenerateButton.addEventListener("click", async () => {
    if (activeController) {
      return;
    }
    await startRun({ url: `/api/chat/${threadId}/regenerate`, question: null, appendUser: false });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (activeController) {
      return;
    }
    const question = input.value.trim();
    if (!question) {
      input.focus();
      return;
    }

    input.value = "";
    syncHeight();
    await startRun({ url: `/api/chat/${threadId}`, question, appendUser: true });
  });
}

document.addEventListener("DOMContentLoaded", initChat);
