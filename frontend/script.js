/**
 * SWS AI RAG Chatbot — Frontend Logic
 * Handles chat interactions, streaming responses, and source display.
 */

// ─── Configuration ──────────────────────────────────────────────
const API_BASE_URL = "http://localhost:8000";
const ENDPOINTS = {
    chat: `${API_BASE_URL}/api/chat`,
    ingest: `${API_BASE_URL}/api/ingest`,
    health: `${API_BASE_URL}/api/health`,
};

// ─── DOM Elements ───────────────────────────────────────────────
const welcomeScreen = document.getElementById("welcome-screen");
const messagesContainer = document.getElementById("messages-container");
const questionInput = document.getElementById("question-input");
const sendBtn = document.getElementById("btn-send");
const clearBtn = document.getElementById("btn-clear");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const chatArea = document.getElementById("chat-area");

// ─── State ──────────────────────────────────────────────────────
let isProcessing = false;
let conversationHistory = [];

// ─── Initialization ─────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    setupEventListeners();
    checkHealth();
    autoResizeTextarea();
});

function setupEventListeners() {
    // Send button
    sendBtn.addEventListener("click", handleSend);

    // Enter to send (Shift+Enter for new line)
    questionInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });

    // Enable/disable send button based on input
    questionInput.addEventListener("input", () => {
        const hasText = questionInput.value.trim().length > 0;
        sendBtn.disabled = !hasText || isProcessing;
        autoResizeTextarea();
    });

    // Clear conversation
    clearBtn.addEventListener("click", clearConversation);

    // Suggestion chips
    document.querySelectorAll(".suggestion-chip").forEach((chip) => {
        chip.addEventListener("click", () => {
            const query = chip.getAttribute("data-query");
            questionInput.value = query;
            sendBtn.disabled = false;
            handleSend();
        });
    });
}

function autoResizeTextarea() {
    questionInput.style.height = "auto";
    questionInput.style.height = Math.min(questionInput.scrollHeight, 120) + "px";
}

// ─── Health Check ───────────────────────────────────────────────
async function checkHealth() {
    try {
        const response = await fetch(ENDPOINTS.health);
        if (response.ok) {
            const data = await response.json();
            if (data.ollama_connected) {
                setStatus("online", "Online");
            } else {
                setStatus("offline", `Model not found`);
            }
        } else {
            setStatus("offline", "API Error");
        }
    } catch (error) {
        setStatus("offline", "Disconnected");
    }
}

function setStatus(state, text) {
    statusDot.className = `status-dot ${state}`;
    statusText.textContent = text;
}

// ─── Send Message ───────────────────────────────────────────────
async function handleSend() {
    const question = questionInput.value.trim();
    if (!question || isProcessing) return;

    isProcessing = true;
    sendBtn.disabled = true;

    // Hide welcome screen
    welcomeScreen.classList.add("hidden");

    // Add user message
    addMessage("user", question);
    conversationHistory.push({ role: "user", content: question });

    // Clear input
    questionInput.value = "";
    autoResizeTextarea();

    // Show typing indicator
    const typingEl = showTypingIndicator();

    try {
        // Stream the response
        await streamResponse(question, typingEl);
    } catch (error) {
        console.error("Chat error:", error);
        removeTypingIndicator(typingEl);
        addErrorMessage(error.message || "Failed to get response. Please try again.");
    } finally {
        isProcessing = false;
        sendBtn.disabled = questionInput.value.trim().length === 0;
    }
}

// ─── Streaming Response ─────────────────────────────────────────
async function streamResponse(question, typingEl) {
    const response = await fetch(ENDPOINTS.chat, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, stream: true }),
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server error: ${response.status}`);
    }

    // Remove typing indicator and create assistant message
    removeTypingIndicator(typingEl);

    const messageEl = createAssistantMessage();
    const bubbleEl = messageEl.querySelector(".message-bubble");
    const sourcesContainer = messageEl.querySelector(".sources-container");

    let fullContent = "";
    let sources = [];

    // Read the streaming response
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete JSON lines
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer

        for (const line of lines) {
            if (!line.trim()) continue;

            try {
                const event = JSON.parse(line);

                if (event.type === "sources") {
                    sources = event.sources || [];
                } else if (event.type === "token") {
                    fullContent += event.content;
                    bubbleEl.innerHTML = formatMarkdown(fullContent);
                    bubbleEl.classList.add("streaming-cursor");
                    scrollToBottom();
                } else if (event.type === "complete") {
                    if (event.sources) sources = event.sources;
                    if (event.content && !fullContent) {
                        fullContent = event.content;
                        bubbleEl.innerHTML = formatMarkdown(fullContent);
                    }
                }
            } catch (e) {
                // Skip malformed JSON
            }
        }
    }

    // Remove streaming cursor
    bubbleEl.classList.remove("streaming-cursor");

    // Show sources
    if (sources.length > 0) {
        renderSources(sourcesContainer, sources);
    }

    // Save to history
    conversationHistory.push({
        role: "assistant",
        content: fullContent,
        sources,
    });

    scrollToBottom();
}

// ─── Message Rendering ──────────────────────────────────────────
function addMessage(role, content) {
    const messageEl = document.createElement("div");
    messageEl.className = `message ${role}`;

    const avatarText = role === "user" ? "U" : "AI";

    messageEl.innerHTML = `
        <div class="message-avatar">${avatarText}</div>
        <div class="message-body">
            <div class="message-bubble">${formatMarkdown(content)}</div>
        </div>
    `;

    messagesContainer.appendChild(messageEl);
    scrollToBottom();
}

function createAssistantMessage() {
    const messageEl = document.createElement("div");
    messageEl.className = "message assistant";

    messageEl.innerHTML = `
        <div class="message-avatar">AI</div>
        <div class="message-body">
            <div class="message-bubble"></div>
            <div class="sources-container hidden"></div>
        </div>
    `;

    messagesContainer.appendChild(messageEl);
    scrollToBottom();
    return messageEl;
}

function addErrorMessage(errorText) {
    const messageEl = document.createElement("div");
    messageEl.className = "message assistant";

    messageEl.innerHTML = `
        <div class="message-avatar">AI</div>
        <div class="message-body">
            <div class="message-bubble error-bubble">
                <p>⚠️ ${escapeHtml(errorText)}</p>
                <button class="retry-btn" onclick="retryLastMessage()">
                    ↻ Retry
                </button>
            </div>
        </div>
    `;

    messagesContainer.appendChild(messageEl);
    scrollToBottom();
}

function renderSources(container, sources) {
    container.classList.remove("hidden");
    container.innerHTML = `
        <span class="sources-label">Sources</span>
        ${sources.map((s) => `<span class="source-pill">${escapeHtml(s)}</span>`).join("")}
    `;
}

// ─── Typing Indicator ───────────────────────────────────────────
function showTypingIndicator() {
    const messageEl = document.createElement("div");
    messageEl.className = "message assistant typing-message";

    messageEl.innerHTML = `
        <div class="message-avatar">AI</div>
        <div class="message-body">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;

    messagesContainer.appendChild(messageEl);
    scrollToBottom();
    return messageEl;
}

function removeTypingIndicator(el) {
    if (el && el.parentNode) {
        el.parentNode.removeChild(el);
    }
}

// ─── Utilities ──────────────────────────────────────────────────
function scrollToBottom() {
    requestAnimationFrame(() => {
        chatArea.scrollTop = chatArea.scrollHeight;
    });
}

function clearConversation() {
    messagesContainer.innerHTML = "";
    conversationHistory = [];
    welcomeScreen.classList.remove("hidden");
    questionInput.focus();
}

function retryLastMessage() {
    // Find the last user message
    const lastUserMsg = [...conversationHistory]
        .reverse()
        .find((m) => m.role === "user");
    if (lastUserMsg) {
        // Remove the error message
        const lastChild = messagesContainer.lastElementChild;
        if (lastChild) lastChild.remove();

        // Remove from history
        conversationHistory.pop();

        // Resend
        questionInput.value = lastUserMsg.content;
        handleSend();
    }
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function formatMarkdown(text) {
    if (!text) return "";

    let html = escapeHtml(text);

    // Bold: **text**
    html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

    // Italic: *text*
    html = html.replace(/(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");

    // Inline code: `code`
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

    // Bullet points
    html = html.replace(/^[\s]*[-•]\s+(.*)/gm, "<li>$1</li>");
    html = html.replace(/(<li>.*<\/li>\n?)+/g, "<ul>$&</ul>");

    // Numbered lists
    html = html.replace(/^[\s]*\d+\.\s+(.*)/gm, "<li>$1</li>");

    // Line breaks
    html = html.replace(/\n\n/g, "</p><p>");
    html = html.replace(/\n/g, "<br>");

    // Wrap in paragraph if not already structured
    if (!html.startsWith("<")) {
        html = `<p>${html}</p>`;
    }

    return html;
}

// ─── Periodic Health Check ──────────────────────────────────────
setInterval(checkHealth, 30000);
