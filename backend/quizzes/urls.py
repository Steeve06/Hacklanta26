from django.urls import path

from . import views

urlpatterns = [
    path("decks", views.DeckListView.as_view()),
    path("decks/today", views.TodayDeckView.as_view()),
    path("decks/<int:deck_id>", views.DeckDetailView.as_view()),
    path("decks/<int:deck_id>/review", views.DeckReviewView.as_view()),
    path("streak", views.StreakView.as_view()),
]
