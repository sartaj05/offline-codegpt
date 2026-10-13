const assert = require("assert");
const fs = require("fs");

const extension = fs.readFileSync("vscode-extension/extension.js", "utf8");
const manifest = JSON.parse(fs.readFileSync("vscode-extension/package.json", "utf8"));
const commands = manifest.contributes.commands.map((item) => item.command);

for (const command of [
  "syntaxLocalAI.askSelection",
  "syntaxLocalAI.reviewFile",
  "syntaxLocalAI.applyLastSuggestion",
  "syntaxLocalAI.runProjectTests",
  "syntaxLocalAI.previewLastSuggestion",
  "syntaxLocalAI.configureHybrid",
  "syntaxLocalAI.hybridStatus",
  "syntaxLocalAI.queueHybridTask",
  "syntaxLocalAI.refreshHybridTasks",
]) {
  assert(commands.includes(command), `missing command ${command}`);
}
assert(extension.includes("/api/cli/ask/"), "extension must use the local CLI endpoint");
assert(extension.includes("Authorization"), "extension must support local authorization");
assert(extension.includes("vscode.diff"), "extension must provide patch preview");
assert(extension.includes("registerInlineCompletionItemProvider"), "extension must provide inline completion");
assert(extension.includes("cp.exec"), "extension must expose confirmed local test execution");
assert(extension.includes("context.secrets.store"), "extension must store hybrid credentials securely");
assert(extension.includes("/api/connector/token/tasks/"), "extension must support hybrid task submission");
console.log("VS Code extension integration contract passed");
