let currentSessionId = null;

const chatBox = document.getElementById("chatBox");
const promptInput = document.getElementById("promptInput");
const codeInput = document.getElementById("codeInput");
const modelInput = document.getElementById("model");
const languageInput = document.getElementById("language");
const fileInput = document.getElementById("fileInput");
const sendBtn = document.getElementById("sendBtn");
const csrfToken = document.getElementById("csrfToken").value;

function updateActiveModel() {
    const activeModel = document.getElementById("activeModel");
    if (activeModel && modelInput) activeModel.innerText = modelInput.value;
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
    fileInput.value = "";
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
    body.innerText = content;

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
            output.innerText = event.answer;
        } else if (event.type === "error") {
            output.innerText = "Error:\\n" + event.error;
        }
    };

    while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const lines = buffer.split("\\n");
        buffer = lines.pop();
        lines.forEach(consumeLine);
        if (done) break;
    }

    if (buffer.trim()) consumeLine(buffer);
}

async function sendMessage() {
    const prompt = promptInput.value.trim();
    const code = codeInput.value.trim();
    const files = fileInput.files;

    if (!prompt && !code && files.length === 0) {
        alert("Please enter prompt, paste code, or upload one or more files.");
        return;
    }

    let userText = prompt ? "Prompt:\\n" + prompt : "";
    if (files.length > 0) {
        userText += "\\n\\nUploaded Files:\\n";
        userText += Array.from(files).map(file => file.name).join("\\n");
    }
    if (code) userText += "\\n\\nCode:\\n" + code.substring(0, 2000);

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
    Array.from(files).forEach(file => formData.append("files", file));

    try {
        const response = await fetch("/api/ask-code/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken },
            body: formData,
        });

        if (!response.ok) {
            const data = await response.json();
            output.innerText = "Error:\\n" + (data.error || "Request failed.");
        } else {
            await readStream(response, output);
        }
    } catch (error) {
        output.innerText = "Error: Backend or Ollama not available.\\n\\n" + error;
    } finally {
        sendBtn.disabled = false;
        sendBtn.innerText = "Send";
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

promptInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
});

modelInput.addEventListener("change", updateActiveModel);
updateActiveModel();
