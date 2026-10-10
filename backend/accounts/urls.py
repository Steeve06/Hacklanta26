from django.urls import path

from . import views

urlpatterns = [
    path("auth/login", views.LoginView.as_view()),
    path("auth/refresh", views.RefreshView.as_view()),
    path("auth/logout", views.LogoutView.as_view()),
    path("auth/signup", views.SignupView.as_view()),
    path("auth/password/reset", views.PasswordResetRequestView.as_view()),
    path("auth/password/reset/confirm", views.PasswordResetConfirmView.as_view()),
    path("auth/password/change", views.PasswordChangeView.as_view()),
    path("me", views.MeView.as_view()),
    path("me/profile", views.MeView.as_view()),
    path("me/export", views.ExportView.as_view()),
]
