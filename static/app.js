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
  }
}

function initChat() {
  const root = document.querySelector("[data-chat-root]");
  if (!root) {
    return;
  }

  const form = document.getElementById("chat-form");
  const input = document.getElementById("question-input");
  const button = document.getElementById("send-button");
  const messages = document.getElementById("chat-messages");
  const threadId = root.getAttribute("data-thread-id");
  const promptButtons = document.querySelectorAll("[data-prompt]");
  let isComposing = false;

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

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question) {
      input.focus();
      return;
    }

    removeEmptyState();
    appendMessage(messages, "user", question);
    const thinkingMessage = appendThinkingMessage(messages);
    button.disabled = true;
    button.textContent = "处理中...";
    input.value = "";
    syncHeight();

    try {
      const response = await fetch(`/api/chat/${threadId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      if (!response.ok) {
        throw new Error(`请求失败 (${response.status})`);
      }

      if (!response.body) {
        throw new Error("响应体为空");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          handleStreamLine(line, {
            onStatus(payload) {
              updateThinkingMessage(thinkingMessage, payload.message || "正在处理中...");
            },
            onFinal(payload) {
              removeThinkingMessage(thinkingMessage);
              appendMessage(messages, "assistant", payload.answer, payload.metadata);
              if (payload.thread_title) {
                document.title = `${payload.thread_title} | BOE Data Copilot`;
              }
            },
            onError(payload) {
              removeThinkingMessage(thinkingMessage);
              appendMessage(messages, "assistant", payload.detail || "处理出错");
            },
          });
        }

        if (done) {
          if (buffer.trim()) {
            handleStreamLine(buffer, {
              onStatus(payload) {
                updateThinkingMessage(thinkingMessage, payload.message || "正在处理中...");
              },
              onFinal(payload) {
                removeThinkingMessage(thinkingMessage);
                appendMessage(messages, "assistant", payload.answer, payload.metadata);
                if (payload.thread_title) {
                  document.title = `${payload.thread_title} | BOE Data Copilot`;
                }
              },
              onError(payload) {
                removeThinkingMessage(thinkingMessage);
                appendMessage(messages, "assistant", payload.detail || "处理出错");
              },
            });
          }
          break;
        }
      }

      removeThinkingMessage(thinkingMessage);
    } catch (error) {
      removeThinkingMessage(thinkingMessage);
      appendMessage(messages, "assistant", `处理出错：${error.message}`);
    } finally {
      button.disabled = false;
      button.textContent = "发送";
      input.focus();
    }
  });
}

document.addEventListener("DOMContentLoaded", initChat);
