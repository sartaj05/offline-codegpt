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


class UserOllamaSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="ollama_settings")
    server_url = models.URLField(default="http://127.0.0.1:11434", max_length=300)
    default_model = models.CharField(max_length=100, default="qwen2.5-coder:1.5b")
    temperature = models.FloatField(default=0.2)
    top_p = models.FloatField(default=0.9)
    max_context_chars = models.IntegerField(default=24000)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Ollama settings for {self.user.username}"


class AgentTask(models.Model):
    STATUS_CHOICES = (
        ("planned", "Planned"),
        ("running", "Running"),
        ("blocked", "Blocked"),
        ("completed", "Completed"),
    )

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="agent_tasks")
    title = models.CharField(max_length=200)
    goal = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned")
    plan = models.JSONField(default=list)
    current_step = models.PositiveIntegerField(default=0)
    result = models.TextField(blank=True, default="")
    control_state = models.CharField(max_length=20, default="ready")
    logs = models.JSONField(default=list)
    retry_count = models.PositiveIntegerField(default=0)
    source_branch = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class McpConnector(models.Model):
    CONNECTOR_TYPES = (
        ("local_folder", "Local folder"),
        ("documentation", "Documentation"),
        ("database", "Database"),
        ("custom", "Custom"),
    )

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mcp_connectors")
    name = models.CharField(max_length=120)
    connector_type = models.CharField(max_length=30, choices=CONNECTOR_TYPES, default="custom")
    config = models.JSONField(default=dict)
    enabled = models.BooleanField(default=True)
    allow_write = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class McpToolCall(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mcp_tool_calls")
    tool_name = models.CharField(max_length=120)
    arguments = models.JSONField(default=dict)
    success = models.BooleanField(default=False)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)


class AiEvent(models.Model):
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ai_events",
        blank=True,
        null=True,
    )
    event_type = models.CharField(max_length=60, default="chat")
    model_name = models.CharField(max_length=100, blank=True, default="")
    duration_ms = models.PositiveIntegerField(default=0)
    input_chars = models.PositiveIntegerField(default=0)
    output_chars = models.PositiveIntegerField(default=0)
    success = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class Workspace(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_workspaces")
    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)


class WorkspaceMembership(models.Model):
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("developer", "Developer"),
        ("reviewer", "Reviewer"),
        ("viewer", "Viewer"),
    )

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="workspace_memberships")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="developer")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["workspace", "user"], name="unique_workspace_member"),
        ]


class AuditEvent(models.Model):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_events")
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="audit_events")
    event_type = models.CharField(max_length=80)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class WorkspacePolicy(models.Model):
    workspace = models.OneToOneField(Workspace, on_delete=models.CASCADE, related_name="policy")
    require_approval_for_git = models.BooleanField(default=True)
    require_approval_for_tools = models.BooleanField(default=True)
    require_approval_for_deploy = models.BooleanField(default=True)
    require_tests = models.BooleanField(default=True)
    allow_external_connectors = models.BooleanField(default=False)
    audit_retention_days = models.PositiveIntegerField(default=90)
    updated_at = models.DateTimeField(auto_now=True)


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


class EvaluationTask(models.Model):
    """A reusable prompt/code fixture for measuring local AI quality."""

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="evaluation_tasks")
    name = models.CharField(max_length=160)
    prompt = models.TextField()
    code = models.TextField(blank=True, default="")
    expected_output = models.TextField(blank=True, default="")
    language = models.CharField(max_length=50, default="auto")
    tags = models.CharField(max_length=300, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return self.name


class EvaluationRun(models.Model):
    STATUS_CHOICES = (
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    )

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="evaluation_runs")
    task = models.ForeignKey(EvaluationTask, on_delete=models.CASCADE, related_name="runs")
    model_name = models.CharField(max_length=100)
    response = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="running")
    duration_ms = models.PositiveIntegerField(default=0)
    input_chars = models.PositiveIntegerField(default=0)
    output_chars = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.task.name} · {self.model_name}"
