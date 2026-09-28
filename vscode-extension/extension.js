const vscode = require("vscode");

async function askServer(serverUrl, prompt, code) {
    const body = new URLSearchParams({ prompt, code, language: "auto" });
    const response = await fetch(serverUrl.replace(/\/$/, "") + "/api/cli/ask/", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
    });
    const text = await response.text();
    const answer = [];
    text.split("\n").forEach(line => {
        try {
            const event = JSON.parse(line);
            if (event.type === "token") answer.push(event.token || "");
            if (event.type === "error") answer.push("\nError: " + event.error);
        } catch (error) {
            // Ignore incomplete non-event lines.
        }
    });
    if (!response.ok) throw new Error(answer.join("") || "Syntax Local AI request failed.");
    return answer.join("");
}

function activate(context) {
    const output = vscode.window.createOutputChannel("Syntax Local AI");
    const serverUrl = () => vscode.workspace.getConfiguration("syntaxLocalAI").get("serverUrl");

    context.subscriptions.push(vscode.commands.registerCommand("syntaxLocalAI.askSelection", async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) return;
        const prompt = await vscode.window.showInputBox({ prompt: "What should Syntax Local AI do?" });
        if (!prompt) return;
        const code = editor.document.getText(editor.selection) || editor.document.getText();
        output.show(true);
        output.appendLine("Working...");
        try {
            output.appendLine(await askServer(serverUrl(), prompt, code));
        } catch (error) {
            output.appendLine("Error: " + error.message);
        }
    }));

    context.subscriptions.push(vscode.commands.registerCommand("syntaxLocalAI.reviewFile", async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) return;
        output.show(true);
        output.appendLine("Reviewing " + editor.document.fileName + "...");
        try {
            output.appendLine(await askServer(
                serverUrl(),
                "Review this file for bugs, security issues, tests, and concrete improvements.",
                editor.document.getText(),
            ));
        } catch (error) {
            output.appendLine("Error: " + error.message);
        }
    }));
}

function deactivate() {}

module.exports = { activate, deactivate };
