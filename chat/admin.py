from django.contrib import admin

from .models import (
    LocalModelConfig,
    ChatSession,
    ChatMessage,
    KnowledgeDocument,
    KnowledgeChunk,
    AssistantMemory,
    MessageFeedback,
    TrainingExample,
)


@admin.register(LocalModelConfig)
class LocalModelConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "display_name", "is_default", "is_active", "temperature")
    search_fields = ("name", "display_name")


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("title", "model_name", "is_pinned", "created_at", "updated_at")
    search_fields = ("title", "model_name")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("session", "role", "filename", "model_name", "created_at")
    search_fields = ("content", "filename", "model_name")
    list_filter = ("role", "model_name")


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "filename", "language", "source_type", "file_size_bytes", "uploaded_at", "is_active")
    search_fields = ("title", "filename", "original_text")
    list_filter = ("language", "source_type", "is_active")


@admin.register(KnowledgeChunk)
class KnowledgeChunkAdmin(admin.ModelAdmin):
    list_display = ("document", "chunk_index", "language", "created_at")
    search_fields = ("content", "summary", "keywords")
    list_filter = ("language",)


@admin.register(AssistantMemory)
class AssistantMemoryAdmin(admin.ModelAdmin):
    list_display = ("title", "memory_type", "importance", "is_active", "created_at")
    search_fields = ("title", "content")
    list_filter = ("memory_type", "importance", "is_active")


@admin.register(MessageFeedback)
class MessageFeedbackAdmin(admin.ModelAdmin):
    list_display = ("message", "feedback_type", "created_at")
    search_fields = ("correction_text",)
    list_filter = ("feedback_type",)


@admin.register(TrainingExample)
class TrainingExampleAdmin(admin.ModelAdmin):
    list_display = ("instruction", "status", "created_at")
    search_fields = ("instruction", "input_text", "expected_output")
    list_filter = ("status",)