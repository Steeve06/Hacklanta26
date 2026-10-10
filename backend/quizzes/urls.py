from django.urls import path

from . import views

urlpatterns = [
    path("decks", views.DeckListView.as_view()),
    path("decks/today", views.TodayDeckView.as_view()),
    path("decks/<int:deck_id>", views.DeckDetailView.as_view()),
    path("decks/<int:deck_id>/start", views.DeckStartView.as_view()),
    path("decks/<int:deck_id>/answer", views.DeckAnswerView.as_view()),
    path("decks/<int:deck_id>/finish", views.DeckFinishView.as_view()),
    path("leaderboard", views.LeaderboardView.as_view()),
    path("streak", views.StreakView.as_view()),
]
