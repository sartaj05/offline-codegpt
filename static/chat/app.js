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
const remoteIntegrationPanel = document.getElementById("remoteIntegrationPanel");
const remoteProvider = document.getElementById("remoteProvider");
const remoteRepository = document.getElementById("remoteRepository");
const remoteToken = document.getElementById("remoteToken");
const remoteOutput = document.getElementById("remoteOutput");
const mcpPanel = document.getElementById("mcpPanel");
const mcpConnectorName = document.getElementById("mcpConnectorName");
const mcpConnectorType = document.getElementById("mcpConnectorType");
const mcpConnectorConfig = document.getElementById("mcpConnectorConfig");
const mcpConnectorList = document.getElementById("mcpConnectorList");
const mcpSearchQuery = document.getElementById("mcpSearchQuery");
const mcpOutput = document.getElementById("mcpOutput");
const observabilityPanel = document.getElementById("observabilityPanel");
const evaluationPanel = document.getElementById("evaluationPanel");
const evaluationTaskName = document.getElementById("evaluationTaskName");
const evaluationTaskLanguage = document.getElementById("evaluationTaskLanguage");
const evaluationTaskTags = document.getElementById("evaluationTaskTags");
const evaluationTaskPrompt = document.getElementById("evaluationTaskPrompt");
const evaluationTaskCode = document.getElementById("evaluationTaskCode");
const evaluationTaskExpected = document.getElementById("evaluationTaskExpected");
const evaluationTaskStatus = document.getElementById("evaluationTaskStatus");
const evaluationTaskList = document.getElementById("evaluationTaskList");
const evaluationSuiteName = document.getElementById("evaluationSuiteName");
const evaluationSuiteDescription = document.getElementById("evaluationSuiteDescription");
const evaluationSuiteStatus = document.getElementById("evaluationSuiteStatus");
const evaluationSuiteList = document.getElementById("evaluationSuiteList");
const evaluationDashboardStats = document.getElementById("evaluationDashboardStats");
const evaluationDashboardModels = document.getElementById("evaluationDashboardModels");
const evaluationDashboardRecent = document.getElementById("evaluationDashboardRecent");
let evaluationTasksCache = [];
const observabilityStats = document.getElementById("observabilityStats");
const observabilityOutput = document.getElementById("observabilityOutput");
let observabilityTimer = null;
const sandboxTimeout = document.getElementById("sandboxTimeout");
const sandboxMemory = document.getElementById("sandboxMemory");
const sandboxOutputChars = document.getElementById("sandboxOutputChars");
const sandboxApproval = document.getElementById("sandboxApproval");
const sandboxPolicyStatus = document.getElementById("sandboxPolicyStatus");
const workspacePanel = document.getElementById("workspacePanel");
const workspaceName = document.getElementById("workspaceName");
const workspaceMember = document.getElementById("workspaceMember");
const workspaceRole = document.getElementById("workspaceRole");
const workspaceSummary = document.getElementById("workspaceSummary");
const workspaceMembers = document.getElementById("workspaceMembers");
const workspaceAudit = document.getElementById("workspaceAudit");
const devopsPanel = document.getElementById("devopsPanel");
const devopsKind = document.getElementById("devopsKind");
const devopsArtifact = document.getElementById("devopsArtifact");
const devopsLogs = document.getElementById("devopsLogs");
const devopsLogOutput = document.getElementById("devopsLogOutput");
const documentationPanel = document.getElementById("documentationPanel");
const documentationType = document.getElementById("documentationType");
const documentationProjectName = document.getElementById("documentationProjectName");
const documentationChangeSummary = document.getElementById("documentationChangeSummary");
const documentationOutput = document.getElementById("documentationOutput");
const reviewGatePanel = document.getElementById("reviewGatePanel");
const reviewDiff = document.getElementById("reviewDiff");
const reviewTests = document.getElementById("reviewTests");
const reviewGateSummary = document.getElementById("reviewGateSummary");
const reviewGateOutput = document.getElementById("reviewGateOutput");
const dependenciesPanel = document.getElementById("dependenciesPanel");
const dependencyFilename = document.getElementById("dependencyFilename");
const dependencyContent = document.getElementById("dependencyContent");
const dependencyOutput = document.getElementById("dependencyOutput");
const browserTestsPanel = document.getElementById("browserTestsPanel");
const browserBaseUrl = document.getElementById("browserBaseUrl");
const browserSnapshotName = document.getElementById("browserSnapshotName");
const browserFlow = document.getElementById("browserFlow");
const browserTestOutput = document.getElementById("browserTestOutput");
const browserReport = document.getElementById("browserReport");
const browserReportOutput = document.getElementById("browserReportOutput");
const modelRouterPanel = document.getElementById("modelRouterPanel");
const routerTask = document.getElementById("routerTask");
const routerMemory = document.getElementById("routerMemory");
const routerGpu = document.getElementById("routerGpu");
const routerOutput = document.getElementById("routerOutput");
const devcontainerPanel = document.getElementById("devcontainerPanel");
const devcontainerProjectName = document.getElementById("devcontainerProjectName");
const devcontainerOutput = document.getElementById("devcontainerOutput");
const incidentPanel = document.getElementById("incidentPanel");
const incidentLogs = document.getElementById("incidentLogs");
const incidentTraces = document.getElementById("incidentTraces");
const incidentMetrics = document.getElementById("incidentMetrics");
const incidentOutput = document.getElementById("incidentOutput");
const architecturePanel = document.getElementById("architecturePanel");
const architectureFiles = document.getElementById("architectureFiles");
const architectureOutput = document.getElementById("architectureOutput");
const crossRepositoryFiles = document.getElementById("crossRepositoryFiles");
const crossRepositoryOutput = document.getElementById("crossRepositoryOutput");
const contractsPanel = document.getElementById("contractsPanel");
const contractSpec = document.getElementById("contractSpec");
const contractCode = document.getElementById("contractCode");
const contractOutput = document.getElementById("contractOutput");
const provenancePanel = document.getElementById("provenancePanel");
const provenanceArtifact = document.getElementById("provenanceArtifact");
const provenanceCommit = document.getElementById("provenanceCommit");
const provenanceFiles = document.getElementById("provenanceFiles");
const provenanceOutput = document.getElementById("provenanceOutput");
const provenanceStatus = document.getElementById("provenanceStatus");
const identityPolicyPanel = document.getElementById("identityPolicyPanel");
const identitySummary = document.getElementById("identitySummary");
const policyGit = document.getElementById("policyGit");
const policyTools = document.getElementById("policyTools");
const policyDeploy = document.getElementById("policyDeploy");
const policyTests = document.getElementById("policyTests");
const policyExternal = document.getElementById("policyExternal");
const policyRetention = document.getElementById("policyRetention");
const identityPolicyStatus = document.getElementById("identityPolicyStatus");
const enterpriseProvider = document.getElementById("enterpriseProvider");
const enterpriseIssuer = document.getElementById("enterpriseIssuer");
const enterpriseSamlEntrypoint = document.getElementById("enterpriseSamlEntrypoint");
const enterpriseClientId = document.getElementById("enterpriseClientId");
const enterpriseDomains = document.getElementById("enterpriseDomains");
const enterpriseEnforce = document.getElementById("enterpriseEnforce");
const enterpriseScim = document.getElementById("enterpriseScim");
const enterpriseIdentityStatus = document.getElementById("enterpriseIdentityStatus");
const enterpriseScimToken = document.getElementById("enterpriseScimToken");
const secretsPanel = document.getElementById("secretsPanel");
const secretName = document.getElementById("secretName");
const secretValue = document.getElementById("secretValue");
const secretDescription = document.getElementById("secretDescription");
const secretsStatus = document.getElementById("secretsStatus");
const secretsList = document.getElementById("secretsList");
const secretRevealOutput = document.getElementById("secretRevealOutput");
const remotePrTitle = document.getElementById("remotePrTitle");
const remotePrHead = document.getElementById("remotePrHead");
const remotePrBase = document.getElementById("remotePrBase");
const remotePrBody = document.getElementById("remotePrBody");
const agentGoal = document.getElementById("agentGoal");
const agentStatus = document.getElementById("agentStatus");
const agentPlan = document.getElementById("agentPlan");
const agentLogs = document.getElementById("agentLogs");
const agentJobStatus = document.getElementById("agentJobStatus");
const agentTeamRoles = document.getElementById("agentTeamRoles");
const agentTeamStatus = document.getElementById("agentTeamStatus");
const agentTeamLogs = document.getElementById("agentTeamLogs");
let agentTaskId = null;
let agentTeamId = null;
let agentJobId = null;
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

function toggleRemoteIntegration() {
    if (!remoteIntegrationPanel) return;
    remoteIntegrationPanel.hidden = !remoteIntegrationPanel.hidden;
    if (!remoteIntegrationPanel.hidden && !remoteRepository.value) loadRemoteSettings();
}

async function loadRemoteSettings() {
    try {
        const response = await fetch("/api/remote/settings/");
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to load remote settings.");
        remoteProvider.value = data.provider;
        remoteRepository.value = data.repository;
        remoteOutput.innerText = data.token_set ? "Connected. Token is stored in this local session." : "Remote integration is not connected.";
    } catch (error) {
        remoteOutput.innerText = String(error);
    }
}

async function saveRemoteSettings() {
    remoteOutput.innerText = "Connecting...";
    try {
        const response = await fetch("/api/remote/settings/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams({
                provider: remoteProvider.value,
                repository: remoteRepository.value.trim(),
                token: remoteToken.value.trim(),
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Connection failed.");
        remoteToken.value = "";
        remoteOutput.innerText = "Connected. Token is stored in this local session.";
    } catch (error) {
        remoteOutput.innerText = String(error);
    }
}

async function loadRemoteRepositories() {
    remoteOutput.innerText = "Loading repositories...";
    try {
        const response = await fetch("/api/remote/repositories/");
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to load repositories.");
        remoteOutput.innerText = data.repositories.map(item => item.name).join("\n") || "No repositories found.";
    } catch (error) {
        remoteOutput.innerText = String(error);
    }
}

async function loadRemoteIssues() {
    remoteOutput.innerText = "Loading issues...";
    try {
        const response = await fetch("/api/remote/issues/?repository=" + encodeURIComponent(remoteRepository.value.trim()));
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to load issues.");
        remoteOutput.innerText = data.issues.map(item => "#" + item.id + " " + item.title).join("\n") || "No open issues found.";
    } catch (error) {
        remoteOutput.innerText = String(error);
    }
}

async function createRemotePullRequest() {
    remoteOutput.innerText = "Creating draft pull request...";
    try {
        const response = await fetch("/api/remote/pull-request/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams({
                repository: remoteRepository.value.trim(),
                title: remotePrTitle.value.trim(),
                head: remotePrHead.value.trim(),
                base: remotePrBase.value.trim(),
                body: remotePrBody.value,
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Pull request failed.");
        remoteOutput.innerText = "Draft pull request created: " + (data.url || "success");
    } catch (error) {
        remoteOutput.innerText = String(error);
    }
}

function toggleMcpPanel() {
    if (!mcpPanel) return;
    mcpPanel.hidden = !mcpPanel.hidden;
    if (!mcpPanel.hidden) loadMcpConnectors();
}

function toggleObservability() {
    if (!observabilityPanel) return;
    observabilityPanel.hidden = !observabilityPanel.hidden;
    if (observabilityPanel.hidden) {
        if (observabilityTimer) window.clearInterval(observabilityTimer);
        observabilityTimer = null;
        return;
    }
    loadObservability();
    if (observabilityTimer) window.clearInterval(observabilityTimer);
    observabilityTimer = window.setInterval(loadObservability, 5000);
}

async function loadObservability() {
    if (!observabilityOutput) return;
    observabilityOutput.innerText = "Loading local AI metrics...";
    try {
        const response = await fetch("/api/observability/");
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to load metrics.");
        const summary = data.summary;
        observabilityStats.innerHTML = [
            ["Requests", summary.events],
            ["Success rate", summary.success_rate + "%"],
            ["Avg. latency", summary.average_duration_ms + " ms"],
            ["Input chars", summary.input_chars],
            ["Output chars", summary.output_chars],
            ["Active jobs", data.agent_summary.active_jobs],
            ["Tool calls", data.resource_usage.tool_calls],
        ].map(item => "<div><strong>" + item[1] + "</strong><span>" + item[0] + "</span></div>").join("");
        const agentHeader = "Agent center: " + data.agent_summary.tasks + " tasks, " + data.agent_summary.teams + " teams, " + data.agent_summary.jobs + " jobs, " + data.agent_summary.failed_jobs + " failed jobs.";
        const timeline = data.timeline.map(item => item.created_at + " | " + item.kind + " | " + item.status + " | " + item.name + " | " + item.message);
        const aiEvents = data.events.map(event => event.created_at + " | AI " + (event.success ? "ok" : "failed") + " | " + (event.model || "local model") + " | " + event.duration_ms + " ms | in " + event.input_chars + " / out " + event.output_chars);
        observabilityOutput.innerText = agentHeader + "\nResource usage: " + data.resource_usage.cpu_ms + " CPU ms, " + data.resource_usage.memory_mb_peak + " MB peak memory.\n\n" +
            (timeline.length ? timeline.join("\n") : "No agent timeline events yet.") + "\n\n" +
            (aiEvents.length ? aiEvents.join("\n") : "No AI activity recorded yet.");
    } catch (error) {
        observabilityOutput.innerText = "Metrics error: " + error;
    }
}

function toggleEvaluationLab() {
    if (!evaluationPanel) return;
    evaluationPanel.hidden = !evaluationPanel.hidden;
    if (!evaluationPanel.hidden) {
        loadEvaluationTasks();
        loadEvaluationDashboard();
    }
}

async function loadEvaluationDashboard() {
    if (!evaluationDashboardStats) return;
    evaluationDashboardStats.innerText = "Loading evaluation metrics...";
    try {
        const response = await fetch("/api/evaluations/dashboard/");
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to load evaluation dashboard.");
        const summary = data.summary;
        evaluationDashboardStats.innerHTML = [
            ["Tasks", summary.tasks],
            ["Runs", summary.runs],
            ["Success rate", summary.success_rate + "%"],
            ["Average score", summary.average_score + "/100"],
            ["Average latency", summary.average_duration_ms + " ms"],
            ["Needs review", summary.regressions_needing_review],
        ].map(item => "<div><strong>" + item[1] + "</strong><span>" + item[0] + "</span></div>").join("");
        evaluationDashboardModels.innerText = data.models.length
            ? data.models.map(item => item.model_name + " · score " + item.average_score + " · " + item.average_duration_ms + " ms · " + item.completed + "/" + item.runs + " completed").join("\n")
            : "No model runs yet.";
        evaluationDashboardRecent.innerText = data.recent_runs.length
            ? data.recent_runs.map(item => item.created_at.slice(0, 19).replace("T", " ") + " · " + item.task + " · " + item.model_name + " · " + item.status + " · " + (item.score === null ? "unscored" : item.score + "/100")).join("\n")
            : "No evaluation runs yet.";
    } catch (error) {
        evaluationDashboardStats.innerText = "Dashboard error: " + error;
    }
}

function renderEvaluationTasks(tasks) {
    if (!evaluationTaskList) return;
    evaluationTaskList.innerHTML = "";
    if (!tasks.length) {
        evaluationTaskList.innerText = "No evaluation tasks yet. Add your first reusable task above.";
        return;
    }
    tasks.forEach(task => {
        const card = document.createElement("div");
        card.className = "evaluation-task-card";
        const heading = document.createElement("div");
        heading.className = "evaluation-task-heading";
        const title = document.createElement("strong");
        title.innerText = task.name;
        const meta = document.createElement("span");
        meta.innerText = task.language + (task.tags.length ? " · " + task.tags.join(", ") : "");
        heading.append(title, meta);
        const prompt = document.createElement("p");
        prompt.innerText = task.prompt;
        const run = document.createElement("button");
        run.type = "button";
        run.innerText = "Run with selected model";
        run.onclick = () => runEvaluationTask(task);
        const remove = document.createElement("button");
        remove.type = "button";
        remove.innerText = "Delete";
        remove.onclick = () => deleteEvaluationTask(task.id, task.name);
        const actions = document.createElement("div");
        actions.className = "evaluation-task-actions";
        actions.append(run, remove);
        const result = document.createElement("pre");
        result.className = "evaluation-task-result";
        result.id = "evaluation-result-" + task.id;
        result.innerText = "No run yet.";
        card.append(heading, prompt, actions, result);
        evaluationTaskList.appendChild(card);
    });
}

async function runEvaluationTask(task) {
    const output = document.getElementById("evaluation-result-" + task.id);
    output.innerText = "Running " + (modelInput ? modelInput.value : "local model") + "...";
    try {
        const response = await fetch("/api/evaluations/tasks/" + task.id + "/run/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ model: modelInput ? modelInput.value : "" }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || data.run?.response || "Evaluation run failed.");
        output.innerText = data.run.model_name + " · " + data.run.duration_ms + " ms\n\n" + data.run.response;
        loadEvaluationDashboard();
        const scoreButton = document.createElement("button");
        scoreButton.type = "button";
        scoreButton.innerText = "Score response";
        scoreButton.onclick = () => scoreEvaluationRun(data.run.id, output);
        output.parentElement.appendChild(scoreButton);
    } catch (error) {
        output.innerText = "Run error: " + error;
    }
}

async function scoreEvaluationRun(runId, output) {
    try {
        const response = await fetch("/api/evaluations/runs/" + runId + "/score/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ automatic: "true" }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to score response.");
        output.innerText += "\n\nAutomatic score: " + data.score.overall + "/100" +
            "\nCorrectness " + data.score.correctness + " · Relevance " + data.score.relevance +
            " · Completeness " + data.score.completeness + " · Safety " + data.score.safety;
        loadEvaluationDashboard();
    } catch (error) {
        output.innerText += "\n\nScore error: " + error;
    }
}

async function loadEvaluationTasks() {
    if (!evaluationTaskList) return;
    evaluationTaskStatus.innerText = "Loading evaluation tasks...";
    try {
        const response = await fetch("/api/evaluations/tasks/");
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to load evaluation tasks.");
        evaluationTasksCache = data.tasks;
        renderEvaluationTasks(data.tasks);
        evaluationTaskStatus.innerText = data.tasks.length + " reusable task(s) ready.";
        loadEvaluationSuites();
    } catch (error) {
        evaluationTaskStatus.innerText = "Evaluation task error: " + error;
    }
}

async function createEvaluationTask() {
    if (!evaluationTaskName.value.trim() || !evaluationTaskPrompt.value.trim()) {
        evaluationTaskStatus.innerText = "Task name and prompt are required.";
        return;
    }
    try {
        const response = await fetch("/api/evaluations/tasks/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
                name: evaluationTaskName.value.trim(),
                language: evaluationTaskLanguage.value,
                tags: evaluationTaskTags.value,
                prompt: evaluationTaskPrompt.value,
                code: evaluationTaskCode.value,
                expected_output: evaluationTaskExpected.value,
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to create evaluation task.");
        [evaluationTaskName, evaluationTaskTags, evaluationTaskPrompt, evaluationTaskCode, evaluationTaskExpected].forEach(input => input.value = "");
        await loadEvaluationTasks();
    } catch (error) {
        evaluationTaskStatus.innerText = "Evaluation task error: " + error;
    }
}

async function deleteEvaluationTask(taskId, taskName) {
    if (!confirm("Delete evaluation task '" + taskName + "'?")) return;
    try {
        const response = await fetch("/api/evaluations/tasks/" + taskId + "/", {
            method: "DELETE", headers: { "X-CSRFToken": csrfToken },
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to delete evaluation task.");
        await loadEvaluationTasks();
    } catch (error) {
        evaluationTaskStatus.innerText = "Evaluation task error: " + error;
    }
}

function renderEvaluationSuites(suites) {
    if (!evaluationSuiteList) return;
    evaluationSuiteList.innerHTML = "";
    if (!suites.length) {
        evaluationSuiteList.innerText = "No regression suites yet.";
        return;
    }
    suites.forEach(suite => {
        const card = document.createElement("div");
        card.className = "evaluation-task-card";
        const result = suite.last_result && suite.last_result.results
            ? (suite.last_result.passed ? "PASS" : "CHECK") + " · " + suite.last_result.model_name
            : "No baseline run yet.";
        card.innerText = suite.name + " · " + suite.task_ids.length + " task(s) · " + result;
        const button = document.createElement("button");
        button.type = "button";
        button.innerText = "Run regression";
        button.onclick = () => runEvaluationSuite(suite.id);
        card.appendChild(button);
        evaluationSuiteList.appendChild(card);
    });
}

async function loadEvaluationSuites() {
    if (!evaluationSuiteList) return;
    try {
        const response = await fetch("/api/evaluations/regressions/");
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to load regression suites.");
        renderEvaluationSuites(data.suites);
        evaluationSuiteStatus.innerText = data.suites.length + " regression suite(s) ready.";
    } catch (error) {
        evaluationSuiteStatus.innerText = "Regression error: " + error;
    }
}

async function createEvaluationSuite() {
    if (!evaluationSuiteName.value.trim()) {
        evaluationSuiteStatus.innerText = "Enter a regression suite name.";
        return;
    }
    try {
        const response = await fetch("/api/evaluations/regressions/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
                name: evaluationSuiteName.value.trim(),
                description: evaluationSuiteDescription.value,
                task_ids: JSON.stringify(evaluationTasksCache.map(task => task.id)),
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to create regression suite.");
        evaluationSuiteName.value = "";
        evaluationSuiteDescription.value = "";
        await loadEvaluationSuites();
    } catch (error) {
        evaluationSuiteStatus.innerText = "Regression error: " + error;
    }
}

async function runEvaluationSuite(suiteId) {
    evaluationSuiteStatus.innerText = "Running regression suite...";
    try {
        const response = await fetch("/api/evaluations/regressions/" + suiteId + "/run/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ model: modelInput ? modelInput.value : "" }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Regression run failed.");
        const result = data.suite.last_result;
        evaluationSuiteStatus.innerText = (result.passed ? "Regression passed." : "Regression needs review.") +
            " " + result.results.filter(item => item.status === "passed").length + "/" + result.results.length + " task(s) passed.";
        await loadEvaluationSuites();
    } catch (error) {
        evaluationSuiteStatus.innerText = "Regression error: " + error;
    }
}

function toggleWorkspace() {
    if (!workspacePanel) return;
    workspacePanel.hidden = !workspacePanel.hidden;
    if (!workspacePanel.hidden) loadWorkspace();
}

function renderWorkspace(workspace) {
    workspaceSummary.innerText = workspace.name + " · owner " + workspace.owner;
    workspaceMembers.innerText = "Members\n\n" + workspace.members.map(member => member.username + " · " + member.role).join("\n");
    workspaceAudit.innerText = "Recent audit events\n\n" + (workspace.audit.length
        ? workspace.audit.map(event => event.created_at + " · " + event.event_type + " · " + event.actor).join("\n")
        : "No audit events yet.");
}

async function workspaceRequest(values) {
    const response = await fetch("/api/workspace/", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams(values),
    });
    const data = await response.json();
    if (!data.success) throw new Error(data.error || "Workspace action failed.");
    renderWorkspace(data.workspace);
}

async function loadWorkspace() {
    if (!workspaceSummary) return;
    workspaceSummary.innerText = "Loading workspace...";
    try {
        const response = await fetch("/api/workspace/");
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to load workspace.");
        renderWorkspace(data.workspace);
    } catch (error) {
        workspaceSummary.innerText = "Workspace error: " + error;
    }
}

async function createWorkspace() {
    if (!workspaceName.value.trim()) return;
    try {
        await workspaceRequest({ action: "create", name: workspaceName.value.trim() });
        workspaceName.value = "";
    } catch (error) {
        workspaceSummary.innerText = "Workspace error: " + error;
    }
}

async function addWorkspaceMember() {
    if (!workspaceMember.value.trim()) return;
    try {
        await workspaceRequest({ action: "add_member", username: workspaceMember.value.trim(), role: workspaceRole.value });
        workspaceMember.value = "";
    } catch (error) {
        workspaceSummary.innerText = "Workspace error: " + error;
    }
}

function toggleDevops() {
    if (!devopsPanel) return;
    devopsPanel.hidden = !devopsPanel.hidden;
}

async function generateDevopsArtifact() {
    devopsArtifact.innerText = "Generating...";
    try {
        const response = await fetch("/api/devops/generate/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
                kind: devopsKind.value,
                code: codeInput ? codeInput.value : "",
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to generate artifact.");
        devopsArtifact.innerText = data.artifact + "\n\nDeployment checklist:\n- " + data.checklist.join("\n- ");
    } catch (error) {
        devopsArtifact.innerText = "DevOps error: " + error;
    }
}

async function analyzeDevopsLogs() {
    devopsLogOutput.innerText = "Analyzing logs...";
    try {
        const response = await fetch("/api/devops/logs/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ logs: devopsLogs.value }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to analyze logs.");
        devopsLogOutput.innerText = data.summary + "\n\n" +
            (data.findings.length ? data.findings.map(item => item.severity.toUpperCase() + " line " + item.line + ": " + item.message).join("\n") : "No error or warning lines detected.") +
            "\n\nRecommendations:\n- " + (data.recommendations.join("\n- ") || "No extra recommendations.");
    } catch (error) {
        devopsLogOutput.innerText = "Log analysis error: " + error;
    }
}

function toggleDocumentation() {
    if (!documentationPanel) return;
    documentationPanel.hidden = !documentationPanel.hidden;
}

async function generateDocumentation() {
    documentationOutput.innerText = "Generating Markdown...";
    try {
        const response = await fetch("/api/documentation/generate/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
                doc_type: documentationType.value,
                project_name: documentationProjectName.value.trim(),
                change_summary: documentationChangeSummary.value,
                filename: editorFileName ? editorFileName.innerText : "current-code",
                code: codeInput ? codeInput.value : "",
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to generate documentation.");
        documentationOutput.innerText = data.markdown;
    } catch (error) {
        documentationOutput.innerText = "Documentation error: " + error;
    }
}

function toggleReviewGate() {
    if (!reviewGatePanel) return;
    reviewGatePanel.hidden = !reviewGatePanel.hidden;
}

async function runReviewGate() {
    reviewGateSummary.innerText = "Running quality and security checks...";
    try {
        const response = await fetch("/api/review/gate/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
                code: codeInput ? codeInput.value : "",
                filename: editorFileName ? editorFileName.innerText : "editor-buffer",
                language: languageInput ? languageInput.value : "auto",
                diff: reviewDiff.value,
                tests: reviewTests.value,
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Review gate failed.");
        reviewGateSummary.innerText = data.summary + " Score: " + data.score + "/100";
        reviewGateOutput.innerText = data.checks.map(check => (check.passed ? "PASS " : "FAIL ") + check.name + " — " + check.detail).join("\n") +
            "\n\nFindings:\n" + (data.findings.length ? data.findings.map(item => item.severity.toUpperCase() + " " + item.filename + (item.line ? ":" + item.line : "") + " — " + item.message).join("\n") : "No findings.");
    } catch (error) {
        reviewGateSummary.innerText = "Review error: " + error;
    }
}

function toggleDependencies() {
    if (!dependenciesPanel) return;
    dependenciesPanel.hidden = !dependenciesPanel.hidden;
}

async function analyzeDependencies() {
    dependencyOutput.innerText = "Analyzing dependencies...";
    try {
        const response = await fetch("/api/dependencies/analyze/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
                filename: dependencyFilename.value,
                content: dependencyContent.value,
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Dependency analysis failed.");
        dependencyOutput.innerText = data.summary + "\n\n" +
            (data.findings.length ? data.findings.map(item => item.severity.toUpperCase() + " " + item.package + " — " + item.message).join("\n") : "No manifest hygiene findings.") +
            "\n\nUpgrade plan:\n- " + (data.upgrade_plan.join("\n- ") || "No upgrade actions generated.") +
            "\n\n" + data.limitations;
    } catch (error) {
        dependencyOutput.innerText = "Dependency error: " + error;
    }
}

function toggleBrowserTests() {
    if (!browserTestsPanel) return;
    browserTestsPanel.hidden = !browserTestsPanel.hidden;
}

async function generateBrowserTest() {
    browserTestOutput.innerText = "Generating Playwright test...";
    try {
        const response = await fetch("/api/browser-tests/generate/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
                base_url: browserBaseUrl.value,
                snapshot_name: browserSnapshotName.value,
                flow: browserFlow.value,
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Browser test generation failed.");
        browserTestOutput.innerText = data.test_code + "\n\nRun:\n" + data.command;
    } catch (error) {
        browserTestOutput.innerText = "Browser test error: " + error;
    }
}

async function analyzeBrowserReport() {
    browserReportOutput.innerText = "Analyzing browser report...";
    try {
        const response = await fetch("/api/browser-tests/report/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ report: browserReport.value }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Browser report analysis failed.");
        browserReportOutput.innerText = data.summary + "\n\n" +
            (data.failed.length ? "Failures:\n" + data.failed.join("\n") : "No failures detected.") +
            "\n\nNext steps:\n- " + data.next_steps.join("\n- ");
    } catch (error) {
        browserReportOutput.innerText = "Browser report error: " + error;
    }
}

function toggleModelRouter() {
    if (!modelRouterPanel) return;
    modelRouterPanel.hidden = !modelRouterPanel.hidden;
}

async function routeLocalModel() {
    routerOutput.innerText = "Selecting local model...";
    const models = modelInput ? Array.from(modelInput.options).map(option => option.value) : [];
    try {
        const response = await fetch("/api/models/route/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
                task: routerTask.value,
                memory_gb: routerMemory.value || "0",
                gpu: routerGpu.checked ? "true" : "false",
                models_json: JSON.stringify(models),
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Model routing failed.");
        if (modelInput) {
            modelInput.value = data.selected_model;
            updateActiveModel();
        }
        routerOutput.innerText = "Recommended: " + data.selected_model + "\nReason: " + data.reason +
            "\n\nCandidates:\n" + data.candidates.map(item => item.model + " (" + item.score + ") — " + item.reasons.join(", ")).join("\n");
    } catch (error) {
        routerOutput.innerText = "Router error: " + error;
    }
}

function toggleDevcontainer() {
    if (!devcontainerPanel) return;
    devcontainerPanel.hidden = !devcontainerPanel.hidden;
}

async function generateDevcontainer() {
    devcontainerOutput.innerText = "Generating devcontainer.json...";
    try {
        const response = await fetch("/api/devcontainers/generate/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
                project_name: devcontainerProjectName.value.trim(),
                filename: editorFileName ? editorFileName.innerText : "",
                code: codeInput ? codeInput.value : "",
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Dev Container generation failed.");
        devcontainerOutput.innerText = data.path + "\n\n" + data.config + "\n\nNotes:\n- " + data.notes.join("\n- ");
    } catch (error) {
        devcontainerOutput.innerText = "Environment error: " + error;
    }
}

function toggleIncident() {
    if (!incidentPanel) return;
    incidentPanel.hidden = !incidentPanel.hidden;
}

async function analyzeIncident() {
    incidentOutput.innerText = "Correlating incident signals...";
    try {
        const response = await fetch("/api/incidents/analyze/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
                logs: incidentLogs.value,
                traces: incidentTraces.value,
                metrics: incidentMetrics.value,
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Incident analysis failed.");
        incidentOutput.innerText = data.summary + "\n\nSuspected causes:\n- " + data.suspected_causes.join("\n- ") +
            "\n\nActions:\n- " + data.recommended_actions.join("\n- ") +
            "\n\nPostmortem draft:\n" + data.postmortem;
    } catch (error) {
        incidentOutput.innerText = "Incident error: " + error;
    }
}

function toggleArchitecture() {
    if (!architecturePanel) return;
    architecturePanel.hidden = !architecturePanel.hidden;
}

async function analyzeCrossRepositories() {
    crossRepositoryOutput.innerText = "Building cross-repository impact graph...";
    try {
        const response = await fetch("/api/architecture/cross-repo/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ repositories_json: crossRepositoryFiles.value }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Cross-repository analysis failed.");
        const newline = String.fromCharCode(10);
        crossRepositoryOutput.innerText = data.summary + newline + data.warnings.join(newline) +
            newline + newline + "Impacts:" + newline +
            (data.impacts.length ? data.impacts.map(item => item.repository + " · " + item.risk + " · in " + item.incoming_dependencies + " / out " + item.outgoing_dependencies).join(newline) : "No impact data.") +
            newline + newline + "Cross-repository edges:" + newline +
            (data.cross_edges.length ? data.cross_edges.map(edge => edge.from + " -> " + edge.to).join(newline) : "None");
    } catch (error) {
        crossRepositoryOutput.innerText = "Cross-repository error: " + error;
    }
}

async function analyzeArchitecture() {
    architectureOutput.innerText = "Building architecture graph...";
    try {
        const response = await fetch("/api/architecture/analyze/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ files_json: architectureFiles.value }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Architecture analysis failed.");
        architectureOutput.innerText = data.summary + "\n" + data.warnings.join("\n") +
            "\n\nRelationships:\n" + (data.edges.length ? data.edges.map(edge => edge.from + " -> " + edge.to).join("\n") : "No local relationships detected.") +
            "\n\nRoutes:\n" + (data.routes.length ? data.routes.map(route => route.file + " " + route.route).join("\n") : "No routes detected.") +
            "\n\nCycles:\n" + (data.cycles.length ? data.cycles.map(cycle => cycle.join(" -> ")).join("\n") : "None");
    } catch (error) {
        architectureOutput.innerText = "Architecture error: " + error;
    }
}

function toggleContracts() {
    if (!contractsPanel) return;
    contractsPanel.hidden = !contractsPanel.hidden;
}

async function analyzeContracts() {
    contractOutput.innerText = "Checking API contract...";
    try {
        const response = await fetch("/api/contracts/analyze/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ spec: contractSpec.value, code: contractCode.value }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "API contract analysis failed.");
        contractOutput.innerText = data.summary +
            "\n\nUndocumented:\n" + (data.undocumented.length ? data.undocumented.map(item => item.method + " " + item.path).join("\n") : "None") +
            "\n\nStale documentation:\n" + (data.stale_documentation.length ? data.stale_documentation.map(item => item.method + " " + item.path).join("\n") : "None") +
            "\n\nBreaking risks:\n" + (data.breaking_risks.join("\n- ") || "None") +
            "\n\nSuggested OpenAPI:\n" + data.suggested_openapi;
    } catch (error) {
        contractOutput.innerText = "Contract error: " + error;
    }
}

function toggleProvenance() {
    if (!provenancePanel) return;
    provenancePanel.hidden = !provenancePanel.hidden;
}

async function generateProvenance() {
    provenanceStatus.innerText = "Generating artifact provenance...";
    try {
        const response = await fetch("/api/provenance/generate/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
                artifact_name: provenanceArtifact.value,
                commit: provenanceCommit.value || "unknown",
                files_json: provenanceFiles.value || "[]",
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Provenance generation failed.");
        provenanceOutput.value = data.provenance;
        provenanceStatus.innerText = "Provenance generated.";
    } catch (error) {
        provenanceStatus.innerText = "Provenance error: " + error;
    }
}

async function verifyProvenance() {
    provenanceStatus.innerText = "Verifying provenance...";
    try {
        const response = await fetch("/api/provenance/verify/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ provenance: provenanceOutput.value }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Provenance verification failed.");
        provenanceStatus.innerText = (data.valid ? "Valid provenance." : "Invalid provenance.") + " " +
            data.checks.map(check => (check.passed ? "PASS " : "FAIL ") + check.name).join(" · ");
    } catch (error) {
        provenanceStatus.innerText = "Verification error: " + error;
    }
}

function toggleIdentityPolicy() {
    if (!identityPolicyPanel) return;
    identityPolicyPanel.hidden = !identityPolicyPanel.hidden;
    if (!identityPolicyPanel.hidden) {
        loadIdentityPolicy();
        loadEnterpriseIdentity();
    }
}

function renderIdentityPolicy(data) {
    identitySummary.innerText = data.identity.username + " · " + data.identity.role + " · " + data.workspace + " · " + data.identity.authentication;
    const policy = data.policy;
    policyGit.checked = policy.require_approval_for_git;
    policyTools.checked = policy.require_approval_for_tools;
    policyDeploy.checked = policy.require_approval_for_deploy;
    policyTests.checked = policy.require_tests;
    policyExternal.checked = policy.allow_external_connectors;
    policyRetention.value = policy.audit_retention_days;
}

async function loadIdentityPolicy() {
    identityPolicyStatus.innerText = "Loading policy...";
    try {
        const response = await fetch("/api/identity/policy/");
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to load policy.");
        renderIdentityPolicy(data);
        identityPolicyStatus.innerText = "Policy loaded.";
    } catch (error) {
        identityPolicyStatus.innerText = "Policy error: " + error;
    }
}

async function saveIdentityPolicy() {
    identityPolicyStatus.innerText = "Saving policy...";
    try {
        const response = await fetch("/api/identity/policy/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
                require_approval_for_git: policyGit.checked,
                require_approval_for_tools: policyTools.checked,
                require_approval_for_deploy: policyDeploy.checked,
                require_tests: policyTests.checked,
                allow_external_connectors: policyExternal.checked,
                audit_retention_days: policyRetention.value,
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to save policy.");
        renderIdentityPolicy(data);
        identityPolicyStatus.innerText = "Policy saved and added to the audit log.";
    } catch (error) {
        identityPolicyStatus.innerText = "Policy error: " + error;
    }
}

function renderEnterpriseIdentity(config) {
    if (!config) return;
    enterpriseProvider.value = config.provider || "oidc";
    enterpriseIssuer.value = config.issuer_url || "";
    enterpriseSamlEntrypoint.value = config.saml_entrypoint_url || "";
    enterpriseClientId.value = config.client_id || "";
    enterpriseDomains.value = config.allowed_domains || "";
    enterpriseEnforce.checked = Boolean(config.enforce_sso);
    enterpriseScim.checked = Boolean(config.scim_enabled);
    enterpriseIdentityStatus.innerText = (config.token_configured ? "SCIM token configured." : "SCIM token not configured.") +
        (config.updated_at ? " Updated " + config.updated_at + "." : "");
}

async function loadEnterpriseIdentity() {
    enterpriseIdentityStatus.innerText = "Loading enterprise identity...";
    try {
        const response = await fetch("/api/identity/enterprise/");
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to load enterprise identity.");
        renderEnterpriseIdentity(data.identity_config);
    } catch (error) {
        enterpriseIdentityStatus.innerText = "Enterprise identity error: " + error;
    }
}

async function saveEnterpriseIdentity(rotateToken) {
    enterpriseIdentityStatus.innerText = rotateToken ? "Rotating SCIM token..." : "Saving enterprise identity...";
    enterpriseScimToken.hidden = true;
    try {
        const response = await fetch("/api/identity/enterprise/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
                provider: enterpriseProvider.value,
                issuer_url: enterpriseIssuer.value,
                saml_entrypoint_url: enterpriseSamlEntrypoint.value,
                client_id: enterpriseClientId.value,
                allowed_domains: enterpriseDomains.value,
                enforce_sso: enterpriseEnforce.checked,
                scim_enabled: enterpriseScim.checked,
                action: rotateToken ? "rotate_scim_token" : "",
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to save enterprise identity.");
        renderEnterpriseIdentity(data.identity_config);
        if (data.scim_token) {
            enterpriseScimToken.hidden = false;
            enterpriseScimToken.innerText = "SCIM token (copy it now; it is shown only once): " + data.scim_token;
            enterpriseIdentityStatus.innerText = "Enterprise settings saved and a new SCIM token was generated.";
        } else {
            enterpriseIdentityStatus.innerText = "Enterprise settings saved.";
        }
    } catch (error) {
        enterpriseIdentityStatus.innerText = "Enterprise identity error: " + error;
    }
}

function toggleSecretsVault() {
    if (!secretsPanel) return;
    secretsPanel.hidden = !secretsPanel.hidden;
    if (!secretsPanel.hidden) loadSecrets();
}

function renderSecrets(items) {
    secretsList.innerHTML = "";
    if (!items.length) {
        secretsList.innerText = "No workspace secrets yet.";
        return;
    }
    items.forEach(item => {
        const row = document.createElement("div");
        row.className = "secret-row";
        const label = document.createElement("span");
        label.innerText = item.name + " · version " + item.version + " · masked";
        const reveal = document.createElement("button");
        reveal.type = "button";
        reveal.innerText = "Reveal";
        reveal.onclick = () => revealSecret(item.id, item.name);
        const remove = document.createElement("button");
        remove.type = "button";
        remove.innerText = "Delete";
        remove.onclick = () => deleteSecret(item.id);
        row.append(label, reveal, remove);
        secretsList.append(row);
    });
}

async function loadSecrets() {
    secretsStatus.innerText = "Loading encrypted secrets...";
    try {
        const response = await fetch("/api/secrets/");
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to load secrets.");
        renderSecrets(data.secrets);
        secretsStatus.innerText = data.secrets.length + " masked workspace secret(s).";
    } catch (error) {
        secretsStatus.innerText = "Secrets error: " + error;
    }
}

async function saveSecret() {
    secretsStatus.innerText = "Encrypting and saving secret...";
    try {
        const response = await fetch("/api/secrets/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ name: secretName.value, value: secretValue.value, description: secretDescription.value }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to save secret.");
        secretValue.value = "";
        await loadSecrets();
        secretsStatus.innerText = "Secret encrypted and saved.";
    } catch (error) {
        secretsStatus.innerText = "Secrets error: " + error;
    }
}

async function revealSecret(id, name) {
    secretRevealOutput.hidden = true;
    try {
        const response = await fetch("/api/secrets/" + id + "/reveal/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken },
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to reveal secret.");
        secretRevealOutput.hidden = false;
        secretRevealOutput.innerText = name + ": " + data.value + "\n\n" + data.warning;
    } catch (error) {
        secretsStatus.innerText = "Reveal error: " + error;
    }
}

async function deleteSecret(id) {
    if (!confirm("Delete this workspace secret?")) return;
    const response = await fetch("/api/secrets/" + id + "/", { method: "DELETE", headers: { "X-CSRFToken": csrfToken } });
    const data = await response.json();
    if (!data.success) {
        secretsStatus.innerText = "Delete error: " + (data.error || "Unable to delete secret.");
        return;
    }
    secretRevealOutput.hidden = true;
    loadSecrets();
}

function renderMcpConnectors(connectors) {
    if (!mcpConnectorList) return;
    mcpConnectorList.innerHTML = "";
    if (!connectors.length) {
        mcpConnectorList.innerText = "No custom connectors yet.";
        return;
    }
    connectors.forEach(connector => {
        const row = document.createElement("div");
        row.className = "mcp-connector";
        const label = document.createElement("span");
        label.innerText = connector.name + " · " + connector.connector_type + (connector.allow_write ? " · write enabled" : " · read only");
        const remove = document.createElement("button");
        remove.type = "button";
        remove.innerText = "Remove";
        remove.onclick = () => deleteMcpConnector(connector.id);
        row.append(label, remove);
        mcpConnectorList.appendChild(row);
    });
}

async function loadMcpConnectors() {
    try {
        const response = await fetch("/api/mcp/connectors/");
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to load MCP connectors.");
        renderMcpConnectors(data.connectors);
        mcpOutput.innerText = "Available tools:\n" + data.tools.map(tool => tool.name + (tool.write ? " [write approval]" : " [read-only]")).join("\n");
    } catch (error) {
        mcpOutput.innerText = String(error);
    }
}

async function saveMcpConnector() {
    try {
        const response = await fetch("/api/mcp/connectors/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams({
                name: mcpConnectorName.value.trim(),
                connector_type: mcpConnectorType.value,
                config: mcpConnectorConfig.value.trim() || "{}",
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to save connector.");
        mcpConnectorName.value = "";
        mcpConnectorConfig.value = "";
        await loadMcpConnectors();
    } catch (error) {
        mcpOutput.innerText = String(error);
    }
}

async function deleteMcpConnector(id) {
    try {
        await fetch("/api/mcp/connectors/" + id + "/", {
            method: "DELETE",
            headers: { "X-CSRFToken": csrfToken },
        });
        await loadMcpConnectors();
    } catch (error) {
        mcpOutput.innerText = String(error);
    }
}

async function callMcpSearch() {
    try {
        const response = await fetch("/api/mcp/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                id: Date.now(),
                method: "tools/call",
                params: { name: "project.search", arguments: { query: mcpSearchQuery.value.trim() } },
            }),
        });
        const data = await response.json();
        if (data.error) throw new Error(data.error.message);
        mcpOutput.innerText = JSON.stringify(data.result, null, 2);
    } catch (error) {
        mcpOutput.innerText = String(error);
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
async function loadSandboxPolicy() {
    if (!sandboxPolicyStatus) return;
    try {
        const response = await fetch("/api/sandbox/policy/");
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to load sandbox policy.");
        sandboxTimeout.value = data.policy.timeout_seconds;
        sandboxMemory.value = data.policy.memory_mb;
        sandboxOutputChars.value = data.policy.output_chars;
        sandboxApproval.checked = data.policy.require_approval;
        sandboxPolicyStatus.innerText = "Network blocked · policy ready.";
    } catch (error) {
        sandboxPolicyStatus.innerText = "Policy error: " + error;
    }
}

async function saveSandboxPolicy() {
    try {
        const response = await fetch("/api/sandbox/policy/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
                timeout_seconds: sandboxTimeout.value,
                memory_mb: sandboxMemory.value,
                output_chars: sandboxOutputChars.value,
                require_approval: sandboxApproval.checked ? "true" : "false",
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to save sandbox policy.");
        sandboxPolicyStatus.innerText = "Saved · network remains blocked.";
    } catch (error) {
        sandboxPolicyStatus.innerText = "Policy error: " + error;
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

async function scanSecurity() {
    const code = codeInput.value.trim();
    const output = document.getElementById("securityOutput");
    if (!code) {
        alert("Paste code before scanning it.");
        return;
    }
    output.innerText = "Scanning locally...";
    try {
        const response = await fetch("/api/security/scan/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams({
                code,
                filename: editorFileName ? editorFileName.innerText : "editor-buffer",
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Security scan failed.");
        const lines = [
            data.summary,
            "",
            ...data.findings.map(item => "[" + item.severity.toUpperCase() + "] " + item.rule + " " + item.filename + (item.line ? ":" + item.line : "") + " - " + item.message),
            "",
            "Dependencies: " + data.dependencies.length,
            "Licenses: " + data.licenses.map(item => item.filename + "=" + item.license).join(", "),
            data.limitations,
            "",
            "SBOM:",
            JSON.stringify(data.sbom, null, 2),
        ];
        output.innerText = lines.join("\n");
    } catch (error) {
        output.innerText = "Security scan error: " + error;
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

function renderAgentTask(task) {
    if (!agentPlan) return;
    agentTaskId = task.id;
    agentStatus.innerText = task.status.toUpperCase() + " | " + task.progress + "/" + task.total_steps + " steps | " + task.result;
    if (agentLogs) agentLogs.innerText = (task.logs || []).map(log => "[" + log.level + "] " + log.message).join("\n") || "Agent logs will appear here.";
    agentPlan.innerHTML = "";
    task.plan.forEach((step, index) => {
        const row = document.createElement("div");
        row.className = "agent-step" + (step.completed ? " completed" : "");
        const details = document.createElement("div");
        details.className = "agent-step-details";
        const title = document.createElement("strong");
        title.innerText = (index + 1) + ". " + step.title;
        const description = document.createElement("span");
        description.innerText = step.description + (step.requires_approval ? " Approval required." : "");
        details.append(title, description);
        const actions = document.createElement("div");
        actions.className = "agent-step-actions";
        if (step.requires_approval && !step.approved && !step.completed) {
            const approve = document.createElement("button");
            approve.type = "button";
            approve.innerText = "Approve";
            approve.onclick = () => updateAgentStep(index, "approve");
            actions.appendChild(approve);
        }
        if (!step.completed) {
            const complete = document.createElement("button");
            complete.type = "button";
            complete.innerText = step.requires_approval ? "Complete" : "Mark done";
            complete.disabled = step.requires_approval && !step.approved;
            complete.onclick = () => updateAgentStep(index, "complete");
            actions.appendChild(complete);
        }
        if (!step.completed && (step.approved || !step.requires_approval)) {
            const reject = document.createElement("button");
            reject.type = "button";
            reject.innerText = "Reject";
            reject.onclick = () => updateAgentStep(index, "reject");
            actions.appendChild(reject);
        }
        row.append(details, actions);
        agentPlan.appendChild(row);
    });
}

async function createAgentPlan() {
    const goal = agentGoal ? agentGoal.value.trim() : "";
    if (!goal) {
        alert("Describe the task for the agent.");
        return;
    }
    agentStatus.innerText = "Creating plan...";
    try {
        const response = await fetch("/api/agent/plan/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams({ goal }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to create agent plan.");
        renderAgentTask(data.task);
    } catch (error) {
        agentStatus.innerText = "Agent error: " + error;
    }
}

async function updateAgentStep(step, action) {
    if (!agentTaskId) return;
    try {
        const response = await fetch("/api/agent/task/" + agentTaskId + "/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams({ step, action }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Agent action failed.");
        renderAgentTask(data.task);
    } catch (error) {
        agentStatus.innerText = "Agent error: " + error;
    }
}

async function runAgentTask() {
    if (!agentTaskId) return;
    try {
        const response = await fetch("/api/agent/task/" + agentTaskId + "/run/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
                code: codeInput.value,
                test_code: document.getElementById("testInput") ? document.getElementById("testInput").value : "",
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Agent run failed.");
        renderAgentTask(data.task);
    } catch (error) {
        agentStatus.innerText = "Agent error: " + error;
    }
}

async function queueAgentJob() {
    if (!agentTaskId) {
        agentJobStatus.innerText = "Create an approved agent plan first.";
        return;
    }
    try {
        const response = await fetch("/api/agent/jobs/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
                task_id: agentTaskId,
                code: codeInput.value,
                test_code: document.getElementById("testInput") ? document.getElementById("testInput").value : "",
            }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to queue background job.");
        agentJobId = data.job.id;
        agentJobStatus.innerText = "QUEUED job #" + agentJobId + " · ready for worker run.";
        await runAgentJob();
    } catch (error) {
        agentJobStatus.innerText = "Job error: " + error;
    }
}

async function runAgentJob() {
    if (!agentJobId) return;
    const response = await fetch("/api/agent/job/" + agentJobId + "/run/", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken },
    });
    const data = await response.json();
    if (!data.success && !data.job) {
        agentJobStatus.innerText = "Job error: " + (data.error || "Worker failed.");
        return;
    }
    agentJobStatus.innerText = data.job.status.toUpperCase() + " job #" + agentJobId + " · attempt " + data.job.attempts;
}

async function controlAgentTask(action) {
    if (!agentTaskId) return;
    try {
        const response = await fetch("/api/agent/task/" + agentTaskId + "/control/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ action }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Agent control failed.");
        renderAgentTask(data.task);
    } catch (error) {
        agentStatus.innerText = "Agent error: " + error;
    }
}

function renderAgentTeam(team) {
    agentTeamId = team.id;
    agentTeamStatus.innerText = team.status.toUpperCase() + " | " + team.progress + "/" + team.total_members + " roles | " + team.title;
    agentTeamLogs.innerText = (team.logs || []).map(log => "[" + log.level + "] " + log.message).join(String.fromCharCode(10)) || "Team logs will appear here.";
}

async function createAgentTeam() {
    const goal = agentGoal ? agentGoal.value.trim() : "";
    if (!goal) {
        alert("Describe the team goal in the agent goal field.");
        return;
    }
    try {
        const roles = agentTeamRoles.value.split(",").map(role => role.trim()).filter(Boolean);
        const response = await fetch("/api/agent/teams/", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ goal, roles: JSON.stringify(roles) }),
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Unable to create agent team.");
        renderAgentTeam(data.team);
    } catch (error) {
        agentTeamStatus.innerText = "Team error: " + error;
    }
}

async function runAgentTeam() {
    if (!agentTeamId) return;
    const response = await fetch("/api/agent/team/" + agentTeamId + "/run/", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken },
    });
    const data = await response.json();
    if (!data.success) {
        agentTeamStatus.innerText = "Team error: " + (data.error || "Unable to run team.");
        return;
    }
    renderAgentTeam(data.team);
}

async function controlAgentTeam(action) {
    if (!agentTeamId) return;
    const response = await fetch("/api/agent/team/" + agentTeamId + "/control/", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ action }),
    });
    const data = await response.json();
    if (!data.success) {
        agentTeamStatus.innerText = "Team error: " + (data.error || "Team action failed.");
        return;
    }
    renderAgentTeam(data.team);
}

function resetAgentTask() {
    if (agentTaskId) updateAgentStep(0, "undo");
    else if (agentPlan) agentPlan.innerHTML = "";
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
if (sandboxPolicyStatus) loadSandboxPolicy();
