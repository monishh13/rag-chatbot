/**
 * SWS AI RAG Chatbot — Frontend Logic
 * Handles chat interactions, streaming responses, source display,
 * chat history session persistence, and document uploads.
 */

// ─── Configuration ──────────────────────────────────────────────
const API_BASE_URL = "http://localhost:8000";
const ENDPOINTS = {
    chat: `${API_BASE_URL}/api/chat`,
    ingest: `${API_BASE_URL}/api/ingest`,
    health: `${API_BASE_URL}/api/health`,
    upload: `${API_BASE_URL}/api/upload`,
};

// ─── DOM Elements ───────────────────────────────────────────────
const workspaceContainer = document.querySelector(".workspace-container");
const btnToggleSidebar = document.getElementById("btn-toggle-sidebar");
const btnNewChat = document.getElementById("btn-new-chat");
const sidebarHistory = document.getElementById("sidebar-history");

const welcomeScreen = document.getElementById("welcome-screen");
const messagesContainer = document.getElementById("messages-container");
const questionInput = document.getElementById("question-input");
const sendBtn = document.getElementById("btn-send");
const clearBtn = document.getElementById("btn-clear");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const chatArea = document.getElementById("chat-area");

// Tab togglers
const tabButtons = document.querySelectorAll(".tab-button");
const panels = document.querySelectorAll(".panel");

// File Upload Elements
const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const uploadListContainer = document.getElementById("upload-list-container");
const uploadList = document.getElementById("upload-list");

// ─── State ──────────────────────────────────────────────────────
let isProcessing = false;
let chats = []; // Array of { id, title, history: [] }
let activeChatId = null;

// ─── Initialization ─────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    loadChatsFromStorage();
    setupEventListeners();
    checkHealth();
    autoResizeTextarea();
});

// ─── LocalStorage Session Management ────────────────────────────
function loadChatsFromStorage() {
    try {
        const stored = localStorage.getItem("sws_chats");
        if (stored) {
            chats = JSON.parse(stored);
        }
    } catch (e) {
        console.error("Failed to load chats from localStorage", e);
        chats = [];
    }

    if (chats.length === 0) {
        createNewChat();
    } else {
        // Load the most recent active chat, or the first one
        activeChatId = chats[0].id;
        renderSidebar();
        loadActiveChat();
    }
}

function saveChatsToStorage() {
    try {
        localStorage.setItem("sws_chats", JSON.stringify(chats));
    } catch (e) {
        console.error("Failed to save chats to localStorage", e);
    }
}

function createNewChat() {
    const newChat = {
        id: "chat_" + Date.now(),
        title: "New Conversation",
        history: []
    };
    chats.unshift(newChat);
    activeChatId = newChat.id;
    saveChatsToStorage();
    renderSidebar();
    loadActiveChat();
}

function deleteChat(chatId, event) {
    if (event) event.stopPropagation();
    
    chats = chats.filter(c => c.id !== chatId);
    saveChatsToStorage();
    
    if (chats.length === 0) {
        createNewChat();
    } else if (activeChatId === chatId) {
        activeChatId = chats[0].id;
        loadActiveChat();
    }
    renderSidebar();
}

function selectChat(chatId) {
    if (activeChatId === chatId) return;
    activeChatId = chatId;
    renderSidebar();
    loadActiveChat();
}

function loadActiveChat() {
    // Clear display
    messagesContainer.innerHTML = "";
    isProcessing = false;
    sendBtn.disabled = true;
    questionInput.value = "";
    
    const activeChat = chats.find(c => c.id === activeChatId);
    if (!activeChat || activeChat.history.length === 0) {
        welcomeScreen.classList.remove("hidden");
    } else {
        welcomeScreen.classList.add("hidden");
        // Populate existing messages
        activeChat.history.forEach(msg => {
            if (msg.role === "user") {
                addMessage("user", msg.content);
            } else {
                const messageEl = createAssistantMessage();
                const bubbleEl = messageEl.querySelector(".message-bubble");
                bubbleEl.innerHTML = formatMarkdown(msg.content);
                
                if (msg.sources && msg.sources.length > 0) {
                    const sourcesContainer = messageEl.querySelector(".sources-container");
                    renderSources(sourcesContainer, msg.sources);
                }
            }
        });
        scrollToBottom();
    }
}

function renderSidebar() {
    sidebarHistory.innerHTML = "";
    
    if (chats.length === 0) {
        sidebarHistory.innerHTML = '<div class="history-empty">No past conversations</div>';
        return;
    }
    
    chats.forEach(chat => {
        const item = document.createElement("div");
        item.className = `history-item ${chat.id === activeChatId ? "active" : ""}`;
        item.onclick = () => selectChat(chat.id);
        
        const titleSpan = document.createElement("span");
        titleSpan.className = "history-title";
        titleSpan.textContent = chat.title;
        
        const deleteBtn = document.createElement("button");
        deleteBtn.className = "btn-delete-chat";
        deleteBtn.title = "Delete Chat";
        deleteBtn.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
        `;
        deleteBtn.onclick = (e) => deleteChat(chat.id, e);
        
        item.appendChild(titleSpan);
        item.appendChild(deleteBtn);
        sidebarHistory.appendChild(item);
    });
}

// ─── Setup Event Listeners ──────────────────────────────────────
function setupEventListeners() {
    // Sidebar toggle
    btnToggleSidebar.addEventListener("click", () => {
        workspaceContainer.classList.toggle("sidebar-collapsed");
        workspaceContainer.classList.toggle("sidebar-open");
    });
    
    // New chat button
    btnNewChat.addEventListener("click", createNewChat);

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

    // Clear conversation (re-creates empty chat session)
    clearBtn.addEventListener("click", () => {
        const activeChat = chats.find(c => c.id === activeChatId);
        if (activeChat) {
            activeChat.history = [];
            activeChat.title = "New Conversation";
            saveChatsToStorage();
        }
        renderSidebar();
        loadActiveChat();
    });

    // Suggestion chips
    document.querySelectorAll(".suggestion-chip").forEach((chip) => {
        chip.addEventListener("click", () => {
            const query = chip.getAttribute("data-query");
            questionInput.value = query;
            sendBtn.disabled = false;
            handleSend();
        });
    });

    // Navigation Tab Switching
    tabButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            tabButtons.forEach(b => b.classList.remove("active"));
            panels.forEach(p => p.classList.remove("active"));
            
            btn.classList.add("active");
            const targetPanel = document.getElementById(`${btn.getAttribute("data-tab")}-panel`);
            if (targetPanel) {
                targetPanel.classList.add("active");
            }
        });
    });

    // File drag & drop events
    dropZone.addEventListener("click", () => fileInput.click());
    
    fileInput.addEventListener("change", (e) => {
        handleFiles(e.target.files);
    });

    ["dragenter", "dragover"].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.add("dragover");
        }, false);
    });

    ["dragleave", "drop"].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.remove("dragover");
        }, false);
    });

    dropZone.addEventListener("drop", (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
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

    const activeChat = chats.find(c => c.id === activeChatId);
    if (!activeChat) return;

    isProcessing = true;
    sendBtn.disabled = true;

    // Hide welcome screen
    welcomeScreen.classList.add("hidden");

    // Add user message
    addMessage("user", question);
    activeChat.history.push({ role: "user", content: question });

    // Update conversation title if it was default
    if (activeChat.title === "New Conversation") {
        activeChat.title = question.length > 25 ? question.substring(0, 25) + "..." : question;
        renderSidebar();
    }

    saveChatsToStorage();

    // Clear input
    questionInput.value = "";
    autoResizeTextarea();

    // Show typing indicator
    const typingEl = showTypingIndicator();

    try {
        // Stream the response
        await streamResponse(question, typingEl, activeChat);
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
async function streamResponse(question, typingEl, activeChat) {
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
    activeChat.history.push({
        role: "assistant",
        content: fullContent,
        sources,
    });
    saveChatsToStorage();

    scrollToBottom();
}

// ─── File Upload Logic ──────────────────────────────────────────
function handleFiles(files) {
    if (!files || files.length === 0) return;
    
    uploadListContainer.classList.remove("hidden");
    
    Array.from(files).forEach(file => {
        if (!file.name.toLowerCase().endsWith(".pdf")) {
            alert("Only PDF documents are supported.");
            return;
        }
        
        uploadFile(file);
    });
}

function uploadFile(file) {
    const itemId = "upload_" + Date.now() + "_" + Math.random().toString(36).substr(2, 5);
    
    // Create UI item
    const item = document.createElement("div");
    item.className = "upload-item";
    item.id = itemId;
    item.innerHTML = `
        <div class="upload-item-header">
            <span class="upload-item-name">${escapeHtml(file.name)}</span>
            <span class="upload-item-status">Uploading...</span>
        </div>
        <div class="upload-item-progress">
            <div class="upload-item-progress-fill"></div>
        </div>
        <div class="upload-item-stats">Preparing file...</div>
    `;
    uploadList.appendChild(item);
    
    const progressFill = item.querySelector(".upload-item-progress-fill");
    const statusTextEl = item.querySelector(".upload-item-status");
    const statsTextEl = item.querySelector(".upload-item-stats");
    
    // Setup dynamic mock interval for embedding progress since the actual
    // HTTP upload takes milliseconds, but embedding processing takes several seconds.
    let progress = 0;
    const interval = setInterval(() => {
        if (progress < 90) {
            progress += Math.floor(Math.random() * 8) + 2;
            progress = Math.min(progress, 90);
            progressFill.style.width = `${progress}%`;
            statsTextEl.textContent = `Extracting and generating embeddings (${progress}%)...`;
        }
    }, 400);

    const formData = new FormData();
    formData.append("file", file);

    fetch(ENDPOINTS.upload, {
        method: "POST",
        body: formData
    })
    .then(async response => {
        clearInterval(interval);
        const data = await response.json();
        
        if (response.ok) {
            progressFill.style.width = "100%";
            progressFill.style.background = "var(--green-500)";
            statusTextEl.className = "upload-item-status success";
            statusTextEl.textContent = "Complete";
            
            const stats = data.stats || {};
            statsTextEl.textContent = `Processed ${stats.pages || 0} pages, created ${stats.chunks || 0} chunks (${stats.new_chunks || 0} new database entries) in ${stats.elapsed_seconds || 0}s.`;
            
            // Check health to update db index count
            checkHealth();
        } else {
            throw new Error(data.detail || "Ingestion server error");
        }
    })
    .catch(error => {
        clearInterval(interval);
        progressFill.style.width = "100%";
        progressFill.style.background = "var(--red-500)";
        statusTextEl.className = "upload-item-status error";
        statusTextEl.textContent = "Failed";
        statsTextEl.textContent = error.message || "Failed to process PDF file.";
    });
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

function retryLastMessage() {
    const activeChat = chats.find(c => c.id === activeChatId);
    if (!activeChat) return;

    // Find the last user message
    const lastUserMsg = [...activeChat.history]
        .reverse()
        .find((m) => m.role === "user");
        
    if (lastUserMsg) {
        // Remove the error message UI element
        const lastChild = messagesContainer.lastElementChild;
        if (lastChild) lastChild.remove();

        // Remove the failed response if any, or matching history entries
        activeChat.history.pop();

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
