import uuid

from django.db import models
from django.contrib.auth.models import User


class LocalModelConfig(models.Model):
    """
    Stores local Ollama model configuration.
    Example:
    qwen2.5-coder:1.5b
    phi3:latest
    """

    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=150, blank=True, null=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    temperature = models.FloatField(default=0.2)
    top_p = models.FloatField(default=0.9)
    max_context_chars = models.IntegerField(default=24000)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.display_name or self.name


class ChatSession(models.Model):
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
        blank=True,
        null=True,
    )
    title = models.CharField(max_length=200, default="New Chat")
    model_name = models.CharField(max_length=100, default="qwen2.5-coder:1.5b")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_pinned = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    tags = models.CharField(max_length=300, blank=True, default="")

    def __str__(self):
        return self.title


class ChatMessage(models.Model):
    ROLE_CHOICES = (
        ("user", "User"),
        ("assistant", "Assistant"),
        ("system", "System"),
    )

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages"
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()

    filename = models.CharField(max_length=500, blank=True, null=True)

    # Optional metadata
    model_name = models.CharField(max_length=100, blank=True, null=True)
    prompt_tokens_estimate = models.IntegerField(default=0)
    response_time_ms = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role}: {self.content[:80]}"


class ConversationRevision(models.Model):
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    source_message_id = models.IntegerField()
    branch_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    role = models.CharField(max_length=20)
    content = models.TextField()
    model_name = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"Revision {self.branch_id}: {self.role}"


class KnowledgeDocument(models.Model):
    """
    Stores uploaded files or project files.
    Example:
    views.py, models.py, urls.py, app.js
    """

    SOURCE_CHOICES = (
        ("upload", "Upload"),
        ("manual", "Manual"),
        ("project", "Project Folder"),
    )

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="knowledge_documents",
        blank=True,
        null=True,
    )
    title = models.CharField(max_length=300)
    filename = models.CharField(max_length=300, blank=True, null=True)
    file_extension = models.CharField(max_length=30, blank=True, null=True)

    source_type = models.CharField(
        max_length=30,
        choices=SOURCE_CHOICES,
        default="upload"
    )

    language = models.CharField(max_length=50, default="auto")

    original_text = models.TextField()

    file_size_bytes = models.BigIntegerField(default=0)

    # Useful for duplicate detection later
    content_hash = models.CharField(max_length=128, blank=True, null=True, db_index=True)

    is_active = models.BooleanField(default=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.filename or self.title


class KnowledgeChunk(models.Model):
    """
    Stores small chunks of uploaded code/text for local search.
    This is the main memory/RAG table.
    """

    document = models.ForeignKey(
        KnowledgeDocument,
        on_delete=models.CASCADE,
        related_name="chunks"
    )

    chunk_index = models.IntegerField()
    content = models.TextField()

    language = models.CharField(max_length=50, default="auto")

    # Optional fields for future improvement
    summary = models.TextField(blank=True, null=True)
    keywords = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["document", "chunk_index"]),
            models.Index(fields=["language"]),
        ]

    def __str__(self):
        return f"{self.document} - chunk {self.chunk_index}"


class AssistantMemory(models.Model):
    """
    Stores important learned rules/facts.
    Example:
    - User prefers Django project structure.
    - In this project, use Ollama qwen2.5-coder:1.5b.
    - Use root templates and root static folder.
    """

    MEMORY_TYPE_CHOICES = (
        ("preference", "Preference"),
        ("project_rule", "Project Rule"),
        ("bug_fix", "Bug Fix"),
        ("coding_pattern", "Coding Pattern"),
        ("general", "General"),
    )

    title = models.CharField(max_length=300)
    content = models.TextField()

    memory_type = models.CharField(
        max_length=50,
        choices=MEMORY_TYPE_CHOICES,
        default="general"
    )

    importance = models.IntegerField(default=1)  # 1 low, 5 high

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.title


class MessageFeedback(models.Model):
    """
    Stores user feedback on assistant answers.
    This helps improve future responses.
    """

    FEEDBACK_CHOICES = (
        ("like", "Like"),
        ("dislike", "Dislike"),
        ("correction", "Correction"),
    )

    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name="feedbacks"
    )

    feedback_type = models.CharField(max_length=30, choices=FEEDBACK_CHOICES)

    correction_text = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.feedback_type} for message {self.message_id}"


class TrainingExample(models.Model):
    """
    Stores clean prompt/answer examples for future offline fine-tuning.
    This does not train automatically.
    It prepares data for future LoRA/fine-tune.
    """

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("exported", "Exported"),
    )

    instruction = models.TextField()
    input_text = models.TextField(blank=True, null=True)
    expected_output = models.TextField()

    source_message = models.ForeignKey(
        ChatMessage,
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="draft")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.instruction[:80]
