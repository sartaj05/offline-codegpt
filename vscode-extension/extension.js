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

    const runPrompt = async (prompt, code, label) => {
        output.show(true);
        output.appendLine("\n--- " + label + " ---");
        try {
            output.appendLine(await askServer(serverUrl(), prompt, code));
        } catch (error) {
            output.appendLine("Error: " + error.message);
        }
    };

    context.subscriptions.push(vscode.commands.registerCommand("syntaxLocalAI.askSelection", async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) return;
        const prompt = await vscode.window.showInputBox({ prompt: "What should Syntax Local AI do?" });
        if (!prompt) return;
        const code = editor.document.getText(editor.selection) || editor.document.getText();
        await runPrompt(prompt, code, "Selection request");
    }));

    context.subscriptions.push(vscode.commands.registerCommand("syntaxLocalAI.reviewFile", async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) return;
        await runPrompt("Review this file for bugs, security issues, tests, and concrete improvements.", editor.document.getText(), "File review");
    }));

    context.subscriptions.push(vscode.commands.registerCommand("syntaxLocalAI.explainSelection", async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) return;
        const code = editor.document.getText(editor.selection) || editor.document.getText();
        await runPrompt("Explain this code, its dependencies, edge cases, and likely failure modes.", code, "Code explanation");
    }));

    context.subscriptions.push(vscode.commands.registerCommand("syntaxLocalAI.generateTests", async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) return;
        await runPrompt("Generate focused tests for this code. Return an editable test file with a short rationale.", editor.document.getText(), "Test generation");
    }));

    context.subscriptions.push(vscode.commands.registerCommand("syntaxLocalAI.askProject", async () => {
        const prompt = await vscode.window.showInputBox({ prompt: "Ask the local project workspace" });
        if (!prompt) return;
        await runPrompt(prompt, "", "Project request");
    }));
}

function deactivate() {}

module.exports = { activate, deactivate };
