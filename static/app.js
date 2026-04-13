function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderTable(metadata) {
  if (!metadata || !metadata.columns || !metadata.columns.length || !metadata.rows || !metadata.rows.length) {
    return "";
  }

  const head = metadata.columns.map((col) => `<th>${escapeHtml(col)}</th>`).join("");
  const body = metadata.rows
    .map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`)
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

function renderAssistantActions(messageId) {
  if (!messageId) {
    return "";
  }
  return `
    <div class="message-actions">
      <button
        type="button"
        class="button button-secondary button-compact message-regenerate-button"
        data-regenerate-message-id="${escapeHtml(messageId)}"
      >重新生成此条</button>
    </div>
  `;
}

function createMessageElement(role, content, metadata = {}, messageId = "") {
  const article = document.createElement("article");
  article.className = `message message-${role}`;
  if (messageId) {
    article.dataset.messageId = String(messageId);
  }
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
    ${role === "assistant" ? renderAssistantActions(messageId) : ""}
    ${role === "assistant" ? renderTable(metadata) : ""}
    ${role === "assistant" ? renderSql(metadata) : ""}
  `;
  return article;
}

function appendMessage(container, role, content, metadata = {}, messageId = "") {
  const article = createMessageElement(role, content, metadata, messageId);
  container.appendChild(article);
  container.scrollTop = container.scrollHeight;
  return article;
}

const THINKING_STEPS = [
  { key: "route", label: "识别问题" },
  { key: "guard", label: "安全检查" },
  { key: "filters", label: "整理条件" },
  { key: "schema", label: "装载结构" },
  { key: "sql", label: "编写 SQL" },
  { key: "execute", label: "执行查询" },
  { key: "reflect", label: "修正 SQL" },
  { key: "answer", label: "生成回答" },
];

const NODE_TO_STEP = {
  route_intent: "route",
  skill_dispatch: "route",
  check_guard: "guard",
  refine_filters: "filters",
  get_schema: "schema",
  write_sql: "sql",
  execute_sql: "execute",
  reflect_sql: "reflect",
  generate_answer: "answer",
};

function renderThinkingSteps(currentStep, currentMessage = "正在启动工作流...") {
  const currentIndex = THINKING_STEPS.findIndex((step) => step.key === currentStep);
  const items = THINKING_STEPS.map((step, index) => {
    let state = "pending";
    let marker = "○";
    if (currentIndex >= 0 && index < currentIndex) {
      state = "completed";
      marker = "✓";
    } else if (step.key === currentStep) {
      state = "active";
      marker = "●";
    }
    return `
      <li class="thinking-step thinking-step-${state}">
        <span class="thinking-step-marker">${marker}</span>
        <div class="thinking-step-content">
          <div class="thinking-step-title">${step.label}</div>
          ${step.key === currentStep ? `<div class="thinking-step-detail">${escapeHtml(currentMessage)}</div>` : ""}
        </div>
      </li>
    `;
  }).join("");

  return `
    <div class="thinking-panel">
      <div class="thinking-summary">${escapeHtml(currentMessage)}</div>
      <ol class="thinking-steps">${items}</ol>
    </div>
  `;
}

function appendThinkingMessage(container) {
  const article = document.createElement("article");
  article.className = "message message-assistant message-thinking";
  article.dataset.currentStep = "";
  article.innerHTML = `
    <div class="message-head">
      <div class="message-identity">
        <span class="message-avatar">AI</span>
        <span>BOE Data Copilot</span>
      </div>
      <span>处理中</span>
    </div>
    <div class="message-body thinking-status">${renderThinkingSteps("", "正在启动工作流...")}</div>
  `;
  container.appendChild(article);
  container.scrollTop = container.scrollHeight;
  return article;
}

function updateThinkingMessage(article, nodeName, message) {
  if (!article) {
    return;
  }
  const body = article.querySelector(".thinking-status");
  if (!body) {
    return;
  }
  const stepKey = NODE_TO_STEP[nodeName] || article.dataset.currentStep || "";
  article.dataset.currentStep = stepKey;
  body.innerHTML = renderThinkingSteps(stepKey, message);
  article.scrollIntoView({ block: "end" });
}

function completeThinkingMessage(article, message = "已完成") {
  if (!article) {
    return;
  }
  const body = article.querySelector(".thinking-status");
  if (!body) {
    return;
  }
  body.innerHTML = renderThinkingSteps("answer", message);
}

function cancelThinkingMessage(article, message = "已停止本次回复。") {
  if (!article) {
    return;
  }
  const body = article.querySelector(".thinking-status");
  if (!body) {
    return;
  }
  const stepKey = article.dataset.currentStep || "";
  body.innerHTML = renderThinkingSteps(stepKey, message);
}

function failThinkingMessage(article, message) {
  if (!article) {
    return;
  }
  const body = article.querySelector(".thinking-status");
  if (!body) {
    return;
  }
  const stepKey = article.dataset.currentStep || "";
  body.innerHTML = renderThinkingSteps(stepKey, message);
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
  const sendButton = document.getElementById("send-button");
  const messages = document.getElementById("chat-messages");
  const threadId = root.getAttribute("data-thread-id");
  const promptButtons = document.querySelectorAll("[data-prompt]");
  let isComposing = false;
  let activeController = null;
  let activeRegenerateButton = null;
  let runCompleted = true;

  const setDeleteActionsDisabled = (disabled) => {
    document.querySelectorAll(".thread-delete-button").forEach((el) => {
      el.disabled = disabled;
    });
  };

  const setRegenerateButtonsDisabled = (disabled, exceptButton = null) => {
    document.querySelectorAll(".message-regenerate-button").forEach((button) => {
      button.disabled = disabled;
      if (exceptButton && button === exceptButton) {
        button.disabled = disabled;
      }
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
    activeRegenerateButton = null;
    sendButton.disabled = false;
    sendButton.textContent = "发送";
    setDeleteActionsDisabled(false);
    setRegenerateButtonsDisabled(false);
    input.focus();
  };

  const setBusyState = () => {
    sendButton.disabled = false;
    sendButton.textContent = "停止";
    setDeleteActionsDisabled(true);
    setRegenerateButtonsDisabled(true);
    if (activeRegenerateButton) {
      activeRegenerateButton.disabled = true;
    }
  };

  const streamHandlers = (thinkingMessage) => ({
    onStatus(payload) {
      if (payload.thread_id && payload.thread_id !== threadId) {
        return;
      }
      updateThinkingMessage(thinkingMessage, payload.node || "", payload.message || "正在处理中...");
    },
    onFinal(payload) {
      if (payload.thread_id !== threadId) {
        return;
      }
      runCompleted = true;
      completeThinkingMessage(thinkingMessage, "已完成，正在展示结果");
      removeThinkingMessage(thinkingMessage);
      appendMessage(messages, "assistant", payload.answer, payload.metadata, payload.message_id || "");
      if (payload.thread_title) {
        document.title = `${payload.thread_title} | BOE Data Copilot`;
      }
    },
    onError(payload) {
      if (payload.thread_id && payload.thread_id !== threadId) {
        return;
      }
      runCompleted = true;
      failThinkingMessage(thinkingMessage, payload.detail || "处理出错");
      removeThinkingMessage(thinkingMessage);
      appendMessage(messages, "assistant", payload.detail || "处理出错");
    },
    onCancelled(payload) {
      if (payload.thread_id && payload.thread_id !== threadId) {
        return;
      }
      runCompleted = true;
      cancelThinkingMessage(thinkingMessage, "已停止本次回复。");
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

  async function startRun({ url, question = null, appendUser = false, regenerateButton = null }) {
    if (activeController) {
      return;
    }

    removeEmptyState();
    if (appendUser && question) {
      appendMessage(messages, "user", question);
    }

    if (regenerateButton) {
      activeRegenerateButton = regenerateButton;
      const assistantMessage = regenerateButton.closest(".message-assistant");
      if (assistantMessage) {
        assistantMessage.remove();
      }
    }

    const thinkingMessage = appendThinkingMessage(messages);
    runCompleted = false;
    activeController = new AbortController();
    setBusyState();

    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: question != null ? JSON.stringify({ question }) : JSON.stringify({ assistant_message_id: Number(regenerateButton?.dataset.regenerateMessageId) }),
        signal: activeController.signal,
      });
      await consumeStream(response, thinkingMessage);
      removeThinkingMessage(thinkingMessage);
    } catch (error) {
      removeThinkingMessage(thinkingMessage);
      if (error.name === "AbortError") {
        // wait for backend cancelled event; do not append a duplicate local message
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

  messages.addEventListener("click", async (event) => {
    const target = event.target instanceof Element ? event.target.closest(".message-regenerate-button") : null;
    if (!target || activeController) {
      return;
    }
    await startRun({
      url: `/api/chat/${threadId}/regenerate`,
      regenerateButton: target,
    });
  });

  sendButton.addEventListener("click", async (event) => {
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
