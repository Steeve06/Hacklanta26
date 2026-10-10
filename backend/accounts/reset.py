"""Password reset links: single use (the token hashes the current password) and valid for
PASSWORD_RESET_TIMEOUT seconds. Locally the email prints to the server console."""

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .models import User


def reset_link(user: User) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?uid={uid}&token={token}"


def send_reset_email(user: User) -> None:
    minutes = settings.PASSWORD_RESET_TIMEOUT // 60
    send_mail(
        subject="Reset your Leon password",
        message=(
            f"Hi {user.first_name},\n\n"
            f"Use this link to choose a new password. It works once and expires in {minutes} "
            f"minutes:\n\n{reset_link(user)}\n\n"
            "If you didn't ask for this, you can ignore this email."
        ),
        from_email=None,
        recipient_list=[user.email],
    )


def user_from_reset_link(uid: str, token: str) -> User | None:
    try:
        pk = int(force_str(urlsafe_base64_decode(uid)))
    except (TypeError, ValueError, OverflowError):
        return None
    user = User.objects.filter(pk=pk, is_active=True).first()
    if user is None or not default_token_generator.check_token(user, token):
        return None
    return user
