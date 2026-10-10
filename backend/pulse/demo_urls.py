from django.urls import path

from . import demo

urlpatterns = [
    path("students", demo.DemoStudentsView.as_view()),
    path("scan-notifications", demo.DemoScanView.as_view()),
    path("replan/<int:student_id>", demo.DemoReplanView.as_view()),
    path("time-travel", demo.DemoTimeTravelView.as_view()),
]
