from django.urls import path
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from accounts.serializers import MeSerializer

from . import onboarding
from .onboarding_serializers import OnboardingPatchSerializer, OnboardingStateSerializer
from .views import StudentView


def _state_response(student, state, note: str = "", stale: bool = False) -> Response:
    data = onboarding.snapshot(student, state, note=note, stale=stale)
    return Response(OnboardingStateSerializer(data).data)


class OnboardingView(StudentView):
    @extend_schema(responses=OnboardingStateSerializer)
    def get(self, request):
        return _state_response(request.user, onboarding.state_for(request.user))

    @extend_schema(request=OnboardingPatchSerializer, responses=OnboardingStateSerializer)
    def patch(self, request):
        serializer = OnboardingPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data
        state, note, stale = onboarding.save_step(
            request.user, body["step"], body.get("data"), body.get("version")
        )
        return _state_response(request.user, state, note=note, stale=stale)


class OnboardingCompleteView(StudentView):
    @extend_schema(request=None, responses=MeSerializer)
    def post(self, request):
        onboarding.complete(request.user)
        return Response(MeSerializer(request.user).data)


urlpatterns = [
    path("onboarding", OnboardingView.as_view()),
    path("onboarding/complete", OnboardingCompleteView.as_view()),
]
