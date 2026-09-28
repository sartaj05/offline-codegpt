from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.index, name="chat_home"),
    path("api/ask-code/", views.ask_code, name="ask_code"),
    path("api/models/", views.model_list, name="model_list"),
    path("api/search/", views.knowledge_search, name="knowledge_search"),
    path("api/execute/", views.execute_code, name="execute_code"),
    path("api/session/<int:session_id>/", views.session_messages, name="session_messages"),
    path("api/session/<int:session_id>/export/", views.export_session, name="export_session"),
]
