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

    def test_home_requires_authentication(self):
        self.client.logout()
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

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
