import json

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from requests.exceptions import ConnectionError as RequestsConnectionError
from unittest.mock import patch

from .models import ChatMessage, ChatSession, KnowledgeChunk, KnowledgeDocument


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
