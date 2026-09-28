let currentSessionId = null;

const chatBox = document.getElementById("chatBox");
const promptInput = document.getElementById("promptInput");
const codeInput = document.getElementById("codeInput");
const modelInput = document.getElementById("model");
const languageInput = document.getElementById("language");
const fileInput = document.getElementById("fileInput");
const folderInput = document.getElementById("folderInput");
const imageInput = document.getElementById("imageInput");
const sendBtn = document.getElementById("sendBtn");
const searchInput = document.getElementById("searchInput");
const searchResults = document.getElementById("searchResults");
const csrfToken = document.getElementById("csrfToken").value;

function updateActiveModel() {
    const activeModel = document.getElementById("activeModel");
    if (activeModel && modelInput) activeModel.innerText = modelInput.value;
}

function escapeHtml(value) {
    return value.replace(/[&<>'"]/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "'": "&#39;",
        '"': "&quot;",
    })[character]);
}

function highlightCode(code, language) {
    const placeholders = [];
    const stash = html => {
        placeholders.push(html);
        return `@@TOKEN_${placeholders.length - 1}@@`;
    };

    let highlighted = escapeHtml(code);
    highlighted = highlighted.replace(/(\/\/[^\n]*|#[^\n]*|\/\*[\s\S]*?\*\/)/g,
        match => stash(`<span class="token-comment">${match}</span>`));
    highlighted = highlighted.replace(/(&quot;[\s\S]*?&quot;|&#39;[\s\S]*?&#39;)/g,
        match => stash(`<span class="token-string">${match}</span>`));

    const keywords = language === "python"
        ? "and|as|class|def|elif|else|for|from|if|import|in|is|None|not|or|return|True|False|while|with|yield"
        : "async|await|break|case|catch|class|const|else|export|false|for|from|function|if|import|interface|let|new|null|return|switch|this|throw|true|try|typeof|var|while|public|private|static|void|int|string|SELECT|FROM|WHERE|INSERT|UPDATE|DELETE";
    highlighted = highlighted.replace(new RegExp(`\\b(${keywords})\\b`, "g"),
        '<span class="token-keyword">$1</span>');

    return highlighted.replace(/@@TOKEN_(\d+)@@/g, (_, index) => placeholders[index]);
}

function renderMessageContent(element, content) {
    const fence = /```([\w+#-]*)\s*\n?([\s\S]*?)```/g;
    let cursor = 0;
    let match;
    element.innerHTML = "";
    element.dataset.rawContent = content;

    while ((match = fence.exec(content)) !== null) {
        if (match.index > cursor) {
            element.appendChild(document.createTextNode(content.slice(cursor, match.index)));
        }

        const pre = document.createElement("pre");
        const code = document.createElement("code");
        code.className = `language-${match[1] || "text"}`;
        code.innerHTML = highlightCode(match[2].replace(/\n$/, ""), match[1]);
        pre.appendChild(code);
        const copyCodeButton = document.createElement("button");
        copyCodeButton.type = "button";
        copyCodeButton.className = "code-copy-button";
        copyCodeButton.innerText = "Copy code";
        copyCodeButton.onclick = () => copyText(match[2].replace(/\n$/, ""), copyCodeButton);
        const codeActions = document.createElement("div");
        codeActions.className = "code-actions";
        codeActions.appendChild(copyCodeButton);
        pre.appendChild(codeActions);
        element.appendChild(pre);
        cursor = fence.lastIndex;
    }

    if (cursor === 0) {
        element.innerText = content;
    } else if (cursor < content.length) {
        element.appendChild(document.createTextNode(content.slice(cursor)));
    }
}

async function copyText(text, button) {
    try {
        await navigator.clipboard.writeText(text);
        const original = button.innerText;
        button.innerText = "Copied";
        setTimeout(() => { button.innerText = original; }, 1200);
    } catch (error) {
        alert("Unable to copy text: " + error);
    }
}

function downloadText(filename, text) {
    const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
}

function addAssistantActions(element) {
    const actions = document.createElement("div");
    actions.className = "message-actions";

    const copyButton = document.createElement("button");
    copyButton.type = "button";
    copyButton.innerText = "Copy answer";
    copyButton.onclick = () => copyText(element.dataset.rawContent || element.innerText, copyButton);

    const downloadButton = document.createElement("button");
    downloadButton.type = "button";
    downloadButton.innerText = "Download .md";
    downloadButton.onclick = () => downloadText("offline-codegpt-answer.md", element.dataset.rawContent || element.innerText);

    actions.append(copyButton, downloadButton);
    element.parentElement.appendChild(actions);
}
function clearWelcome() {
    const welcome = document.querySelector(".welcome");
    if (welcome) welcome.remove();
}

function setPrompt(text) {
    promptInput.value = text;
    promptInput.focus();
}

function newChat() {
    currentSessionId = null;
    chatBox.innerHTML = `
        <div class="welcome">
            <h1>How can I help with your code?</h1>
            <p>This works locally using Django + Ollama. No internet required after setup.</p>
            <div class="sample-grid">
                <button onclick="setPrompt('Explain this code step by step')">Explain code</button>
                <button onclick="setPrompt('Find bugs and give corrected code')">Find bugs</button>
                <button onclick="setPrompt('Optimize this code for performance')">Optimize</button>
                <button onclick="setPrompt('Convert this code into clean production code')">Refactor</button>
            </div>
        </div>`;
    promptInput.value = "";
    codeInput.value = "";
    if (fileInput) fileInput.value = "";
    if (folderInput) folderInput.value = "";
    if (imageInput) imageInput.value = "";
}

function addMessage(role, content) {
    clearWelcome();

    const wrapper = document.createElement("div");
    wrapper.className = "message " + (role === "user" ? "user-message" : "assistant-message");

    const inner = document.createElement("div");
    inner.className = "message-inner";

    const avatar = document.createElement("div");
    avatar.className = "avatar " + (role === "user" ? "user-avatar" : "ai-avatar");
    avatar.innerText = role === "user" ? "U" : "AI";

    const body = document.createElement("div");
    body.className = "message-content";
    if (role === "assistant") {
        renderMessageContent(body, content);
        addAssistantActions(body);
    } else {
        body.innerText = content;
    }

    inner.append(avatar, body);
    wrapper.appendChild(inner);
    chatBox.appendChild(wrapper);
    chatBox.scrollTop = chatBox.scrollHeight;
    return body;
}

async function readStream(response, output) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let streamedAnswer = "";

    const consumeLine = (line) => {
        if (!line.trim()) return;

        const event = JSON.parse(line);
        if (event.type === "token") {
            streamedAnswer += event.token;
            output.innerText = streamedAnswer;
            chatBox.scrollTop = chatBox.scrollHeight;
        } else if (event.type === "complete") {
            currentSessionId = event.session_id;
            renderMessageContent(output, event.answer);
        } else if (event.type === "error") {
            output.innerText = "Error:\n" + event.error;
        }
    };

    while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const lines = buffer.split("\n");
        buffer = lines.pop();
        lines.forEach(consumeLine);
        if (done) break;
    }

    if (buffer.trim()) consumeLine(buffer);
}

async function sendMessage() {
    const prompt = promptInput.value.trim();
    const code = codeInput.value.trim();
    const files = [
        ...(fileInput ? fileInput.files : []),
        ...(folderInput ? folderInput.files : []),
    ];
    const images = imageInput ? [...imageInput.files] : [];

    if (!prompt && !code && files.length === 0 && images.length === 0) {
        alert("Please enter a prompt, paste code, or choose an upload.");
        return;
    }

    let userText = prompt ? "Prompt:\n" + prompt : "";
    if (files.length > 0) {
        userText += "\n\nUploaded Files:\n";
        userText += files.map(file => file.webkitRelativePath || file.name).join("\n");
    }
    if (images.length > 0) {
        userText += "\n\nUploaded Images:\n";
        userText += images.map(image => image.name).join("\n");
    }
    if (code) userText += "\n\nCode:\n" + code.substring(0, 2000);

    addMessage("user", userText.trim());
    promptInput.value = "";
    sendBtn.disabled = true;
    sendBtn.innerText = "Generating...";
    const output = addMessage("assistant", "Thinking locally...");

    const formData = new FormData();
    formData.append("prompt", prompt);
    formData.append("code", code);
    formData.append("model", modelInput.value);
    formData.append("language", languageInput.value);
    if (currentSessionId) formData.append("session_id", currentSessionId);
    files.forEach(file => {
        const relativePath = file.webkitRelativePath || file.name;
        formData.append("files", file, relativePath);
        formData.append("file_paths", relativePath);
    });
    images.forEach(image => formData.append("images", image, image.name));

    try {
        const response = await fetch("/api/ask-code/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken },
            body: formData,
        });

        if (!response.ok) {
            const data = await response.json();
            output.innerText = data.login_required
                ? "Sign in to unlock uploads and image analysis."
                : "Error:\n" + (data.error || "Request failed.");
        } else {
            await readStream(response, output);
        }
    } catch (error) {
        output.innerText = "Error: Backend or Ollama not available.\n\n" + error;
    } finally {
        sendBtn.disabled = false;
        sendBtn.innerText = "Send";
    }
}
async function runCode() {
    const code = codeInput.value.trim();
    if (!code) {
        alert("Paste code before checking it.");
        return;
    }

    const output = document.getElementById("executionOutput");
    output.innerText = "Checking locally...";
    try {
        const response = await fetch("/api/execute/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams({ code, language: languageInput.value }),
        });
        const data = await response.json();
        output.innerText = data.success
            ? (data.stdout || "Completed without output.")
            : (data.stderr || data.error || "Check failed.");
    } catch (error) {
        output.innerText = "Check error: " + error;
    }
}

async function analyzeQuality() {
    const code = codeInput.value.trim();
    if (!code) {
        alert("Paste code before analyzing it.");
        return;
    }

    const output = document.getElementById("qualityOutput");
    output.innerText = "Analyzing locally...";
    try {
        const response = await fetch("/api/analyze/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams({
                code,
                language: languageInput.value,
                mode: document.getElementById("qualityMode").value,
            }),
        });
        const data = await response.json();
        if (!data.success) {
            output.innerText = data.error || "Analysis failed.";
            return;
        }

        const lines = [data.summary];
        data.findings.forEach(finding => {
            lines.push(`[${finding.severity}] ${finding.category}${finding.line ? ` (line ${finding.line})` : ""}: ${finding.message}`);
        });
        if (data.test_template) lines.push("\\nGenerated test template:\\n" + data.test_template);
        output.innerText = lines.join("\\n");
    } catch (error) {
        output.innerText = "Analysis error: " + error;
    }
}

async function loadSession(sessionId) {
    try {
        const response = await fetch(`/api/session/${sessionId}/`);
        const data = await response.json();
        if (!data.success) {
            alert("Unable to load chat.");
            return;
        }

        currentSessionId = data.session_id;
        chatBox.innerHTML = "";
        data.messages.forEach(message => addMessage(message.role, message.content));
    } catch (error) {
        alert("Error loading chat: " + error);
    }
}

function exportChat(format) {
    if (!currentSessionId) {
        alert("Send or open a chat before exporting it.");
        return;
    }
    window.location.href = `/api/session/${currentSessionId}/export/?format=${format}`;
}

async function searchProject() {
    const query = searchInput.value.trim();
    if (!query) {
        searchResults.innerHTML = "";
        return;
    }

    searchResults.innerText = "Searching...";
    try {
        const response = await fetch(`/api/search/?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        searchResults.innerHTML = "";

        if (!data.results.length) {
            searchResults.innerText = "No matching project code.";
            return;
        }

        data.results.forEach(result => {
            const item = document.createElement("button");
            item.type = "button";
            item.className = "search-result";
            item.innerText = `${result.filename} · chunk ${result.chunk_index + 1}`;
            item.title = result.content;
            item.onclick = () => {
                codeInput.value = result.content;
                codeInput.focus();
            };
            searchResults.appendChild(item);
        });
    } catch (error) {
        searchResults.innerText = "Search failed: " + error;
    }
}

if (searchInput) searchInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter") searchProject();
});

promptInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
});

modelInput.addEventListener("change", updateActiveModel);
updateActiveModel();
