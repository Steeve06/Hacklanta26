from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme


class SessionJWTScheme(SimpleJWTScheme):
    target_class = "accounts.auth.SessionJWTAuthentication"
