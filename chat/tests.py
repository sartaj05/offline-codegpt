import json
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from requests.exceptions import ConnectionError as RequestsConnectionError
from unittest.mock import patch

from .models import ChatMessage, ChatSession, KnowledgeChunk, KnowledgeDocument
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
