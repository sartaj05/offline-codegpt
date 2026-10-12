const vscode = require("vscode");
const cp = require("child_process");

async function askServer(serverUrl, prompt, code, accessToken = "") {
    const body = new URLSearchParams({ prompt, code, language: "auto" });
    const response = await fetch(serverUrl.replace(/\/$/, "") + "/api/cli/ask/", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded", ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) },
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

function firstCodeBlock(text) {
    const match = String(text || "").match(/```(?:[A-Za-z0-9_+#.-]+)?\s*\n([\s\S]*?)```/);
    return match ? match[1].trimEnd() : String(text || "").trim();
}

function addReviewDiagnostics(collection, document, answer) {
    const diagnostics = [];
    String(answer || "").split("\n").forEach((line) => {
        const match = line.match(/(?:line|L)\s*(\d+)/i);
        if (!match) return;
        const lineNumber = Math.max(1, Math.min(Number(match[1]), document.lineCount)) - 1;
        diagnostics.push(new vscode.Diagnostic(new vscode.Range(lineNumber, 0, lineNumber, document.lineAt(lineNumber).text.length), line.trim(), vscode.DiagnosticSeverity.Warning));
    });
    collection.set(document.uri, diagnostics);
}

function activate(context) {
    const output = vscode.window.createOutputChannel("Syntax Local AI");
    const diagnostics = vscode.languages.createDiagnosticCollection("syntax-local-ai");
    let lastSuggestion = "";
    const serverUrl = () => vscode.workspace.getConfiguration("syntaxLocalAI").get("serverUrl");
    const accessToken = () => vscode.workspace.getConfiguration("syntaxLocalAI").get("accessToken") || process.env.SYNTAX_LOCAL_AI_TOKEN || "";

    const runPrompt = async (prompt, code, label) => {
        output.show(true);
        output.appendLine("\n--- " + label + " ---");
        try {
            const answer = await askServer(serverUrl(), prompt, code, accessToken());
            lastSuggestion = answer;
            output.appendLine(answer);
            return answer;
        } catch (error) {
            output.appendLine("Error: " + error.message);
            return "";
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
        const answer = await runPrompt("Review this file for bugs, security issues, tests, and concrete improvements. Include line numbers for findings.", editor.document.getText(), "File review");
        addReviewDiagnostics(diagnostics, editor.document, answer);
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

    context.subscriptions.push(vscode.commands.registerCommand("syntaxLocalAI.applyLastSuggestion", async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor || !lastSuggestion) {
            vscode.window.showInformationMessage("Run a local coding request first.");
            return;
        }
        const answer = firstCodeBlock(lastSuggestion);
        const approved = await vscode.window.showWarningMessage("Apply the latest suggested code to the current editor?", { modal: true }, "Apply");
        if (approved !== "Apply") return;
        const target = editor.selection.isEmpty ? new vscode.Range(0, 0, editor.document.lineCount, 0) : editor.selection;
        await editor.edit((edit) => edit.replace(target, answer));
        output.appendLine("Applied the reviewed suggestion. Undo remains available in VS Code.");
    }));

    context.subscriptions.push(vscode.commands.registerCommand("syntaxLocalAI.previewLastSuggestion", async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor || !lastSuggestion) {
            vscode.window.showInformationMessage("Run a local coding request first.");
            return;
        }
        const proposed = firstCodeBlock(lastSuggestion);
        const current = editor.document.getText(editor.selection) || editor.document.getText();
        const currentDoc = await vscode.workspace.openTextDocument({ language: editor.document.languageId, content: current });
        const proposedDoc = await vscode.workspace.openTextDocument({ language: editor.document.languageId, content: proposed });
        await vscode.commands.executeCommand("vscode.diff", currentDoc.uri, proposedDoc.uri, "Syntax Local AI: proposed patch");
    }));

    context.subscriptions.push(vscode.commands.registerCommand("syntaxLocalAI.clearDiagnostics", () => diagnostics.clear()));

    context.subscriptions.push(vscode.commands.registerCommand("syntaxLocalAI.runProjectTests", async () => {
        const command = vscode.workspace.getConfiguration("syntaxLocalAI").get("testCommand");
        const approved = await vscode.window.showInformationMessage(`Run local tests: ${command}`, { modal: true }, "Run tests");
        if (approved !== "Run tests") return;
        const folder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!folder) { vscode.window.showErrorMessage("Open a workspace before running tests."); return; }
        const result = await new Promise((resolve) => cp.exec(command, { cwd: folder, timeout: 120000, maxBuffer: 2 * 1024 * 1024 }, (error, stdout, stderr) => resolve({ error, stdout, stderr })));
        output.appendLine(`\n--- Project tests ---\n${result.stdout || result.stderr || "No test output."}`);
        vscode.window.showInformationMessage(result.error ? "Local tests failed. See Syntax Local AI output." : "Local tests passed.");
        if (result.error) output.appendLine(`Exit error: ${result.error.message}`);
    }));

    context.subscriptions.push(vscode.languages.registerInlineCompletionItemProvider({ scheme: "file" }, {
        async provideInlineCompletionItems(document, position, context, token) {
            if (token.isCancellationRequested) return { items: [] };
            const linePrefix = document.lineAt(position.line).text.slice(0, position.character);
            if (linePrefix.trim().length < 3) return { items: [] };
            const lineSuffix = document.lineAt(position.line).text.slice(position.character);
            try {
                const answer = await askServer(serverUrl(), "Complete the code after PREFIX. Return only the missing code, with no markdown.\nPREFIX:\n" + linePrefix + "\nSUFFIX:\n" + lineSuffix, document.getText(), accessToken());
                const completion = answer.replace(/^```[A-Za-z0-9_+#.-]*\s*|```$/g, "").trim();
                if (!completion || token.isCancellationRequested) return { items: [] };
                return { items: [new vscode.InlineCompletionItem(completion, new vscode.Range(position, position))] };
            } catch (error) {
                return { items: [] };
            }
        }
    }));
    context.subscriptions.push(vscode.languages.registerCodeActionsProvider({ scheme: "file" }, {
        provideCodeActions(document, range) {
            const actions = [];
            for (const diagnostic of diagnostics.get(document.uri) || []) {
                if (diagnostic.range.intersection(range)) {
                    const action = new vscode.CodeAction("Ask Syntax Local AI about this finding", vscode.CodeActionKind.QuickFix);
                    action.command = { command: "syntaxLocalAI.askSelection", title: "Ask Syntax Local AI" };
                    actions.push(action);
                }
            }
            return actions;
        }
    }));
    context.subscriptions.push(diagnostics);
}

function deactivate() {}

module.exports = { activate, deactivate };
