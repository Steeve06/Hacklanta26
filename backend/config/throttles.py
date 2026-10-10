from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle


class WriteThrottle(UserRateThrottle):
    scope = "write"

    def allow_request(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return super().allow_request(request, view)


class RegenerateThrottle(UserRateThrottle):
    """Limits the manual "Rebuild schedule" button. Students still in onboarding aren't
    counted: step 5 rebuilds every time they go back and change an answer."""

    scope = "regenerate"

    def allow_request(self, request, view):
        profile = getattr(request.user, "profile", None)
        if profile is not None and not profile.onboarding_done:
            return True
        return super().allow_request(request, view)


class AuthIPThrottle(AnonRateThrottle):
    """Sign-in, sign-up and password reset share one budget per IP address."""

    scope = "auth"


class AuthEmailThrottle(SimpleRateThrottle):
    """The same budget per email address, so one address can't be hammered from many IPs."""

    scope = "auth_email"

    def get_cache_key(self, request, view):
        email = request.data.get("email") if hasattr(request, "data") else None
        if not isinstance(email, str) or not email.strip():
            return None
        return self.cache_format % {"scope": self.scope, "ident": email.strip().lower()}


AUTH_THROTTLES = [AuthIPThrottle, AuthEmailThrottle]
