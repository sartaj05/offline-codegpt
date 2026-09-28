let currentSessionId = null;
let editingMessage = null;
let editingMessageId = "";

const chatBox = document.getElementById("chatBox");
const promptInput = document.getElementById("promptInput");
const codeInput = document.getElementById("codeInput");
const modelInput = document.getElementById("model");
const ollamaSettingsPanel = document.getElementById("ollamaSettingsPanel");
const ollamaServerUrl = document.getElementById("ollamaServerUrl");
const ollamaDefaultModel = document.getElementById("ollamaDefaultModel");
const ollamaTemperature = document.getElementById("ollamaTemperature");
const ollamaTopP = document.getElementById("ollamaTopP");
const ollamaContextLength = document.getElementById("ollamaContextLength");
const ollamaModelName = document.getElementById("ollamaModelName");
const ollamaSettingsStatus = document.getElementById("ollamaSettingsStatus");
const languageInput = document.getElementById("language");
const fileInput = document.getElementById("fileInput");
const folderInput = document.getElementById("folderInput");
const imageInput = document.getElementById("imageInput");
const sendBtn = document.getElementById("sendBtn");
const sendStatus = document.createElement("div");
sendStatus.className = "send-status";
sendStatus.setAttribute("aria-live", "polite");
if (sendBtn) {
    const promptBar = sendBtn.closest(".prompt-bar");
    if (promptBar) promptBar.insertAdjacentElement("afterend", sendStatus);
}
const searchInput = document.getElementById("searchInput");
const searchResults = document.getElementById("searchResults");
const projectStats = document.getElementById("projectStats");
const projectFiles = document.getElementById("projectFiles");
const gitBranch = document.getElementById("gitBranch");
const gitFiles = document.getElementById("gitFiles");
const gitDiff = document.getElementById("gitDiff");
const gitCommitMessage = document.getElementById("gitCommitMessage");
const chatSearch = document.getElementById("chatSearch");
const chatHistory = document.getElementById("chatHistory");
const editorFileName = document.getElementById("editorFileName");
const editorLanguage = document.getElementById("editorLanguage");
const editorTabs = document.getElementById("editorTabs");
const editorPreview = document.getElementById("editorPreview");
const saveFileBtn = document.getElementById("saveFileBtn");
const csrfToken = document.getElementById("csrfToken").value;
const patchPanel = document.getElementById("patchPanel");
const patchStatus = document.getElementById("patchStatus");
const patchDiff = document.getElementById("patchDiff");
let editorTabsState = [];
let activeEditorDocumentId = null;
let pendingPatch = null;
let codeBeforePatch = "";

function updateActiveModel() {
    const activeModel = document.getElementById("activeModel");
    if (activeModel && modelInput) activeModel.innerText = modelInput.value;
}

function toggleOllamaSettings() {
    if (ollamaSettingsPanel) ollamaSettingsPanel.hidden = !ollamaSettingsPanel.hidden;
}

function renderOllamaModels(models, selected) {
    [modelInput, ollamaDefaultModel].forEach(select => {
        if (!select) return;
        select.innerHTML = "";
        models.forEach(name => {
            const option = document.createElement("option");
            option.value = name;
            option.innerText = name;
            option.selected = name === selected;
            select.appendChild(option);
        });
    });
    updateActiveModel();
}

async function loadOllamaSettings() {
    if (!ollamaSettingsPanel) return;
    try {
        const response = await fetch("/api/ollama/settings/");
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to load settings.");
        const settings = data.settings;
        ollamaServerUrl.value = settings.server_url;
        ollamaTemperature.value = settings.temperature;
        ollamaTopP.value = settings.top_p;
        ollamaContextLength.value = settings.max_context_chars;
        renderOllamaModels(data.models, settings.default_model);
    } catch (error) {
        ollamaSettingsStatus.innerText = String(error);
    }
}

async function saveOllamaSettings() {
    try {
        const response = await fetch("/api/ollama/settings/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams({
                server_url: ollamaServerUrl.value.trim(),
                default_model: ollamaDefaultModel.value,
                temperature: ollamaTemperature.value,
                top_p: ollamaTopP.value,
                max_context_chars: ollamaContextLength.value,
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to save settings.");
        renderOllamaModels(data.models, data.settings.default_model);
        ollamaSettingsStatus.innerText = "Saved. New chats use these settings.";
    } catch (error) {
        ollamaSettingsStatus.innerText = String(error);
    }
}

async function manageOllamaModel(action) {
    const name = ollamaModelName.value.trim();
    if (!name) {
        ollamaSettingsStatus.innerText = "Enter a model name first.";
        return;
    }
    if (action === "delete" && !confirm("Delete local model " + name + "?")) return;
    ollamaSettingsStatus.innerText = action === "pull" ? "Pulling model..." : "Deleting model...";
    try {
        const response = await fetch("/api/ollama/models/action/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams({ action, name }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Model action failed.");
        renderOllamaModels(data.models, modelInput.value);
        ollamaSettingsStatus.innerText = action === "pull" ? "Model pulled." : "Model deleted.";
    } catch (error) {
        ollamaSettingsStatus.innerText = String(error);
    }
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
        const reviewPatchButton = document.createElement("button");
        reviewPatchButton.type = "button";
        reviewPatchButton.className = "code-copy-button";
        reviewPatchButton.innerText = "Review patch";
        reviewPatchButton.onclick = () => openPatchReview(match[2].trimEnd(), match[1] || languageInput.value);
        codeActions.appendChild(reviewPatchButton);
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
    downloadButton.onclick = () => downloadText("syntax-local-ai-answer.md", element.dataset.rawContent || element.innerText);

    actions.append(copyButton, downloadButton);
    element.parentElement.appendChild(actions);
}

function addSourceCitations(element, sources) {
    if (!sources || !sources.length) return;
    const citations = document.createElement("div");
    citations.className = "source-citations";
    const label = document.createElement("span");
    label.className = "source-citations-label";
    label.innerText = "Sources";
    citations.appendChild(label);
    sources.forEach(source => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "source-citation";
        button.innerText = source.filename + ":" + source.line_start;
        button.title = "Open retrieved project context";
        button.onclick = () => {
            codeInput.value = source.content;
            if (languageInput && [...languageInput.options].some(option => option.value === source.language)) {
                languageInput.value = source.language;
            }
            codeInput.focus();
            codeInput.scrollIntoView({ behavior: "smooth", block: "center" });
        };
        citations.appendChild(button);
    });
    element.appendChild(citations);
}

function restoreFileSelection(input, files) {
    if (!input) return;
    input.value = "";
    if (!files || !files.length || typeof DataTransfer === "undefined") return;
    const transfer = new DataTransfer();
    files.forEach(file => transfer.items.add(file));
    input.files = transfer.files;
}

function addUserDetails(column, payload) {
    const details = document.createElement("details");
    details.className = "message-details-panel";

    const summary = document.createElement("summary");
    summary.innerText = "View request details";
    details.appendChild(summary);

    const metadata = document.createElement("div");
    metadata.className = "request-meta";
    const parts = [
        payload.model ? "Model: " + payload.model : "",
        payload.language ? "Language: " + payload.language : "",
        payload.prompt ? "Prompt included" : "",
        payload.code ? payload.code.length.toLocaleString() + " code characters" : "",
        payload.fileNames.length ? payload.fileNames.length + " file(s)" : "",
        payload.imageNames.length ? payload.imageNames.length + " image(s)" : "",
    ].filter(Boolean);
    metadata.innerText = parts.join("  |  ");
    details.appendChild(metadata);

    if (payload.code) {
        const codeLabel = document.createElement("div");
        codeLabel.className = "detail-label";
        codeLabel.innerText = "Full code";
        const codeBlock = document.createElement("pre");
        codeBlock.innerText = payload.code;
        details.append(codeLabel, codeBlock);
    }

    if (payload.fileNames.length || payload.imageNames.length) {
        const filesLabel = document.createElement("div");
        filesLabel.className = "detail-label";
        filesLabel.innerText = "Attachments";
        const filesList = document.createElement("div");
        filesList.className = "attachment-list";
        filesList.innerText = [...payload.fileNames, ...payload.imageNames].join("\n");
        details.append(filesLabel, filesList);
    }

    column.appendChild(details);
}

function addUserActions(column, wrapper, payload) {
    const actions = document.createElement("div");
    actions.className = "message-actions";

    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.innerText = "Edit message";
    editButton.onclick = () => {
        editingMessage = wrapper;
        editingMessageId = wrapper.dataset.messageId || "";
        wrapper.classList.add("editing-message");
        promptInput.value = payload.prompt || "";
        codeInput.value = payload.code || "";
        if (modelInput && payload.model) modelInput.value = payload.model;
        if (languageInput && payload.language) languageInput.value = payload.language;
        restoreFileSelection(fileInput, payload.fileFiles);
        restoreFileSelection(folderInput, payload.folderFiles);
        restoreFileSelection(imageInput, payload.imageFiles);
        updateActiveModel();
        sendStatus.textContent = "Editing message - update it and press Send.";
        promptInput.focus();
        promptInput.scrollIntoView({ behavior: "smooth", block: "center" });
    };

    actions.appendChild(editButton);
    column.appendChild(actions);
}

function clearWelcome() {
    const welcome = document.querySelector(".welcome");
    if (welcome) welcome.remove();
}

function parseStoredUserMessage(content, model) {
    const promptMatch = content.match(/^Prompt:\n([\s\S]*?)(?=\n\n(?:Uploaded Files|Uploaded Images|Code):|$)/);
    const filesMatch = content.match(/\n\nUploaded Files:\n([\s\S]*?)(?=\n\n(?:Uploaded Images|Code):|$)/);
    const imagesMatch = content.match(/\n\nUploaded Images:\n([\s\S]*?)(?=\n\nCode:|$)/);
    const codeMatch = content.match(/\n\nCode:\n([\s\S]*)$/);
    const names = value => value ? value.split("\n").map(item => item.trim()).filter(Boolean) : [];
    return {
        prompt: promptMatch ? promptMatch[1].trim() : "",
        code: codeMatch ? codeMatch[1] : "",
        model: model || "",
        language: "auto",
        fileFiles: [],
        folderFiles: [],
        imageFiles: [],
        fileNames: names(filesMatch && filesMatch[1]),
        imageNames: names(imagesMatch && imagesMatch[1]),
    };
}

function setPrompt(text) {
    promptInput.value = text;
    promptInput.focus();
}

function newChat() {
    currentSessionId = null;
    editingMessage = null;
    editingMessageId = "";
    sendStatus.textContent = "";
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
    editorTabsState = [];
    activeEditorDocumentId = null;
    if (editorFileName) editorFileName.innerText = "Scratch buffer";
    if (editorLanguage) editorLanguage.innerText = "Auto detect";
    if (saveFileBtn) saveFileBtn.disabled = true;
    renderEditorTabs();
    syncEditorPreview();
}

function addMessage(role, content, options = {}) {
    clearWelcome();

    const wrapper = document.createElement("div");
    wrapper.className = "message " + (role === "user" ? "user-message" : "assistant-message");
    if (options.messageId) wrapper.dataset.messageId = options.messageId;

    const inner = document.createElement("div");
    inner.className = "message-inner";

    const avatar = document.createElement("div");
    avatar.className = "avatar " + (role === "user" ? "user-avatar" : "ai-avatar");
    avatar.innerText = role === "user" ? "U" : "AI";

    const column = document.createElement("div");
    column.className = "message-column";
    const body = document.createElement("div");
    body.className = "message-content";
    if (role === "assistant") {
        renderMessageContent(body, content);
    } else {
        body.innerText = content;
    }

    column.appendChild(body);
    if (role === "assistant") addAssistantActions(body);
    if (role === "user" && options.payload) {
        addUserDetails(column, options.payload);
        addUserActions(column, wrapper, options.payload);
    }
    inner.append(avatar, column);
    wrapper.appendChild(inner);
    chatBox.appendChild(wrapper);
    chatBox.scrollTop = chatBox.scrollHeight;
    return body;
}

async function readStream(response, output, userWrapper) {
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
            if (userWrapper && event.user_message_id) {
                userWrapper.dataset.messageId = event.user_message_id;
            }
            renderMessageContent(output, event.answer);
            addSourceCitations(output, event.sources);
            if (chatHistory) loadChatHistory();
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
    if (sendBtn.disabled) return;

    const prompt = promptInput.value.trim();
    const code = codeInput.value.trim();
    const fileFiles = fileInput ? [...fileInput.files] : [];
    const folderFiles = folderInput ? [...folderInput.files] : [];
    const imageFiles = imageInput ? [...imageInput.files] : [];
    const files = [...fileFiles, ...folderFiles];
    const images = imageFiles;

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

    const editId = editingMessageId;
    if (editingMessage) {
        const assistantMessage = editingMessage.nextElementSibling;
        editingMessage.remove();
        if (assistantMessage && assistantMessage.classList.contains("assistant-message")) {
            assistantMessage.remove();
        }
        editingMessage = null;
        editingMessageId = "";
    }

    const payload = {
        prompt,
        code,
        model: modelInput.value,
        language: languageInput.value,
        fileFiles,
        folderFiles,
        imageFiles,
        fileNames: files.map(file => file.webkitRelativePath || file.name),
        imageNames: images.map(image => image.name),
    };
    const userBody = addMessage("user", userText.trim(), { payload });
    const userWrapper = userBody.closest(".message");
    promptInput.value = "";
    sendBtn.disabled = true;
    sendBtn.innerText = "Generating...";
    const output = addMessage("assistant", "Generating response...");
    output.classList.add("generating-output");
    sendStatus.textContent = "Message sent - Generating response...";

    const formData = new FormData();
    formData.append("prompt", prompt);
    formData.append("code", code);
    formData.append("model", modelInput.value);
    formData.append("language", languageInput.value);
    if (currentSessionId) formData.append("session_id", currentSessionId);
    if (editId) formData.append("edit_message_id", editId);
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
            await readStream(response, output, userWrapper);
        }
    } catch (error) {
        output.innerText = "Error: Backend or Ollama not available.\n\n" + error;
    } finally {
        output.classList.remove("generating-output");
        sendBtn.disabled = false;
        sendBtn.innerText = "Send";
        sendStatus.textContent = "";
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

async function generateTests() {
    const code = codeInput.value.trim();
    const output = document.getElementById("testOutput");
    const input = document.getElementById("testInput");
    if (!code) {
        alert("Paste code before generating tests.");
        return;
    }
    output.innerText = "Generating test scaffold...";
    try {
        const response = await fetch("/api/tests/generate/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams({ code, language: languageInput.value }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Test generation failed.");
        input.value = data.test_code;
        output.innerText = data.summary + " Edit the scaffold, then run it.";
    } catch (error) {
        output.innerText = "Test generation error: " + error;
    }
}

async function runTests() {
    const code = codeInput.value.trim();
    const testCode = document.getElementById("testInput").value.trim();
    const output = document.getElementById("testOutput");
    if (!code || !testCode) {
        alert("Provide source code and test code.");
        return;
    }
    output.innerText = "Running tests in the guarded sandbox...";
    try {
        const response = await fetch("/api/tests/run/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams({
                code,
                test_code: testCode,
                language: languageInput.value,
            }),
        });
        const data = await response.json();
        if (!data.result) throw new Error(data.error || "Test execution failed.");
        const result = data.result;
        const detail = result.success ? (result.stdout || "Completed without output.") : (result.stderr || result.error || "No output.");
        output.innerText = data.summary + "\n\n" + detail + "\n\nDuration: " + result.duration_ms + " ms";
    } catch (error) {
        output.innerText = "Test execution error: " + error;
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
        data.messages.forEach(message => {
            const options = message.role === "user"
                ? {
                    messageId: message.id,
                    payload: parseStoredUserMessage(message.content, data.model),
                }
                : {};
            addMessage(message.role, message.content, options);
        });
    } catch (error) {
        alert("Error loading chat: " + error);
    }
}

function renderChatHistory(sessions) {
    if (!chatHistory) return;
    chatHistory.innerHTML = "";
    if (!sessions.length) {
        chatHistory.innerText = "No matching chats.";
        return;
    }

    sessions.forEach(session => {
        const row = document.createElement("div");
        row.className = "history-row";

        const loadButton = document.createElement("button");
        loadButton.type = "button";
        loadButton.className = "history-item";
        loadButton.innerText = (session.is_pinned ? "Pinned | " : "") + session.title;
        loadButton.title = session.title + " | " + session.updated_at;
        loadButton.onclick = () => loadSession(session.id);
        row.appendChild(loadButton);

        if (session.tags.length) {
            const tags = document.createElement("span");
            tags.className = "history-tags";
            tags.innerText = session.tags.join(", ");
            row.appendChild(tags);
        }

        const actions = document.createElement("div");
        actions.className = "history-actions";
        [
            ["Rename", "rename"],
            ["Tag", "tag"],
            [session.is_pinned ? "Unpin" : "Pin", "pin"],
            ["Archive", "archive"],
            ["Delete", "delete"],
        ].forEach(([label, action]) => {
            const button = document.createElement("button");
            button.type = "button";
            button.innerText = label;
            button.title = label + " chat";
            button.onclick = event => {
                event.stopPropagation();
                manageChatSession(session, action);
            };
            actions.appendChild(button);
        });
        row.appendChild(actions);
        chatHistory.appendChild(row);
    });
}

async function loadChatHistory() {
    if (!chatHistory) return;
    const query = chatSearch ? chatSearch.value.trim() : "";
    chatHistory.innerText = "Loading chats...";
    try {
        const response = await fetch("/api/sessions/?q=" + encodeURIComponent(query));
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to load chats.");
        renderChatHistory(data.sessions);
    } catch (error) {
        chatHistory.innerText = "Chat history unavailable.";
    }
}

async function manageChatSession(session, action) {
    const values = { action };
    if (action === "rename") {
        const title = prompt("Rename chat", session.title);
        if (!title) return;
        values.title = title;
    }
    if (action === "tag") {
        const tags = prompt("Tags separated by commas", session.tags.join(", "));
        if (tags === null) return;
        values.tags = tags;
    }
    if (action === "delete" && !confirm("Delete this chat permanently?")) return;

    try {
        const response = await fetch("/api/session/" + session.id + "/manage/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams(values),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Chat update failed.");
        if (action === "delete" && currentSessionId === session.id) newChat();
        await loadChatHistory();
    } catch (error) {
        alert("Chat update failed: " + error);
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
            item.innerText = result.filename + ":" + result.line_start + "-" + result.line_end;
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

function formatFileSize(bytes) {
    if (!bytes) return "0 B";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function syncEditorPreview() {
    if (!editorPreview) return;
    const language = languageInput.value === "auto" ? "text" : languageInput.value;
    const code = editorPreview.querySelector("code");
    code.innerHTML = highlightCode(codeInput.value || " ", language);
}

function syncActiveEditorTab() {
    const active = editorTabsState.find(tab => tab.id === activeEditorDocumentId);
    if (active) active.content = codeInput.value;
}

function renderEditorTabs() {
    if (!editorTabs) return;
    editorTabs.innerHTML = "";
    const scratch = document.createElement("button");
    scratch.type = "button";
    scratch.className = "editor-tab" + (activeEditorDocumentId === null ? " active" : "");
    scratch.innerText = "Scratch buffer";
    scratch.onclick = () => selectEditorTab(null);
    editorTabs.appendChild(scratch);
    editorTabsState.forEach(tab => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "editor-tab" + (tab.id === activeEditorDocumentId ? " active" : "");
        button.innerText = tab.filename;
        button.title = tab.filename;
        button.onclick = () => selectEditorTab(tab.id);
        editorTabs.appendChild(button);
    });
}

function selectEditorTab(documentId) {
    syncActiveEditorTab();
    if (documentId === null) {
        activeEditorDocumentId = null;
        codeInput.value = "";
        if (editorFileName) editorFileName.innerText = "Scratch buffer";
        if (editorLanguage) editorLanguage.innerText = "Auto detect";
        if (saveFileBtn) saveFileBtn.disabled = true;
    } else {
        const tab = editorTabsState.find(item => item.id === documentId);
        if (!tab) return;
        activeEditorDocumentId = documentId;
        codeInput.value = tab.content;
        languageInput.value = tab.language || "auto";
        if (editorFileName) editorFileName.innerText = tab.filename;
        if (editorLanguage) editorLanguage.innerText = tab.language || "auto";
        if (saveFileBtn) saveFileBtn.disabled = false;
        updateActiveModel();
    }
    renderEditorTabs();
    syncEditorPreview();
    codeInput.focus();
}

async function openProjectFile(documentId) {
    try {
        const response = await fetch("/api/project/" + documentId + "/content/");
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to open file.");
        const document = data.document;
        const existing = editorTabsState.find(tab => tab.id === document.id);
        if (existing) {
            selectEditorTab(document.id);
            return;
        }
        syncActiveEditorTab();
        editorTabsState.push({
            id: document.id,
            filename: document.filename,
            language: document.language,
            content: document.content,
        });
        selectEditorTab(document.id);
    } catch (error) {
        alert("Unable to open project file: " + error);
    }
}

async function saveProjectFile() {
    if (!activeEditorDocumentId) return;
    syncActiveEditorTab();
    try {
        const response = await fetch("/api/project/" + activeEditorDocumentId + "/content/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams({ content: codeInput.value }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Save failed.");
        sendStatus.textContent = "Saved and reindexed " + (editorFileName ? editorFileName.innerText : "file") + ".";
        await loadProjectWorkspace();
    } catch (error) {
        alert("Unable to save file: " + error);
    }
}

async function openPatchReview(updated, language) {
    if (!patchPanel) {
        alert("Sign in to review and apply AI patches.");
        return;
    }
    try {
        const response = await fetch("/api/patch/preview/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams({
                original: codeInput.value,
                updated,
                filename: editorFileName ? editorFileName.innerText : "editor-buffer",
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to create patch.");
        pendingPatch = { updated, language };
        codeBeforePatch = codeInput.value;
        patchDiff.innerText = data.diff;
        patchStatus.innerText = data.changed ? "Review the changes before applying." : "No changes detected.";
        patchPanel.hidden = false;
        patchPanel.scrollIntoView({ behavior: "smooth", block: "center" });
    } catch (error) {
        alert("Unable to review patch: " + error);
    }
}

function applyPatch() {
    if (!pendingPatch) return;
    codeInput.value = pendingPatch.updated;
    if (pendingPatch.language && [...languageInput.options].some(option => option.value === pendingPatch.language)) {
        languageInput.value = pendingPatch.language;
    }
    syncActiveEditorTab();
    syncEditorPreview();
    if (patchStatus) patchStatus.innerText = "Patch applied. Save the file when ready.";
}

function restorePatch() {
    if (!pendingPatch) return;
    codeInput.value = codeBeforePatch;
    syncActiveEditorTab();
    syncEditorPreview();
    if (patchStatus) patchStatus.innerText = "Previous code restored.";
}

function rejectPatch() {
    pendingPatch = null;
    codeBeforePatch = "";
    if (patchPanel) patchPanel.hidden = true;
}

async function loadProjectWorkspace() {
    if (!projectFiles) return;
    projectFiles.innerText = "Loading indexed files...";
    try {
        const response = await fetch("/api/project/");
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to load project files.");
        projectFiles.innerHTML = "";
        const totalChunks = data.documents.reduce((sum, document) => sum + document.chunks, 0);
        projectStats.innerText = data.documents.length
            ? data.documents.length + " file(s) | " + totalChunks + " indexed chunk(s)"
            : "No indexed files yet.";

        data.documents.forEach(document => {
            const row = document.createElement("div");
            row.className = "project-file";

            const info = document.createElement("div");
            info.className = "project-file-info";
            const name = document.createElement("strong");
            name.className = "project-file-name";
            name.innerText = document.filename;
            name.title = document.filename;
            name.onclick = () => openProjectFile(document.id);
            const meta = document.createElement("span");
            meta.innerText = document.language + " | " + formatFileSize(document.size_bytes) + " | " + document.chunks + " chunks";
            info.append(name, meta);

            const actions = document.createElement("div");
            actions.className = "project-file-actions";
            const reindexButton = document.createElement("button");
            reindexButton.type = "button";
            reindexButton.innerText = "Reindex";
            reindexButton.onclick = () => reindexProjectFile(document.id);
            const deleteButton = document.createElement("button");
            deleteButton.type = "button";
            deleteButton.innerText = "Delete";
            deleteButton.onclick = () => deleteProjectFile(document.id, document.filename);
            actions.append(reindexButton, deleteButton);

            row.append(info, actions);
            projectFiles.appendChild(row);
        });
    } catch (error) {
        projectFiles.innerText = "Project workspace unavailable.";
    }
}

function renderGitFiles(files) {
    if (!gitFiles) return;
    gitFiles.innerHTML = "";
    if (!files.length) {
        gitFiles.innerText = "Working tree clean.";
        return;
    }
    const stageAll = document.createElement("button");
    stageAll.type = "button";
    stageAll.className = "git-stage-all";
    stageAll.innerText = "Stage all changes";
    stageAll.onclick = () => stageGitFile("");
    gitFiles.appendChild(stageAll);
    files.forEach(file => {
        const row = document.createElement("div");
        row.className = "git-file";
        const status = document.createElement("span");
        status.className = "git-file-status";
        status.innerText = file.status || "??";
        const path = document.createElement("span");
        path.className = "git-file-path";
        path.innerText = file.path;
        path.title = file.path;
        const button = document.createElement("button");
        button.type = "button";
        button.innerText = "Stage";
        button.onclick = () => stageGitFile(file.path);
        row.append(status, path, button);
        gitFiles.appendChild(row);
    });
}

async function loadGitStatus() {
    if (!gitFiles) return;
    gitFiles.innerText = "Loading Git status...";
    try {
        const [statusResponse, diffResponse] = await Promise.all([
            fetch("/api/git/status/"),
            fetch("/api/git/diff/"),
        ]);
        const status = await statusResponse.json();
        const diff = await diffResponse.json();
        if (!status.success) throw new Error(status.error || "Unable to load Git status.");
        gitBranch.innerText = "Branch: " + status.branch + " | " + status.files.length + " changed file(s)";
        renderGitFiles(status.files);
        gitDiff.innerText = diff.success ? (diff.diff || "No diff available.") : (diff.error || "Unable to load diff.");
    } catch (error) {
        gitBranch.innerText = "Git unavailable";
        gitFiles.innerText = String(error);
    }
}

async function stageGitFile(path) {
    try {
        const body = new URLSearchParams();
        if (path) body.append("paths", path);
        const response = await fetch("/api/git/stage/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken },
            body,
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to stage changes.");
        await loadGitStatus();
    } catch (error) {
        alert("Git stage failed: " + error);
    }
}

async function commitGitChanges() {
    const message = gitCommitMessage ? gitCommitMessage.value.trim() : "";
    if (!message) {
        alert("Enter a commit message.");
        return;
    }
    try {
        const response = await fetch("/api/git/commit/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams({ message }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to create commit.");
        gitCommitMessage.value = "";
        sendStatus.innerText = "Git commit created.";
        await loadGitStatus();
    } catch (error) {
        alert("Git commit failed: " + error);
    }
}

async function reindexProjectFile(documentId) {
    try {
        await fetch("/api/project/" + documentId + "/reindex/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken },
        });
        await loadProjectWorkspace();
    } catch (error) {
        alert("Reindex failed: " + error);
    }
}

async function deleteProjectFile(documentId, filename) {
    if (!confirm("Delete " + filename + " from the project workspace?")) return;
    try {
        await fetch("/api/project/" + documentId + "/", {
            method: "DELETE",
            headers: { "X-CSRFToken": csrfToken },
        });
        await loadProjectWorkspace();
    } catch (error) {
        alert("Delete failed: " + error);
    }
}

if (searchInput) searchInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter") searchProject();
});

if (chatSearch) chatSearch.addEventListener("keydown", function (event) {
    if (event.key === "Enter") loadChatHistory();
});

promptInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
});

modelInput.addEventListener("change", updateActiveModel);
codeInput.addEventListener("input", syncEditorPreview);
languageInput.addEventListener("change", function () {
    if (editorLanguage && activeEditorDocumentId) editorLanguage.innerText = languageInput.value;
    syncEditorPreview();
});
updateActiveModel();
renderEditorTabs();
syncEditorPreview();
if (projectFiles) loadProjectWorkspace();
if (gitFiles) loadGitStatus();
if (ollamaSettingsPanel) loadOllamaSettings();
if (chatHistory) loadChatHistory();
