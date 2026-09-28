import json
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from requests.exceptions import ConnectionError as RequestsConnectionError
from unittest.mock import patch

from .models import AiEvent, AuditEvent, ChatMessage, ChatSession, EvaluationTask, KnowledgeChunk, KnowledgeDocument, WorkspaceMembership, WorkspacePolicy
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
