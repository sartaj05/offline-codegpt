let currentSessionId = null;

const chatBox = document.getElementById("chatBox");
const promptInput = document.getElementById("promptInput");
const codeInput = document.getElementById("codeInput");
const languageInput = document.getElementById("language");
const fileInput = document.getElementById("fileInput");
const sendBtn = document.getElementById("sendBtn");
const csrfToken = document.getElementById("csrfToken").value;


function clearWelcome() {
    const welcome = document.querySelector(".welcome");
    if (welcome) {
        welcome.remove();
    }
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
        </div>
    `;

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

    inner.appendChild(avatar);
    inner.appendChild(body);
    wrapper.appendChild(inner);

    chatBox.appendChild(wrapper);
    chatBox.scrollTop = chatBox.scrollHeight;
}


async function sendMessage() {
    const prompt = promptInput.value.trim();
    const code = codeInput.value.trim();
    const files = fileInput.files;

    if (!prompt && !code && files.length === 0) {
    alert("Please enter prompt, paste code, or upload one or more files.");
    return;
}

    let userText = "";

    if (prompt) {
        userText += "Prompt:\n" + prompt;
    }

    if (files.length > 0) {
    let fileNames = [];

    for (let i = 0; i < files.length; i++) {
        fileNames.push(files[i].name);
    }

    userText += "\n\nUploaded Files:\n" + fileNames.join("\n");
}
    if (code) {
        userText += "\n\nCode:\n" + code.substring(0, 2000);
    }

    addMessage("user", userText);

    promptInput.value = "";

    sendBtn.disabled = true;
    sendBtn.innerText = "...";

    const thinkingId = "thinking-" + Date.now();
    addMessage("assistant", "Thinking locally...");

    const formData = new FormData();
    formData.append("prompt", prompt);
    formData.append("code", code);
    formData.append("language", languageInput.value);

    if (currentSessionId) {
        formData.append("session_id", currentSessionId);
    }

    for (let i = 0; i < files.length; i++) {
    formData.append("files", files[i]);
}
    try {
        const response = await fetch("/api/ask-code/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken
            },
            body: formData
        });

        const data = await response.json();

        const messages = document.querySelectorAll(".assistant-message .message-content");
        const lastAssistant = messages[messages.length - 1];

        if (data.success) {
            currentSessionId = data.session_id;
            lastAssistant.innerText = data.answer;
        } else {
            lastAssistant.innerText = "Error:\n" + data.error;
        }

    } catch (error) {
        const messages = document.querySelectorAll(".assistant-message .message-content");
        const lastAssistant = messages[messages.length - 1];

        lastAssistant.innerText =
            "Error: Backend or Ollama not available.\n\n" +
            "Check:\n" +
            "1. Django server is running\n" +
            "2. Ollama is running\n" +
            "3. Model is available\n\n" +
            error;
    }

    sendBtn.disabled = false;
    sendBtn.innerText = "Send";
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

        data.messages.forEach(msg => {
            addMessage(msg.role, msg.content);
        });

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