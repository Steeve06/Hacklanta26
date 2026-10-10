from django.urls import path

from . import views

urlpatterns = [
    path("conversation", views.ConversationView.as_view()),
    path("messages", views.MessageCreateView.as_view()),
    path("messages/<int:message_id>/confirm", views.ConfirmView.as_view()),
    path("messages/<int:message_id>/decline", views.DeclineView.as_view()),
]
