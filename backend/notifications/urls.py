from django.urls import path

from . import views

urlpatterns = [
    path("notifications", views.InboxView.as_view()),
    path("notifications/read-all", views.ReadAllView.as_view()),
    path("notifications/<int:notification_id>/read", views.ReadView.as_view()),
    path("notifications/<int:notification_id>/action", views.ActionView.as_view()),
    path("push/subscribe", views.PushView.as_view()),
]
