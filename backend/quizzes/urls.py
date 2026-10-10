from django.urls import path

from . import views

urlpatterns = [
    path("checks", views.CheckListView.as_view()),
    path("checks/<int:check_id>", views.CheckDetailView.as_view()),
    path("checks/<int:check_id>/start", views.CheckStartView.as_view()),
    path("checks/<int:check_id>/answer", views.CheckAnswerView.as_view()),
    path("leaderboard", views.LeaderboardView.as_view()),
    path("streak", views.StreakView.as_view()),
]
