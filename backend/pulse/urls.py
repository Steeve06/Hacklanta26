from django.urls import path

from . import views

urlpatterns = [
    path("availability", views.AvailabilityView.as_view()),
    path("blackouts", views.BlackoutListView.as_view()),
    path("blackouts/<int:blackout_id>", views.BlackoutDetailView.as_view()),
    path("schedules/generate", views.GenerateView.as_view()),
    path("jobs/latest", views.LatestJobView.as_view()),
    path("jobs/<int:job_id>", views.JobView.as_view()),
    path("jobs/<int:job_id>/cancel", views.JobCancelView.as_view()),
    path("schedule", views.ScheduleView.as_view()),
    path("sessions/<int:session_id>", views.SessionView.as_view()),
    path("sessions/<int:session_id>/reschedule", views.SessionRescheduleView.as_view()),
]
