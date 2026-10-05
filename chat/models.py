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
    runtime = models.CharField(max_length=20, default="ollama")
    server_url = models.URLField(default="http://127.0.0.1:11434", max_length=300)
    default_model = models.CharField(max_length=100, default="qwen2.5-coder:1.5b")
    fallback_model = models.CharField(max_length=100, default="phi3:mini", blank=True)
    temperature = models.FloatField(default=0.2)
    top_p = models.FloatField(default=0.9)
    max_context_chars = models.IntegerField(default=24000)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Ollama settings for {self.user.username}"


class PrivacyPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="privacy_preferences")
    network_lock_enabled = models.BooleanField(default=True)
    store_chat_history = models.BooleanField(default=True)
    redact_secrets = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Privacy preferences for {self.user.username}"


class NetworkLedger(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="network_ledger")
    runtime = models.CharField(max_length=20, default="local")
    method = models.CharField(max_length=12, default="GET")
    endpoint = models.CharField(max_length=400)
    purpose = models.CharField(max_length=80, default="local runtime")
    allowed = models.BooleanField(default=True)
    response_status = models.PositiveIntegerField(default=0)
    request_chars = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class ScheduledTask(models.Model):
    TASK_TYPES = (
        ("reindex", "Re-index project files"),
        ("health", "Runtime health check"),
        ("benchmark", "Model benchmark"),
        ("backup", "Local backup reminder"),
        ("tests", "Run project tests"),
    )

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="scheduled_tasks")
    name = models.CharField(max_length=160)
    task_type = models.CharField(max_length=30, choices=TASK_TYPES, default="health")
    payload = models.JSONField(default=dict, blank=True)
    interval_minutes = models.PositiveIntegerField(default=60)
    next_run_at = models.DateTimeField(default=None, null=True, blank=True)
    enabled = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_result = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["next_run_at", "-id"]


class ModelCapability(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="model_capabilities")
    runtime = models.CharField(max_length=20, default="ollama")
    model_name = models.CharField(max_length=160)
    capabilities = models.JSONField(default=dict)
    hardware = models.JSONField(default=dict)
    source = models.CharField(max_length=30, default="inferred")
    probed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["owner", "runtime", "model_name"], name="unique_model_capability")]
        ordering = ["model_name"]


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


class AgentWorktree(models.Model):
    STATUS_CHOICES = (("active", "Active"), ("merged", "Merged"), ("discarded", "Discarded"))

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="agent_worktrees")
    task = models.OneToOneField(AgentTask, on_delete=models.CASCADE, related_name="worktree")
    branch = models.CharField(max_length=200)
    path = models.CharField(max_length=500)
    base_ref = models.CharField(max_length=200, default="HEAD")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.task.title} · {self.branch}"


class AgentTeam(models.Model):
    STATUS_CHOICES = (
        ("planned", "Planned"),
        ("running", "Running"),
        ("paused", "Paused"),
        ("completed", "Completed"),
        ("blocked", "Blocked"),
    )

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="agent_teams")
    title = models.CharField(max_length=200)
    goal = models.TextField()
    roles = models.JSONField(default=list)
    members = models.JSONField(default=list)
    shared_context = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned")
    logs = models.JSONField(default=list)
    current_member = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class SandboxPolicy(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="sandbox_policy")
    timeout_seconds = models.PositiveIntegerField(default=3)
    memory_mb = models.PositiveIntegerField(default=128)
    output_chars = models.PositiveIntegerField(default=12000)
    require_approval = models.BooleanField(default=True)
    network_blocked = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Sandbox policy for {self.user.username}"


class PermissionProfile(models.Model):
    MODE_CHOICES = (
        ("read_only", "Read only"),
        ("developer", "Developer"),
        ("unrestricted", "Unrestricted"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="permission_profiles")
    name = models.CharField(max_length=80)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="developer")
    is_active = models.BooleanField(default=False)
    require_confirmation = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="unique_user_permission_profile"),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.user.username}: {self.name}"


class AgentJob(models.Model):
    STATUS_CHOICES = (
        ("queued", "Queued"),
        ("running", "Running"),
        ("paused", "Paused"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    )

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="agent_jobs")
    task = models.ForeignKey(AgentTask, on_delete=models.CASCADE, related_name="jobs")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")
    payload = models.JSONField(default=dict)
    checkpoint = models.JSONField(default=dict)
    logs = models.JSONField(default=list)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"Job {self.id} · {self.task.title}"


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


class McpTask(models.Model):
    STATUS_CHOICES = (("queued", "Queued"), ("working", "Working"), ("input_required", "Input required"), ("completed", "Completed"), ("failed", "Failed"), ("cancelled", "Cancelled"))

    task_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mcp_tasks")
    tool_name = models.CharField(max_length=120)
    arguments = models.JSONField(default=dict)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="queued")
    progress = models.PositiveIntegerField(default=0)
    input_requests = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class ToolSecurityPolicy(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tool_security_policies")
    tool_name = models.CharField(max_length=120)
    enabled = models.BooleanField(default=True)
    require_confirmation = models.BooleanField(default=True)
    allowed_roots = models.JSONField(default=list, blank=True)
    network_allowed = models.BooleanField(default=False)
    max_calls_per_minute = models.PositiveIntegerField(default=30)
    signed_manifest_hash = models.CharField(max_length=128, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["owner", "tool_name"], name="unique_tool_security_policy")]


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


class EnterpriseIdentityConfig(models.Model):
    PROVIDER_CHOICES = (
        ("oidc", "OIDC"),
        ("saml", "SAML"),
    )

    workspace = models.OneToOneField(Workspace, on_delete=models.CASCADE, related_name="identity_config")
    provider = models.CharField(max_length=10, choices=PROVIDER_CHOICES, default="oidc")
    issuer_url = models.URLField(blank=True, default="")
    saml_entrypoint_url = models.URLField(blank=True, default="")
    client_id = models.CharField(max_length=200, blank=True, default="")
    allowed_domains = models.CharField(max_length=500, blank=True, default="")
    enforce_sso = models.BooleanField(default=False)
    scim_enabled = models.BooleanField(default=False)
    scim_token_hash = models.CharField(max_length=128, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)


class DirectoryProvisioningEvent(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="provisioning_events")
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="provisioning_events")
    username = models.CharField(max_length=150)
    action = models.CharField(max_length=30)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class SecretVaultItem(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="secret_items")
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=300, blank=True, default="")
    ciphertext = models.TextField()
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["workspace", "name"], name="unique_workspace_secret_name"),
        ]
        ordering = ["name"]


class ExtensionPackage(models.Model):
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="extension_packages")
    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=160)
    version = models.CharField(max_length=40, default="1.0.0")
    description = models.TextField(blank=True, default="")
    permissions = models.JSONField(default=list)
    manifest = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ExtensionInstall(models.Model):
    STATUS_CHOICES = (("installed", "Installed"), ("disabled", "Disabled"))

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="extension_installs")
    package = models.ForeignKey(ExtensionPackage, on_delete=models.CASCADE, related_name="installs")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="installed")
    version = models.CharField(max_length=40)
    previous_version = models.CharField(max_length=40, blank=True, default="")
    approved_permissions = models.JSONField(default=list)
    installed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "package"], name="unique_owner_extension_install"),
        ]


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
    context_summary = models.TextField(blank=True, default="")
    context_message_count = models.PositiveIntegerField(default=0)
    context_updated_at = models.DateTimeField(blank=True, null=True)

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


class DocumentSection(models.Model):
    SECTION_TYPES = (
        ("page", "Page"),
        ("heading", "Heading"),
        ("table", "Table"),
        ("paragraph", "Paragraph"),
    )

    document = models.ForeignKey(KnowledgeDocument, on_delete=models.CASCADE, related_name="sections")
    section_type = models.CharField(max_length=20, choices=SECTION_TYPES, default="paragraph")
    title = models.CharField(max_length=300, blank=True, default="")
    content = models.TextField()
    page_number = models.PositiveIntegerField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        indexes = [models.Index(fields=["document", "page_number"]), models.Index(fields=["section_type"])]


class KnowledgeCollection(models.Model):
    RETRIEVAL_CHOICES = (("hybrid", "Hybrid RAG"), ("full", "Full document"))

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="knowledge_collections")
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    retrieval_mode = models.CharField(max_length=20, choices=RETRIEVAL_CHOICES, default="hybrid")
    documents = models.ManyToManyField(KnowledgeDocument, through="KnowledgeCollectionDocument", related_name="collections")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="unique_owner_collection_name")]
        ordering = ["name"]


class KnowledgeCollectionDocument(models.Model):
    collection = models.ForeignKey(KnowledgeCollection, on_delete=models.CASCADE, related_name="memberships")
    document = models.ForeignKey(KnowledgeDocument, on_delete=models.CASCADE, related_name="collection_memberships")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["collection", "document"], name="unique_collection_document")]


class CodeSymbol(models.Model):
    document = models.ForeignKey(KnowledgeDocument, on_delete=models.CASCADE, related_name="symbols")
    name = models.CharField(max_length=240)
    kind = models.CharField(max_length=40)
    line_start = models.PositiveIntegerField(default=1)
    line_end = models.PositiveIntegerField(default=1)
    signature = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["name"]), models.Index(fields=["kind"])]


class CodeRelation(models.Model):
    RELATION_TYPES = (("references", "References"), ("imports", "Imports"), ("route", "Route"), ("test", "Test"), ("depends_on", "Depends on"))

    document = models.ForeignKey(KnowledgeDocument, on_delete=models.CASCADE, related_name="relations")
    source_name = models.CharField(max_length=240)
    target_name = models.CharField(max_length=240)
    relation_type = models.CharField(max_length=30, choices=RELATION_TYPES, default="references")
    line_number = models.PositiveIntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["source_name"]), models.Index(fields=["target_name"]), models.Index(fields=["relation_type"])]


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
    embedding = models.JSONField(default=list, blank=True)

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


class ScopedMemory(models.Model):
    SCOPE_CHOICES = (("global", "Global"), ("project", "Project"), ("session", "Conversation"), ("workspace", "Workspace"))

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="scoped_memories")
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default="global")
    scope_key = models.CharField(max_length=240, blank=True, default="")
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_enabled = models.BooleanField(default=True)
    source = models.CharField(max_length=40, default="user")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]


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


class EvaluationScore(models.Model):
    run = models.OneToOneField(EvaluationRun, on_delete=models.CASCADE, related_name="score")
    correctness = models.PositiveIntegerField(default=0)
    relevance = models.PositiveIntegerField(default=0)
    completeness = models.PositiveIntegerField(default=0)
    safety = models.PositiveIntegerField(default=0)
    overall = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, default="")
    method = models.CharField(max_length=30, default="automatic")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Score for run {self.run_id}: {self.overall}/100"


class EvaluationRegressionSuite(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="evaluation_regression_suites")
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    task_ids = models.JSONField(default=list)
    baseline = models.JSONField(default=dict)
    last_result = models.JSONField(default=dict)
    last_run_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return self.name
