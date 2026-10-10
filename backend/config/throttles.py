from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class WriteThrottle(UserRateThrottle):
    scope = "write"

    def allow_request(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return super().allow_request(request, view)


class LoginThrottle(AnonRateThrottle):
    scope = "login"


class RegenerateThrottle(UserRateThrottle):
    scope = "regenerate"
