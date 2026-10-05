import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from requests.exceptions import ConnectionError as RequestsConnectionError
from unittest.mock import patch

from .models import AgentJob, AgentTask, AgentTeam, AiEvent, AuditEvent, ChatMessage, ChatSession, EnterpriseIdentityConfig, EvaluationRun, EvaluationScore, EvaluationTask, ExtensionInstall, ExtensionPackage, KnowledgeChunk, KnowledgeDocument, SandboxPolicy, SecretVaultItem, Workspace, WorkspaceMembership, WorkspacePolicy
from .views import _search_knowledge


class ChatFeatureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="safe-password-123")
        self.client.login(username="tester", password="safe-password-123")

    def test_home_is_available_to_guests(self):
        self.client.logout()
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "FREE PREVIEW")

    def test_lsp_adapter_catalog_reports_local_fallback_and_servers(self):
        response = self.client.get("/api/coding/lsp/adapters/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["fallback"], "local-ast-regex")
        self.assertTrue(any(item["id"] == "pyright" for item in payload["adapters"]))
        self.assertEqual(payload["network_policy"], "blocked")

    def test_repository_instructions_discover_scoped_skills(self):
        response = self.client.post("/api/coding/repository-instructions/", {
            "files": json.dumps([
                {"filename": "AGENTS.md", "content": "# Repository rules\nUse tests."},
                {"filename": ".github/instructions/python.instructions.md", "content": "# Python rules"},
                {"filename": ".github/skills/release/SKILL.md", "content": "# Release skill"},
            ]),
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["always_on"]), 1)
        self.assertEqual(len(payload["path_specific"]), 1)
        self.assertEqual(len(payload["skills"]), 1)

    def test_test_impact_selects_tests_referencing_changed_symbols(self):
        response = self.client.post("/api/coding/test-impact/", {
            "files": json.dumps([
                {"filename": "src/math.py", "content": "def add(left, right):\n    return left + right\n"},
                {"filename": "tests/test_math.py", "content": "from src.math import add\ndef test_add():\n    assert add(1, 2) == 3\n"},
                {"filename": "tests/test_other.py", "content": "def test_other():\n    assert True\n"},
            ]),
            "changed_files": json.dumps(["src/math.py"]),
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["changed_symbols"], ["add"])
        self.assertEqual(payload["impacted_tests"][0]["filename"], "tests/test_math.py")
        self.assertEqual(payload["skipped_tests"][0]["filename"], "tests/test_other.py")

    def test_git_bisect_assistant_generates_safe_reproduction_plan(self):
        response = self.client.post("/api/coding/git-bisect/", {
            "failing_test": "python -m pytest tests/test_api.py -q",
            "known_good": "abc123",
            "known_bad": "def456",
            "commits": json.dumps(["abc123", "mid456", "def456"]),
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("git bisect run python -m pytest tests/test_api.py -q", payload["commands"])
        self.assertFalse(payload["destructive"])
        self.assertTrue(payload["approval_required"])

    def test_incident_debugger_extracts_frame_and_creates_fix_workflow(self):
        response = self.client.post("/api/coding/incident-debug/", {
            "title": "Checkout failure",
            "logs": "ERROR database connection timeout",
            "traces": "File \"checkout.py\", line 42, in submit",
            "metrics": "latency=9000ms",
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["locations"][0]["filename"], "checkout.py")
        self.assertTrue(payload["requires_regression_test"])
        self.assertEqual(payload["fix_workflow"]["isolation"], "agent-worktree")

    def test_migration_safety_flags_dropped_table_and_required_column(self):
        response = self.client.post("/api/coding/migration-safety/", {
            "old_schema": json.dumps({"tables": {"users": {"columns": {"id": {}}}, "legacy": {"columns": {"id": {}}}}}),
            "new_schema": json.dumps({"tables": {"users": {"columns": {"id": {}, "email": {"required": True}}}}}),
            "migration_sql": "DROP TABLE legacy;",
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["safe"])
        self.assertTrue(any(item["kind"] == "drop-table" for item in payload["findings"]))
        self.assertFalse(payload["dry_run"]["executed"])

    def test_local_lsp_returns_symbols_diagnostics_and_references(self):
        response = self.client.post("/api/coding/lsp/", {
            "filename": "app.py",
            "content": "def add(left, right):\n    return left + right\n\nadd(1, 2)\n",
            "operation": "all",
            "symbol": "add",
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["backend"], "local-ast-regex")
        self.assertEqual(payload["definitions"][0]["name"], "add")
        self.assertGreaterEqual(len(payload["references"]), 2)

    def test_ast_safe_refactor_previews_multi_file_rename(self):
        response = self.client.post("/api/coding/refactor/", {
            "old_name": "old_name",
            "new_name": "new_name",
            "files": json.dumps([
                {"filename": "one.py", "content": "def old_name():\n    return old_name\n"},
                {"filename": "two.py", "content": "from one import old_name\n"},
            ]),
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["files_changed"], 2)
        self.assertTrue(payload["approval_required"])

    def test_issue_to_pr_creates_approval_gated_agent_workflow(self):
        response = self.client.post("/api/coding/issue-to-pr/", {
            "title": "Add health endpoint",
            "description": "Create a local health endpoint and cover it with tests.",
            "files": json.dumps(["chat/views.py", "chat/tests.py"]),
            "test_command": "python manage.py test chat",
        })
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["workflow"]["isolation"], "agent-worktree")
        self.assertEqual(len(payload["workflow"]["workflow"]), 6)
        self.assertTrue(all(step["approval_required"] for step in payload["workflow"]["workflow"][1:]))

    def test_pr_review_returns_line_aware_gate_and_fingerprint(self):
        response = self.client.post("/api/coding/pr-review/", {
            "files": json.dumps([{"filename": "app.py", "content": "def run():\n    return eval(user_input)\n"}]),
            "diff": "@@ -0,0 +1,2 @@\n+def run():\n+    return eval(user_input)\n",
            "tests": "python -m pytest",
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["ready"])
        self.assertEqual(len(payload["review_fingerprint"]), 16)
        self.assertTrue(payload["rerun_required_after_push"])

    def test_local_ci_detects_project_commands_and_requires_approval(self):
        response = self.client.post("/api/coding/local-ci/", {
            "files": json.dumps([
                {"filename": "manage.py", "content": ""},
                {"filename": "requirements.txt", "content": "Django==5.0"},
            ]),
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["runner"], "offline-local-ci")
        self.assertTrue(any(item["id"] == "python-tests" for item in payload["commands"]))
        self.assertTrue(payload["approval_required"])

    def test_security_sbom_returns_sarif_and_imported_advisory_matches(self):
        response = self.client.post("/api/coding/security-sbom/", {
            "files": json.dumps([{"filename": "requirements.txt", "content": "demo==1.0"}]),
            "advisory_snapshot": json.dumps({"demo@1.0": [{"id": "LOCAL-001", "severity": "high"}]}),
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["sarif"]["version"], "2.1.0")
        self.assertEqual(payload["advisory_matches"][0]["advisories"][0]["id"], "LOCAL-001")
        self.assertTrue(payload["offline_only"])

    def test_browser_debug_returns_local_repair_loop_and_playwright_test(self):
        response = self.client.post("/api/coding/browser-debug/", {
            "base_url": "http://127.0.0.1:8000",
            "flow": "Open dashboard and verify title",
            "report": "1 failed screenshot comparison",
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["runner"], "local-playwright")
        self.assertIn("@playwright/test", payload["test_code"])
        self.assertTrue(payload["approval_required_for_patch"])

    def test_api_evolution_detects_removed_and_new_required_parameters(self):
        old_spec = {"paths": {"/users": {"get": {}}, "/legacy": {"get": {}}}}
        new_spec = {"paths": {"/users": {"get": {"parameters": [{"name": "org", "in": "query", "required": True}]}}, "/new": {"post": {}}}}
        response = self.client.post("/api/coding/api-evolution/", {
            "old_spec": json.dumps(old_spec),
            "new_spec": json.dumps(new_spec),
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["safe_to_release"])
        self.assertEqual(len(payload["removed"]), 1)
        self.assertEqual(payload["changed"][0]["new_required_parameters"], ["org"])

    def test_performance_profiler_reports_hotspots_and_benchmark_delta(self):
        response = self.client.post("/api/coding/performance/", {
            "files": json.dumps([{"filename": "slow.py", "content": "for item in items:\n    for child in item:\n        save(child)\n"}]),
            "benchmark": json.dumps([{"phase": "before", "duration_ms": 100}, {"phase": "after", "duration_ms": 80}]),
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["benchmark"]["delta_percent"], -20.0)
        self.assertEqual(payload["hotspots"][0]["filename"], "slow.py")
        self.assertTrue(payload["patch_approval_required"])

    def test_monorepo_orchestrator_selects_only_affected_packages(self):
        response = self.client.post("/api/coding/monorepo/", {
            "files": json.dumps([
                {"filename": "packages/ui/package.json", "content": json.dumps({"name": "ui", "scripts": {"test": "vitest"}})},
                {"filename": "packages/api/package.json", "content": json.dumps({"name": "api", "scripts": {"test": "pytest"}})},
            ]),
            "changed_files": json.dumps(["packages/ui/src/button.tsx"]),
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["affected_packages"], ["ui"])
        self.assertTrue(all(task["package"] == "ui" for task in payload["tasks"]))
        self.assertTrue(payload["approval_required"])

    def test_multi_agent_team_creates_roles_and_advances_checkpoints(self):
        created = self.client.post("/api/agent/teams/", {
            "goal": "Prepare a safe release",
            "roles": '["planner", "tester"]',
        })
        self.assertEqual(created.status_code, 201)
        team = created.json()["team"]
        self.assertEqual(team["total_members"], 2)
        self.assertEqual(AgentTeam.objects.get(id=team["id"]).roles, ["planner", "tester"])
        started = self.client.post(f"/api/agent/team/{team['id']}/run/")
        self.assertEqual(started.json()["team"]["status"], "running")
        advanced = self.client.post(f"/api/agent/team/{team['id']}/control/", {"action": "advance"})
        self.assertEqual(advanced.json()["team"]["progress"], 1)

    def test_secure_runtime_policy_is_bounded_and_network_stays_blocked(self):
        saved = self.client.post("/api/sandbox/policy/", {
            "timeout_seconds": "99",
            "memory_mb": "999",
            "output_chars": "999999",
            "require_approval": "false",
        })
        self.assertTrue(saved.json()["success"])
        self.assertEqual(saved.json()["policy"]["timeout_seconds"], 10)
        self.assertEqual(saved.json()["policy"]["memory_mb"], 256)
        self.assertTrue(saved.json()["policy"]["network_blocked"])
        self.assertTrue(SandboxPolicy.objects.get(user=self.user).network_blocked)
        executed = self.client.post("/api/execute/", {"language": "python", "code": "print('safe')"})
        self.assertTrue(executed.json()["success"])
        self.assertEqual(executed.json()["limits"]["timeout_seconds"], 10)

    def test_durable_agent_job_checkpoints_and_can_retry(self):
        task = self.client.post("/api/agent/plan/", {"goal": "Run a safe background check"}).json()["task"]
        queued = self.client.post("/api/agent/jobs/", {
            "task_id": task["id"],
            "code": "def add(a, b):\n    return a + b",
            "test_code": "assert add(2, 3) == 5",
        })
        self.assertEqual(queued.status_code, 201)
        job_id = queued.json()["job"]["id"]
        completed = self.client.post(f"/api/agent/job/{job_id}/run/")
        self.assertTrue(completed.json()["success"])
        self.assertEqual(completed.json()["job"]["status"], "completed")
        self.assertEqual(AgentJob.objects.get(id=job_id).checkpoint["stage"], "completed")
        paused = self.client.post(f"/api/agent/job/{job_id}/control/", {"action": "retry"})
        self.assertEqual(paused.json()["job"]["status"], "queued")

    def test_evaluation_tasks_can_be_created_listed_and_deleted(self):
        created = self.client.post("/api/evaluations/tasks/", {
            "name": "Fix add function",
            "prompt": "Find and fix the bug.",
            "code": "def add(a, b): return a - b",
            "expected_output": "The function should add values.",
            "language": "python",
            "tags": "python, bug-fix",
        })
        self.assertEqual(created.status_code, 201)
        task = created.json()["task"]
        self.assertEqual(task["tags"], ["python", "bug-fix"])
        listing = self.client.get("/api/evaluations/tasks/?q=add")
        self.assertEqual(listing.json()["tasks"][0]["id"], task["id"])
        deleted = self.client.delete(f"/api/evaluations/tasks/{task['id']}/")
        self.assertTrue(deleted.json()["deleted"])

    @patch("chat.views.requests.post")
    def test_evaluation_task_runs_selected_ollama_model(self, mock_post):
        class FakeResponse:
            ok = True
            status_code = 200
            text = ""

            def json(self):
                return {"response": "Use a + b.", "done": True}

        mock_post.return_value = FakeResponse()
        task = EvaluationTask.objects.create(
            owner=self.user,
            name="Add numbers",
            prompt="Explain how to add two numbers.",
            language="python",
        )
        response = self.client.post(f"/api/evaluations/tasks/{task.id}/run/", {"model": "qwen2.5-coder:1.5b"})
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["run"]["model_name"], "qwen2.5-coder:1.5b")
        self.assertEqual(response.json()["run"]["response"], "Use a + b.")
        self.assertEqual(AiEvent.objects.get(event_type="evaluation").output_chars, len("Use a + b."))

    @patch("chat.views.requests.post")
    def test_evaluation_response_gets_automatic_rubric_score(self, mock_post):
        class FakeResponse:
            ok = True
            status_code = 200
            text = ""

            def json(self):
                return {"response": "Return a + b to add the values.", "done": True}

        mock_post.return_value = FakeResponse()
        task = EvaluationTask.objects.create(
            owner=self.user,
            name="Score addition",
            prompt="Explain addition",
            expected_output="Return a + b to add the values.",
        )
        run = self.client.post(f"/api/evaluations/tasks/{task.id}/run/", {}).json()["run"]
        scored = self.client.post(f"/api/evaluations/runs/{run['id']}/score/", {"automatic": "true"})
        self.assertTrue(scored.json()["success"])
        self.assertEqual(scored.json()["score"]["correctness"], 100)
        self.assertGreater(scored.json()["score"]["overall"], 0)

    def test_regression_suite_establishes_and_checks_a_baseline(self):
        task = EvaluationTask.objects.create(owner=self.user, name="Baseline task", prompt="Explain this.")
        run = EvaluationRun.objects.create(owner=self.user, task=task, model_name="qwen2.5-coder:1.5b", status="completed", response="answer")
        EvaluationScore.objects.create(run=run, correctness=90, relevance=90, completeness=90, safety=90, overall=90)
        created = self.client.post("/api/evaluations/regressions/", {
            "name": "Core benchmark",
            "task_ids": f"[{task.id}]",
        })
        self.assertEqual(created.status_code, 201)
        suite_id = created.json()["suite"]["id"]
        result = self.client.post(f"/api/evaluations/regressions/{suite_id}/run/", {"model": "qwen2.5-coder:1.5b"})
        payload = result.json()["suite"]["last_result"]
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["results"][0]["delta"], 0)

    def test_evaluation_dashboard_summarizes_runs_models_and_scores(self):
        task = EvaluationTask.objects.create(owner=self.user, name="Dashboard task", prompt="Explain this.")
        run = EvaluationRun.objects.create(
            owner=self.user,
            task=task,
            model_name="qwen2.5-coder:1.5b",
            status="completed",
            response="answer",
            duration_ms=120,
        )
        EvaluationScore.objects.create(run=run, correctness=80, relevance=80, completeness=80, safety=80, overall=80)
        EvaluationRun.objects.create(
            owner=self.user,
            task=task,
            model_name="qwen2.5-coder:1.5b",
            status="failed",
            duration_ms=200,
        )
        payload = self.client.get("/api/evaluations/dashboard/").json()
        self.assertEqual(payload["summary"]["runs"], 2)
        self.assertEqual(payload["summary"]["success_rate"], 50.0)
        self.assertEqual(payload["summary"]["average_score"], 80.0)
        self.assertEqual(payload["models"][0]["completed"], 1)

    def test_guest_upload_requires_free_account(self):
        self.client.logout()
        image = SimpleUploadedFile("diagram.png", b"fake-image", content_type="image/png")
        response = self.client.post("/api/ask-code/", {
            "prompt": "Explain this image",
            "images": image,
        })
        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.json()["login_required"])

    def test_auth_pages_render(self):
        self.client.logout()
        self.assertEqual(self.client.get("/login/").status_code, 200)
        self.assertEqual(self.client.get("/signup/").status_code, 200)

    def test_authenticated_image_uses_vision_model(self):
        class FakeResponse:
            status_code = 200
            text = ""

            def iter_lines(self, decode_unicode=True):
                return [
                    json.dumps({"response": "Image understood. "}).encode(),
                    json.dumps({"done": True}).encode(),
                ]

        image = SimpleUploadedFile("diagram.png", b"fake-image", content_type="image/png")
        with patch("chat.views.requests.post", return_value=FakeResponse()) as post:
            response = self.client.post("/api/ask-code/", {
                "prompt": "Explain this image",
                "images": image,
            })
            list(response.streaming_content)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "llava:latest")
        self.assertEqual(len(payload["images"]), 1)

    def test_observability_records_completed_chat_metrics(self):
        class FakeResponse:
            status_code = 200
            text = ""

            def iter_lines(self, decode_unicode=True):
                return [
                    json.dumps({"response": "Tracked answer"}).encode(),
                    json.dumps({"done": True}).encode(),
                ]

        with patch("chat.views.requests.post", return_value=FakeResponse()):
            response = self.client.post("/api/ask-code/", {"prompt": "Track this request"})
            list(response.streaming_content)

        event = AiEvent.objects.get(owner=self.user)
        self.assertTrue(event.success)
        self.assertEqual(event.event_type, "chat")
        self.assertEqual(event.output_chars, len("Tracked answer"))

        dashboard = self.client.get("/api/observability/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.json()["summary"]["events"], 1)
        self.assertEqual(dashboard.json()["summary"]["success_rate"], 100.0)

    def test_observability_includes_agent_timeline_and_resource_summary(self):
        task = AgentTask.objects.create(
            owner=self.user,
            title="Observe agent",
            goal="Track a running task",
            status="running",
            logs=[{"message": "Waiting for approval", "level": "warning"}],
        )
        AgentJob.objects.create(
            owner=self.user,
            task=task,
            status="paused",
            logs=[{"message": "Checkpoint saved", "level": "info"}],
        )
        AiEvent.objects.create(owner=self.user, event_type="agent", metadata={"cpu_ms": 42, "memory_mb": 128, "tool_calls": 2})
        payload = self.client.get("/api/observability/").json()
        self.assertEqual(payload["agent_summary"]["active_jobs"], 1)
        self.assertEqual(payload["resource_usage"]["cpu_ms"], 42)
        self.assertTrue(any(item["message"] == "Checkpoint saved" for item in payload["timeline"]))

    def test_secrets_vault_encrypts_masks_and_reveals_only_on_admin_action(self):
        saved = self.client.post("/api/secrets/", {
            "name": "GITHUB_TOKEN",
            "value": "ghp-super-secret",
            "description": "GitHub automation token",
        })
        self.assertEqual(saved.status_code, 200)
        item = SecretVaultItem.objects.get(name="GITHUB_TOKEN")
        self.assertNotEqual(item.ciphertext, "ghp-super-secret")
        listing = self.client.get("/api/secrets/").json()
        self.assertEqual(listing["secrets"][0]["masked"], True)
        self.assertNotIn("ghp-super-secret", json.dumps(listing))
        revealed = self.client.post(f"/api/secrets/{item.id}/reveal/")
        self.assertEqual(revealed.json()["value"], "ghp-super-secret")
        updated = self.client.post("/api/secrets/", {"name": "GITHUB_TOKEN", "value": "ghp-rotated"})
        self.assertEqual(updated.json()["secret"]["version"], 2)

    def test_extension_marketplace_requires_permissions_and_supports_install_uninstall(self):
        catalog = self.client.get("/api/extensions/marketplace/").json()["extensions"]
        package = next(item for item in catalog if item["slug"] == "mcp-project-search")
        denied = self.client.post("/api/extensions/marketplace/", {"action": "install", "slug": package["slug"], "permissions_approved": "false", "approved_permissions": "[]"})
        self.assertEqual(denied.status_code, 400)
        installed = self.client.post("/api/extensions/marketplace/", {
            "action": "install",
            "slug": package["slug"],
            "permissions_approved": "true",
            "approved_permissions": json.dumps(package["permissions"]),
        })
        self.assertEqual(installed.status_code, 200)
        self.assertTrue(installed.json()["extension"]["installed"])
        self.assertTrue(ExtensionInstall.objects.filter(owner=self.user, package__slug=package["slug"], status="installed").exists())
        published = self.client.post("/api/extensions/marketplace/", {
            "action": "publish",
            "name": "Internal Connector",
            "slug": "internal-connector",
            "permissions": '["project.read"]',
            "manifest": '{"connector_type":"custom"}',
        })
        self.assertEqual(published.status_code, 200)
        self.assertTrue(ExtensionPackage.objects.filter(owner=self.user, slug="custom-tester-internal-connector").exists())
        removed = self.client.post("/api/extensions/marketplace/", {"action": "uninstall", "slug": package["slug"]})
        self.assertEqual(removed.json()["extension"]["install_status"], "disabled")

    def test_deployment_toolkit_generates_health_checks_and_validates_environment(self):
        generated = self.client.post("/api/deployment/kit/", {
            "project_name": "Syntax App",
            "port": "8080",
            "health_path": "/health",
            "strategy": "rolling",
        })
        self.assertEqual(generated.status_code, 200)
        payload = generated.json()
        self.assertIn("k8s/syntax-app-deployment.yml", payload["files"])
        self.assertIn("/health", payload["files"]["docker-compose.deploy.yml"])
        validation = self.client.post("/api/deployment/validate/", {"content": "APP_ENV=production\nSECRET_KEY=literal-secret\nEMPTY="})
        self.assertFalse(validation.json()["valid"])
        self.assertTrue(any("SECRET_KEY" in warning for warning in validation.json()["warnings"]))

    def test_workspace_roles_and_audit_log(self):
        created = self.client.post("/api/workspace/", {"action": "create", "name": "Core team"})
        self.assertEqual(created.status_code, 200)
        workspace = created.json()["workspace"]
        member_user = User.objects.create_user(username="reviewer", password="review-password-123")

        added = self.client.post("/api/workspace/", {
            "action": "add_member",
            "username": member_user.username,
            "role": "reviewer",
        })
        self.assertEqual(added.status_code, 200)
        self.assertEqual(
            WorkspaceMembership.objects.get(workspace_id=workspace["id"], user=member_user).role,
            "reviewer",
        )
        self.assertGreaterEqual(AuditEvent.objects.filter(workspace_id=workspace["id"]).count(), 2)

        self.client.logout()
        self.client.login(username=member_user.username, password="review-password-123")
        denied = self.client.post("/api/workspace/", {
            "action": "add_member",
            "username": self.user.username,
            "role": "viewer",
        })
        self.assertEqual(denied.status_code, 403)

    def test_devops_assistant_generates_dockerfile_and_analyzes_logs(self):
        artifact = self.client.post("/api/devops/generate/", {
            "kind": "dockerfile",
            "code": "from django import forms",
            "filenames": "requirements.txt",
        })
        self.assertEqual(artifact.status_code, 200)
        self.assertIn("python:3.12", artifact.json()["artifact"])
        self.assertIn("requirements.txt", artifact.json()["artifact"])

        logs = self.client.post("/api/devops/logs/", {
            "logs": "ERROR connection refused on port 8000\nWARNING retrying",
        })
        payload = logs.json()
        self.assertTrue(payload["success"])
        self.assertEqual(len(payload["findings"]), 2)
        self.assertTrue(payload["recommendations"])

    def test_documentation_generator_creates_readme_and_onboarding(self):
        readme = self.client.post("/api/documentation/generate/", {
            "doc_type": "readme",
            "project_name": "Syntax Local AI",
            "filename": "chat/views.py",
            "code": "def ask_code(request):\n    return None\nclass Runner:\n    pass\n",
        })
        self.assertEqual(readme.status_code, 200)
        self.assertIn("# Syntax Local AI", readme.json()["markdown"])
        self.assertIn("ask_code", readme.json()["markdown"])

        onboarding = self.client.post("/api/documentation/generate/", {
            "doc_type": "onboarding",
            "project_name": "Syntax Local AI",
            "files_json": '[{"filename":"README.md","content":"hello"}]',
        })
        self.assertEqual(onboarding.status_code, 200)
        self.assertIn("First setup", onboarding.json()["markdown"])

    def test_review_gate_reports_blocking_security_issue(self):
        response = self.client.post("/api/review/gate/", {
            "filename": "app.py",
            "language": "python",
            "code": "result = eval(user_input)",
            "diff": "+ result = eval(user_input)",
            "tests": "assert True",
        })
        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(payload["ready"])
        self.assertLess(payload["score"], 80)
        self.assertTrue(any(item["source"] == "security" for item in payload["findings"]))

    def test_dependency_assistant_finds_unpinned_packages(self):
        response = self.client.post("/api/dependencies/analyze/", {
            "filename": "requirements.txt",
            "content": "Django>=5.0\nrequests==2.32.3\n",
        })
        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload["dependencies"]), 2)
        self.assertEqual(payload["dependencies"][0]["name"], "Django")
        self.assertTrue(payload["findings"])
        self.assertIn("Pin Django", payload["upgrade_plan"][0])

    def test_browser_testing_generates_playwright_and_parses_report(self):
        generated = self.client.post("/api/browser-tests/generate/", {
            "base_url": "http://localhost:8000",
            "flow": "Sign in and open the project workspace",
            "snapshot_name": "workspace",
        })
        self.assertEqual(generated.status_code, 200)
        self.assertIn("toHaveScreenshot", generated.json()["test_code"])
        report = self.client.post("/api/browser-tests/report/", {
            "report": "PASS workspace user flow\nFAIL visual snapshot changed\nScreenshot mismatch",
        })
        self.assertEqual(report.status_code, 200)
        self.assertEqual(len(report.json()["failed"]), 1)
        self.assertEqual(len(report.json()["visual_events"]), 2)

    def test_smart_model_router_prefers_coding_model(self):
        response = self.client.post("/api/models/route/", {
            "task": "debug Python code and generate tests",
            "models_json": json.dumps(["phi3:mini", "qwen2.5-coder:1.5b", "llava:latest"]),
            "memory_gb": "8",
            "gpu": "false",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["selected_model"], "qwen2.5-coder:1.5b")
        self.assertTrue(response.json()["candidates"])

    def test_devcontainer_generator_detects_python_project(self):
        response = self.client.post("/api/devcontainers/generate/", {
            "project_name": "Syntax Local AI",
            "files_json": json.dumps([
                {"filename": "requirements.txt", "content": "Django==5.0"},
                {"filename": "manage.py", "content": "print('ok')"},
            ]),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["path"], ".devcontainer/devcontainer.json")
        self.assertIn("devcontainers/python", response.json()["config"])
        self.assertIn("pip install -r requirements.txt", response.json()["config"])

    def test_incident_assistant_correlates_errors_and_drafts_postmortem(self):
        response = self.client.post("/api/incidents/analyze/", {
            "logs": "ERROR connection refused to database\nWARNING retrying request",
            "traces": "trace_id=abc span=db.query duration=3s",
            "metrics": "cpu=92 memory=70",
        })
        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload["errors"]), 1)
        self.assertTrue(payload["suspected_causes"])
        self.assertIn("postmortem", payload["postmortem"])

    def test_architecture_graph_detects_relationships_and_symbols(self):
        response = self.client.post("/api/architecture/analyze/", {
            "files_json": json.dumps([
                {"filename": "app.py", "content": "from services import run\n\ndef main():\n    return run()\n"},
                {"filename": "services.py", "content": "from app import main\n\ndef run():\n    return True\n"},
            ]),
        })
        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(payload["edges"]), 2)
        self.assertTrue(payload["symbols"])
        self.assertTrue(payload["cycles"])

    def test_cross_repository_graph_reports_service_impact(self):
        response = self.client.post("/api/architecture/cross-repo/", {
            "repositories_json": json.dumps([
                {"name": "api", "files": [{"filename": "users.py", "content": "def users(): return True"}]},
                {"name": "worker", "files": [{"filename": "jobs.py", "content": "from users import users"}]},
            ]),
        })
        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload["cross_edges"]), 1)
        self.assertEqual(payload["impacts"][0]["repository"], "api")

    def test_enterprise_identity_rotates_token_and_provisions_scim_users(self):
        saved = self.client.post("/api/identity/enterprise/", {
            "provider": "oidc",
            "issuer_url": "https://idp.example.com",
            "client_id": "syntax-local",
            "allowed_domains": "example.com",
            "enforce_sso": "true",
            "scim_enabled": "true",
            "action": "rotate_scim_token",
        })
        self.assertEqual(saved.status_code, 200)
        token = saved.json()["scim_token"]
        self.assertTrue(saved.json()["identity_config"]["token_configured"])
        self.assertNotIn("scim_token", self.client.get("/api/identity/enterprise/").json())
        workspace = WorkspaceMembership.objects.get(user=self.user).workspace
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}", "HTTP_X_WORKSPACE_ID": str(workspace.id)}
        provisioned = self.client.post(
            "/api/identity/scim/",
            data=json.dumps({"userName": "directory-user", "displayName": "Directory User", "active": True, "role": "reviewer"}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(provisioned.status_code, 201)
        member = WorkspaceMembership.objects.get(workspace=workspace, user__username="directory-user")
        self.assertEqual(member.role, "reviewer")
        deprovisioned = self.client.delete(
            "/api/identity/scim/",
            data=json.dumps({"userName": "directory-user"}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(deprovisioned.status_code, 200)
        self.assertFalse(User.objects.get(username="directory-user").is_active)
        self.assertFalse(WorkspaceMembership.objects.filter(id=member.id).exists())
        self.assertTrue(EnterpriseIdentityConfig.objects.filter(workspace=workspace, scim_enabled=True).exists())

    def test_oidc_login_uses_pkce_state_and_links_workspace_user(self):
        saved = self.client.post("/api/identity/enterprise/", {
            "provider": "oidc",
            "issuer_url": "https://idp.example.com",
            "client_id": "syntax-local",
            "allowed_domains": "example.com",
        })
        self.assertEqual(saved.status_code, 200)
        discovery = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "authorization_endpoint": "https://idp.example.com/authorize",
                "token_endpoint": "https://idp.example.com/token",
                "userinfo_endpoint": "https://idp.example.com/userinfo",
            },
        )
        userinfo = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"email": "sso-user@example.com", "name": "SSO User"})
        token_response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"access_token": "access-token"})
        with patch("chat.views.requests.get", side_effect=[discovery, discovery, userinfo]) as get_request, patch("chat.views.requests.post", return_value=token_response):
            started = self.client.get("/sso/oidc/login/")
            self.assertEqual(started.status_code, 302)
            location = started["Location"]
            query = parse_qs(urlparse(location).query)
            self.assertEqual(query["code_challenge_method"], ["S256"])
            completed = self.client.get("/sso/oidc/callback/?code=auth-code&state=" + query["state"][0])
        self.assertEqual(completed.status_code, 302)
        self.assertEqual(completed["Location"], "/")
        self.assertTrue(User.objects.filter(username="sso-user", email="sso-user@example.com").exists())
        self.assertEqual(get_request.call_count, 3)

    def test_api_contract_finds_undocumented_endpoint(self):
        response = self.client.post("/api/contracts/analyze/", {
            "spec": json.dumps({"paths": {"/api/users/": {"get": {}}}}),
            "code": 'path("api/users/", views.users)\npath("api/orders/", views.orders)',
        })
        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload["implemented"]), 2)
        self.assertEqual(payload["undocumented"][0]["path"], "/api/orders")
        self.assertIn("openapi", payload["suggested_openapi"])

    def test_provenance_generator_and_verifier(self):
        generated = self.client.post("/api/provenance/generate/", {
            "artifact_name": "syntax-local-ai.zip",
            "commit": "abc123",
            "files_json": json.dumps([
                {"filename": "requirements.txt", "content": "Django==5.0"},
                {"filename": "manage.py", "content": "print('ok')"},
            ]),
        })
        self.assertEqual(generated.status_code, 200)
        provenance = generated.json()["provenance"]
        self.assertIn("predicateType", provenance)
        verified = self.client.post("/api/provenance/verify/", {"provenance": provenance})
        self.assertEqual(verified.status_code, 200)
        self.assertTrue(verified.json()["valid"])

    def test_identity_policy_center_allows_admin_and_blocks_member_changes(self):
        saved = self.client.post("/api/identity/policy/", {
            "require_approval_for_git": "true",
            "require_approval_for_tools": "true",
            "require_approval_for_deploy": "false",
            "require_tests": "true",
            "allow_external_connectors": "false",
            "audit_retention_days": "180",
        })
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["policy"]["audit_retention_days"], 180)
        self.assertTrue(WorkspacePolicy.objects.exists())
        self.assertTrue(AuditEvent.objects.filter(event_type="policy.updated").exists())

    def test_quality_endpoint_finds_security_issue(self):
        response = self.client.post("/api/analyze/", {
            "language": "python",
            "mode": "security",
            "code": "result = eval(user_input)",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["findings"])
        self.assertEqual(response.json()["findings"][0]["category"], "security")

    def test_sql_runner_uses_in_memory_database(self):
        response = self.client.post("/api/execute/", {
            "language": "sql",
            "code": "CREATE TABLE users (name TEXT); INSERT INTO users VALUES ('Ada'); SELECT name FROM users;",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertIn("Ada", response.json()["stdout"])

    def test_python_runner_executes_inside_guarded_sandbox(self):
        response = self.client.post("/api/execute/", {
            "language": "python",
            "code": "print('hello from sandbox')",
        })
        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["success"])
        self.assertIn("hello from sandbox", payload["stdout"])
        self.assertEqual(payload["sandbox"], "guarded-local")
        self.assertEqual(payload["limits"]["timeout_seconds"], 3)
        self.assertEqual(payload["limits"]["memory_mb"], 128)

    def test_python_runner_blocks_imports(self):
        response = self.client.post("/api/execute/", {
            "language": "python",
            "code": "import os; print(os.getcwd())",
        })
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertIn("imports are disabled", payload["stderr"])

    def test_javascript_runner_executes_without_network_apis(self):
        response = self.client.post("/api/execute/", {
            "language": "javascript",
            "code": "console.log('hello from javascript')",
        })
        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["success"])
        self.assertIn("hello from javascript", payload["stdout"])

    def test_sql_runner_blocks_file_operations(self):
        response = self.client.post("/api/execute/", {
            "language": "sql",
            "code": "ATTACH DATABASE 'outside.db' AS external",
        })
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertIn("blocked", payload["stderr"])

    def test_export_markdown_is_downloadable(self):
        session = ChatSession.objects.create(owner=self.user, title="Export me")
        ChatMessage.objects.create(session=session, role="user", content="Hello")
        response = self.client.get(f"/api/session/{session.id}/export/?format=markdown")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/markdown")
        self.assertIn("Export me", response.content.decode())

    def test_project_upload_creates_document_chunks_before_model_call(self):
        upload = SimpleUploadedFile(
            "project/app.py",
            b"def greet():\\n    return 'hello'\\n",
            content_type="text/plain",
        )
        with patch("chat.views.requests.post", side_effect=RequestsConnectionError()):
            response = self.client.post("/api/ask-code/", {
                "prompt": "Explain this file",
                "language": "python",
                "files": upload,
                "file_paths": "project/app.py",
            })
        self.assertEqual(response.status_code, 500)
        document = KnowledgeDocument.objects.get(owner=self.user)
        self.assertEqual(document.filename, "project/app.py")
        self.assertTrue(KnowledgeChunk.objects.filter(document=document).exists())

    def test_edit_message_archives_old_branch_and_regenerates(self):
        session = ChatSession.objects.create(owner=self.user, title="Editable chat")
        old_user = ChatMessage.objects.create(
            session=session,
            role="user",
            content="Old request",
        )
        ChatMessage.objects.create(
            session=session,
            role="assistant",
            content="Old answer",
        )

        class FakeResponse:
            status_code = 200
            text = ""

            def iter_lines(self, decode_unicode=True):
                return [
                    json.dumps({"response": "New answer"}).encode(),
                    json.dumps({"done": True}).encode(),
                ]

        with patch("chat.views.requests.post", return_value=FakeResponse()):
            response = self.client.post("/api/ask-code/", {
                "session_id": session.id,
                "edit_message_id": old_user.id,
                "prompt": "New request",
                "language": "python",
            })
            list(response.streaming_content)

        current_messages = list(session.messages.order_by("id"))
        self.assertEqual(len(current_messages), 2)
        self.assertIn("New request", current_messages[0].content)
        self.assertEqual(current_messages[1].content, "New answer")
        revisions = self.client.get(f"/api/session/{session.id}/revisions/").json()
        self.assertTrue(revisions["success"])
        self.assertEqual(revisions["revisions"][0]["messages"], 2)

    def test_project_workspace_lists_reindexes_and_deletes_documents(self):
        document = KnowledgeDocument.objects.create(
            owner=self.user,
            title="app.py",
            filename="project/app.py",
            language="python",
            original_text="def greet(): return 'hello'",
            file_size_bytes=28,
        )
        KnowledgeChunk.objects.create(
            document=document,
            chunk_index=0,
            content=document.original_text,
            language="python",
        )

        listing = self.client.get("/api/project/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["documents"][0]["filename"], "project/app.py")
        self.assertEqual(listing.json()["documents"][0]["chunks"], 1)

        reindex = self.client.post(f"/api/project/{document.id}/reindex/")
        self.assertEqual(reindex.status_code, 200)
        self.assertEqual(reindex.json()["chunks"], 1)

        deleted = self.client.delete(f"/api/project/{document.id}/")
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(KnowledgeDocument.objects.filter(id=document.id).exists())

    def test_project_editor_can_open_save_and_reindex_a_file(self):
        document = KnowledgeDocument.objects.create(
            owner=self.user,
            title="editor.py",
            filename="editor.py",
            language="python",
            original_text="print('old')",
            file_size_bytes=12,
        )
        opened = self.client.get(f"/api/project/{document.id}/content/")
        self.assertEqual(opened.status_code, 200)
        self.assertEqual(opened.json()["document"]["content"], "print('old')")

        saved = self.client.post(
            f"/api/project/{document.id}/content/",
            {"content": "print('new')"},
        )
        self.assertEqual(saved.status_code, 200)
        document.refresh_from_db()
        self.assertEqual(document.original_text, "print('new')")
        self.assertTrue(document.chunks.exists())

    def test_patch_preview_returns_unified_diff(self):
        response = self.client.post(
            "/api/patch/preview/",
            {
                "filename": "editor.py",
                "original": "print('old')",
                "updated": "print('new')",
            },
        )
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertTrue(payload["changed"])
        self.assertIn("--- editor.py (current)", payload["diff"])
        self.assertIn("+print('new')", payload["diff"])

    @patch("chat.views.subprocess.run")
    def test_git_workspace_reports_stages_and_commits_changes(self, mock_run):
        result = lambda stdout="", stderr="", returncode=0: SimpleNamespace(
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
        )
        mock_run.side_effect = [
            result(stdout="main\n"),
            result(stdout=" M app.py\n?? new.py\n"),
            result(),
            result(stdout="[main abc123] Add files\n"),
        ]

        status = self.client.get("/api/git/status/")
        self.assertEqual(status.json()["branch"], "main")
        self.assertEqual(status.json()["files"][0]["path"], "app.py")
        self.assertEqual(status.json()["files"][1]["status"], "??")

        staged = self.client.post("/api/git/stage/", {"paths": ["app.py"]})
        self.assertTrue(staged.json()["success"])
        committed = self.client.post("/api/git/commit/", {"message": "Add files"})
        self.assertTrue(committed.json()["success"])
        self.assertEqual(mock_run.call_args_list[-1].args[0][-2:], ["-m", "Add files"])

    @patch("chat.views.requests.get")
    def test_ollama_settings_save_and_validate_local_server(self, mock_get):
        mock_get.return_value = SimpleNamespace(
            ok=True,
            json=lambda: {"models": [{"name": "deepseek-coder:latest"}]},
        )
        initial = self.client.get("/api/ollama/settings/")
        self.assertEqual(initial.json()["settings"]["server_url"], "http://127.0.0.1:11434")
        invalid = self.client.post(
            "/api/ollama/settings/",
            {"server_url": "https://example.com:11434"},
        )
        self.assertEqual(invalid.status_code, 400)
        saved = self.client.post(
            "/api/ollama/settings/",
            {
                "server_url": "http://localhost:11434/",
                "default_model": "deepseek-coder:latest",
                "temperature": "0.7",
                "top_p": "0.8",
                "max_context_chars": "32000",
            },
        )
        self.assertTrue(saved.json()["success"])
        self.assertEqual(saved.json()["settings"]["server_url"], "http://localhost:11434")
        self.assertEqual(saved.json()["settings"]["temperature"], 0.7)
        self.assertIn("deepseek-coder:latest", saved.json()["models"])

    def test_test_workspace_generates_and_runs_python_tests(self):
        generated = self.client.post(
            "/api/tests/generate/",
            {"code": "def add(a, b):\n    return a + b", "language": "python"},
        )
        self.assertTrue(generated.json()["success"])
        self.assertIn("test_add_happy_path", generated.json()["test_code"])

        executed = self.client.post(
            "/api/tests/run/",
            {
                "code": "def add(a, b):\n    return a + b",
                "test_code": (
                    "def test_add():\n"
                    "    assert add(2, 3) == 5\n"
                    "\n"
                    "if __name__ == '__main__':\n"
                    "    test_add()\n"
                    "    print('PASS')\n"
                ),
                "language": "python",
            },
        )
        self.assertTrue(executed.json()["success"])
        self.assertEqual(executed.json()["summary"], "Tests passed.")
        self.assertIn("PASS", executed.json()["result"]["stdout"])

    def test_agent_plan_requires_approval_and_supports_undo(self):
        planned = self.client.post(
            "/api/agent/plan/",
            {"goal": "Update the editor, run tests, and prepare a Git commit"},
        )
        self.assertTrue(planned.json()["success"])
        task = planned.json()["task"]
        self.assertEqual(task["status"], "planned")
        self.assertTrue(task["plan"][0]["approved"])
        self.assertTrue(task["plan"][1]["requires_approval"])

        approved = self.client.post(
            f"/api/agent/task/{task['id']}/",
            {"action": "approve", "step": 1},
        )
        self.assertEqual(approved.json()["task"]["status"], "running")
        self.assertTrue(approved.json()["task"]["plan"][1]["approved"])

        rejected = self.client.post(
            f"/api/agent/task/{task['id']}/",
            {"action": "reject", "step": 1},
        )
        self.assertEqual(rejected.json()["task"]["status"], "blocked")

        undone = self.client.post(
            f"/api/agent/task/{task['id']}/",
            {"action": "undo"},
        )
        self.assertEqual(undone.json()["task"]["status"], "planned")
        self.assertFalse(undone.json()["task"]["plan"][1]["approved"])

    def test_agent_run_logs_safe_checks_and_supports_controls(self):
        task = self.client.post("/api/agent/plan/", {"goal": "Run tests and review changes"}).json()["task"]
        for step in (1, 2, 4):
            self.client.post(f"/api/agent/task/{task['id']}/", {"action": "approve", "step": step})
        run = self.client.post(
            f"/api/agent/task/{task['id']}/run/",
            {
                "code": "def add(a, b):\n    return a + b",
                "test_code": "assert add(2, 3) == 5",
            },
        )
        self.assertTrue(run.json()["success"])
        self.assertEqual(run.json()["task"]["control_state"], "running")
        self.assertTrue(any("Guarded tests passed" in item["message"] for item in run.json()["task"]["logs"]))
        paused = self.client.post(f"/api/agent/task/{task['id']}/control/", {"action": "pause"})
        self.assertEqual(paused.json()["task"]["control_state"], "paused")
        resumed = self.client.post(f"/api/agent/task/{task['id']}/control/", {"action": "resume"})
        self.assertEqual(resumed.json()["task"]["control_state"], "running")

    def test_security_center_detects_secrets_and_dependency_hygiene(self):
        response = self.client.post(
            "/api/security/scan/",
            {
                "files": json.dumps([
                    {
                        "filename": "app.py",
                        "content": "API_KEY = 'sk_test_1234567890'\nimport os\nos.system(user_input)\n",
                    },
                    {
                        "filename": "requirements.txt",
                        "content": "django==5.2.15\nrequests\n",
                    },
                ]),
            },
        )
        payload = response.json()
        self.assertTrue(payload["success"])
        rules = {item["rule"] for item in payload["findings"]}
        self.assertIn("secret-generic", rules)
        self.assertIn("command-execution", rules)
        self.assertIn("unpinned-dependency", rules)
        self.assertEqual(payload["sbom"]["bomFormat"], "SPDX")

    @patch("chat.views.requests.request")
    def test_remote_git_connects_lists_issues_and_creates_draft(self, mock_request):
        response = lambda payload: SimpleNamespace(ok=True, text="", json=lambda: payload)
        mock_request.side_effect = [
            response([{"full_name": "demo/project", "id": 1, "html_url": "https://github.com/demo/project"}]),
            response([{"number": 7, "title": "Fix bug", "html_url": "https://github.com/demo/project/issues/7"}]),
            response({"number": 8, "html_url": "https://github.com/demo/project/pull/8"}),
        ]
        connected = self.client.post(
            "/api/remote/settings/",
            {"provider": "github", "token": "ghp_example_token", "repository": "demo/project"},
        )
        self.assertTrue(connected.json()["token_set"])
        repositories = self.client.get("/api/remote/repositories/")
        self.assertEqual(repositories.json()["repositories"][0]["name"], "demo/project")
        issues = self.client.get("/api/remote/issues/")
        self.assertEqual(issues.json()["issues"][0]["id"], 7)
        pull_request = self.client.post(
            "/api/remote/pull-request/",
            {
                "title": "Fix bug",
                "head": "fix/bug",
                "base": "main",
                "body": "Summary",
            },
        )
        self.assertTrue(pull_request.json()["success"])
        self.assertEqual(pull_request.json()["number"], 8)

    def test_local_cli_endpoint_streams_without_csrf(self):
        class FakeResponse:
            status_code = 200
            text = ""

            def iter_lines(self, decode_unicode=True):
                return [
                    json.dumps({"response": "CLI answer"}).encode(),
                    json.dumps({"done": True}).encode(),
                ]

        with patch("chat.views.requests.post", return_value=FakeResponse()):
            response = self.client.post("/api/cli/ask/", {"prompt": "Explain this", "code": "print('hi')"})
            output = b"".join(response.streaming_content).decode()
        self.assertIn('"type": "token"', output)
        self.assertIn("CLI answer", output)

    def test_mcp_connectors_tools_and_write_approval(self):
        created = self.client.post(
            "/api/mcp/connectors/",
            {
                "name": "Project docs",
                "connector_type": "documentation",
                "config": json.dumps({"path": "./docs"}),
            },
        )
        self.assertTrue(created.json()["success"])
        listing = self.client.get("/api/mcp/connectors/")
        self.assertEqual(listing.json()["connectors"][0]["name"], "Project docs")
        self.assertTrue(any(tool["name"] == "project.search" for tool in listing.json()["tools"]))

        tools = self.client.post(
            "/api/mcp/",
            data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}),
            content_type="application/json",
        )
        self.assertTrue(any(tool["name"] == "git.commit" for tool in tools.json()["result"]["tools"]))

        search = self.client.post(
            "/api/mcp/",
            data=json.dumps({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "project.search", "arguments": {"query": "missing"}},
            }),
            content_type="application/json",
        )
        self.assertIn("content", search.json()["result"])
        blocked = self.client.post(
            "/api/mcp/",
            data=json.dumps({
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "git.commit", "arguments": {"message": "No approval"}},
            }),
            content_type="application/json",
        )
        self.assertEqual(blocked.status_code, 400)

    def test_rag_results_include_source_line_ranges(self):
        source = "first" + chr(10) + "needle = True" + chr(10) + "last"
        document = KnowledgeDocument.objects.create(
            owner=self.user,
            title="source.py",
            filename="source.py",
            language="python",
            original_text=source,
            file_size_bytes=len(source),
        )
        KnowledgeChunk.objects.create(
            document=document,
            chunk_index=0,
            content=source,
            language="python",
        )

        results = _search_knowledge("needle", owner=self.user)
        self.assertEqual(results[0]["filename"], "source.py")
        self.assertEqual(results[0]["line_start"], 1)
        self.assertEqual(results[0]["line_end"], 3)

    def test_chat_management_supports_search_rename_tags_pin_archive_and_delete(self):
        matching = ChatSession.objects.create(owner=self.user, title="Bug review")
        other = ChatSession.objects.create(owner=self.user, title="Release notes")

        listing = self.client.get("/api/sessions/?q=bug")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual([item["id"] for item in listing.json()["sessions"]], [matching.id])

        renamed = self.client.post(
            f"/api/session/{matching.id}/manage/",
            {"action": "rename", "title": "Important bug review"},
        )
        self.assertEqual(renamed.json()["title"], "Important bug review")
        tagged = self.client.post(
            f"/api/session/{matching.id}/manage/",
            {"action": "tag", "tags": "backend, urgent, backend"},
        )
        self.assertEqual(tagged.json()["tags"], ["backend", "urgent"])
        pinned = self.client.post(
            f"/api/session/{matching.id}/manage/",
            {"action": "pin"},
        )
        self.assertTrue(pinned.json()["is_pinned"])
        archived = self.client.post(
            f"/api/session/{matching.id}/manage/",
            {"action": "archive"},
        )
        self.assertTrue(archived.json()["success"])
        self.assertEqual(self.client.get("/api/sessions/?q=bug").json()["sessions"], [])

        deleted = self.client.post(
            f"/api/session/{other.id}/manage/",
            {"action": "delete"},
        )
        self.assertTrue(deleted.json()["deleted"])

    def test_generated_file_save_and_project_backup_restore(self):
        saved = self.client.post("/api/project/save/", {
            "filename": "generated.py",
            "content": "print('hello')",
            "language": "python",
        })
        self.assertTrue(saved.json()["success"])
        session = ChatSession.objects.create(owner=self.user, title="Backup chat")
        ChatMessage.objects.create(session=session, role="user", content="Generate hello")
        ChatMessage.objects.create(session=session, role="assistant", content="print('hello')")
        backup = self.client.get("/api/backup/")
        self.assertEqual(backup.status_code, 200)
        self.assertEqual(backup["Content-Type"], "application/zip")

        KnowledgeDocument.objects.filter(owner=self.user).delete()
        ChatSession.objects.filter(owner=self.user).delete()
        restored = self.client.post(
            "/api/backup/",
            {"backup": SimpleUploadedFile("backup.zip", backup.content, content_type="application/zip")},
        )
        self.assertTrue(restored.json()["success"])
        self.assertEqual(restored.json()["project_files"], 1)
        self.assertEqual(restored.json()["chats"], 1)
        self.assertEqual(KnowledgeDocument.objects.get(owner=self.user).original_text, "print('hello')")
        self.assertEqual(ChatSession.objects.get(owner=self.user).title, "Backup chat")
