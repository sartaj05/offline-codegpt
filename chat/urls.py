from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.index, name="chat_home"),
    path("api/ask-code/", views.ask_code, name="ask_code"),
    path("api/models/", views.model_list, name="model_list"),
    path("api/sessions/", views.session_list, name="session_list"),
    path("api/session/<int:session_id>/manage/", views.manage_session, name="manage_session"),
    path("api/search/", views.knowledge_search, name="knowledge_search"),
    path("api/project/", views.project_documents, name="project_documents"),
    path("api/project/<int:document_id>/", views.project_document_delete, name="project_document_delete"),
    path("api/project/<int:document_id>/content/", views.project_document_content, name="project_document_content"),
    path("api/project/<int:document_id>/reindex/", views.project_document_reindex, name="project_document_reindex"),
    path("api/execute/", views.execute_code, name="execute_code"),
    path("api/analyze/", views.quality_analyze, name="quality_analyze"),
    path("api/patch/preview/", views.preview_patch, name="preview_patch"),
    path("api/session/<int:session_id>/", views.session_messages, name="session_messages"),
    path("api/session/<int:session_id>/revisions/", views.session_revisions, name="session_revisions"),
    path("api/session/<int:session_id>/export/", views.export_session, name="export_session"),
]
