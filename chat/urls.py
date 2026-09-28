from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="chat_home"),
    path("api/ask-code/", views.ask_code, name="ask_code"),
    path("api/models/", views.model_list, name="model_list"),
    path("api/search/", views.knowledge_search, name="knowledge_search"),
    path("api/session/<int:session_id>/", views.session_messages, name="session_messages"),
]
