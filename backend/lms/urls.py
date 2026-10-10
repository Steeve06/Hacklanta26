from django.urls import path

from . import views

urlpatterns = [
    path("courses", views.CourseListView.as_view()),
    path("courses/<int:course_id>", views.CourseDetailView.as_view()),
    path("courses/<int:course_id>/chapters", views.ChapterListView.as_view()),
    path("courses/<int:course_id>/assessments", views.AssessmentListView.as_view()),
    path("courses/<int:course_id>/syllabus", views.SyllabusView.as_view()),
    path("chapters/<int:chapter_id>", views.ChapterDetailView.as_view()),
    path("chapters/<int:chapter_id>/complete", views.ChapterCompleteView.as_view()),
    path("assessments/<int:assessment_id>", views.AssessmentDetailView.as_view()),
    path("assessments/<int:assessment_id>/questions", views.AssessmentQuestionsView.as_view()),
    path("assessments/<int:assessment_id>/submissions", views.SubmissionCreateView.as_view()),
    path("assessments/<int:assessment_id>/posts", views.DiscussionView.as_view()),
    path("assessments/<int:assessment_id>/attempts", views.QuizAttemptStartView.as_view()),
    path("assessments/<int:assessment_id>/overrides", views.OverrideView.as_view()),
    path("assessments/<int:assessment_id>/excuse", views.ExcuseView.as_view()),
    path("assessments/<int:assessment_id>/roster", views.RosterView.as_view()),
    path("attempts/<int:attempt_id>", views.QuizAttemptView.as_view()),
    path("attempts/<int:attempt_id>/submit", views.QuizAttemptSubmitView.as_view()),
    path("submissions/<int:submission_id>/file", views.SubmissionFileView.as_view()),
    path("submissions/<int:submission_id>/score", views.SubmissionScoreView.as_view()),
]
