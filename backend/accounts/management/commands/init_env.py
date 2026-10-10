import base64
import secrets
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management.base import BaseCommand

PLACEHOLDER_SECRET = "change-me-to-a-long-random-string"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def vapid_pair() -> tuple[str, str]:
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_numbers().private_value.to_bytes(32, "big")
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return _b64(public), _b64(private)


class Command(BaseCommand):
    help = (
        "Fill in a new Django secret key and Web Push (VAPID) keys. With a path, writes them into "
        "that .env file where they are empty or still the placeholder; without one, prints them."
    )

    def add_arguments(self, parser):
        parser.add_argument("env_file", nargs="?")

    def handle(self, *args, env_file=None, **options):
        public, private = vapid_pair()
        values = {
            "DJANGO_SECRET_KEY": secrets.token_urlsafe(50),
            "VAPID_PUBLIC_KEY": public,
            "VAPID_PRIVATE_KEY": private,
        }
        if env_file is None:
            for key, value in values.items():
                self.stdout.write(f"{key}={value}")
            return
        path = Path(env_file)
        lines = path.read_text().splitlines()
        filled = []
        for i, line in enumerate(lines):
            key, sep, current = line.partition("=")
            if sep and key in values and current.strip() in ("", PLACEHOLDER_SECRET):
                lines[i] = f"{key}={values[key]}"
                filled.append(key)
        path.write_text("\n".join(lines) + "\n")
        if filled:
            self.stdout.write(f"Filled in {', '.join(filled)} in {path}.")
        else:
            self.stdout.write(f"{path} already has a secret key and push keys.")
