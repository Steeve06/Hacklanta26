from django.urls import path

from . import views

urlpatterns = [
    path("quizzes", views.QuizListView.as_view()),
    path("quizzes/<int:quiz_id>", views.QuizDetailView.as_view()),
    path("quizzes/<int:quiz_id>/start", views.QuizStartView.as_view()),
    path("quizzes/<int:quiz_id>/submit", views.QuizSubmitView.as_view()),
    path("streak", views.StreakView.as_view()),
]
