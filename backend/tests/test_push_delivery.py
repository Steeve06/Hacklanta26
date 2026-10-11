"""Real Web Push delivery, end to end, with a local push service standing in for FCM/APNs.

Nothing is mocked: pywebpush encrypts and signs exactly as in production and POSTs to the
subscription's endpoint. The fake push service checks the VAPID signature the way Google and
Apple do, and decrypts the payload with the keys a browser would hold."""

import base64
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import http_ece
import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from accounts.management.commands.init_env import vapid_pair
from notifications.delivery import send_to_devices
from notifications.models import Notification, PushSubscription

from .factories import StudentFactory

pytestmark = pytest.mark.django_db


def b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def b64e(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


class PushService:
    """Accepts pushes on /push/<id> and records them; /gone/<id> answers 410 like an expired
    subscription."""

    def __init__(self):
        received = self.received = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                received.append({"path": self.path, "headers": dict(self.headers), "body": body})
                self.send_response(410 if self.path.startswith("/gone") else 201)
                self.end_headers()

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.origin = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


class Browser:
    """The keys a browser creates when it subscribes to push."""

    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.auth = os.urandom(16)
        public = self.key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        self.keys = {"p256dh": b64e(public), "auth": b64e(self.auth)}

    def decrypt(self, body: bytes) -> dict:
        plain = http_ece.decrypt(
            body, private_key=self.key, auth_secret=self.auth, version="aes128gcm"
        )
        return json.loads(plain)


def verify_vapid(authorization: str, public_key_b64: str, audience: str) -> dict:
    """What the push service does before accepting a message."""
    scheme, _, params = authorization.partition(" ")
    assert scheme == "vapid"
    parts = dict(p.strip().split("=", 1) for p in params.split(","))
    assert parts["k"] == public_key_b64
    header, claims, signature = parts["t"].split(".")
    raw = b64d(signature)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), b64d(public_key_b64))
    try:
        public.verify(der, f"{header}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:  # pragma: no cover - the assertion message is the point
        raise AssertionError("VAPID signature does not verify") from None
    payload = json.loads(b64d(claims))
    assert payload["aud"] == audience
    assert payload["exp"] > time.time()
    return payload


@pytest.fixture
def push_service():
    service = PushService()
    yield service
    service.close()


@pytest.fixture
def vapid(settings):
    public, private = vapid_pair()
    settings.VAPID_PUBLIC_KEY, settings.VAPID_PRIVATE_KEY = public, private
    settings.VAPID_SUBJECT = "mailto:team@leon.test"
    return public


def test_a_reminder_reaches_the_device_signed_and_readable(push_service, vapid):
    student = StudentFactory()
    browser = Browser()
    PushSubscription.objects.create(
        user=student, endpoint=f"{push_service.origin}/push/abc", keys=browser.keys
    )
    payload = json.dumps({"title": "Leon · Test", "body": "Push works.", "url": "/pulse/today"})

    assert send_to_devices(student, payload, urgent=True) == 1

    [message] = push_service.received
    headers = {k.lower(): v for k, v in message["headers"].items()}
    assert headers["content-encoding"] == "aes128gcm"
    assert headers["urgency"] == "high"
    assert int(headers["ttl"]) == 12 * 60 * 60
    claims = verify_vapid(headers["authorization"], vapid, push_service.origin)
    assert claims["sub"] == "mailto:team@leon.test"
    assert browser.decrypt(message["body"]) == json.loads(payload)


def test_teacher_post_arrives_as_a_push_the_browser_can_read(
    push_service, vapid, django_capture_on_commit_callbacks
):
    from datetime import timedelta

    from django.utils import timezone

    from lms.models import Enrollment
    from lms.registration import Registration, register_course

    from .factories import TermFactory
    from .test_teaching import client_for, without_quiet_hours

    TermFactory()
    course = register_course(Registration("CS 201", "Data Structures", "ada@school.edu"))
    student = StudentFactory()
    without_quiet_hours(student)
    Enrollment.objects.get_or_create(user=student, course=course)
    browser = Browser()
    PushSubscription.objects.create(
        user=student, endpoint=f"{push_service.origin}/push/maya", keys=browser.keys
    )
    now = timezone.now()
    with django_capture_on_commit_callbacks(execute=True):
        response = client_for(course.instructor).post(
            f"/api/v1/courses/{course.id}/assessments",
            {
                "type": "discussion", "title": "Hash collisions", "instructions": "Discuss.",
                "open_at": (now - timedelta(hours=1)).isoformat(),
                "due_at": (now + timedelta(days=4)).isoformat(),
            },
            format="json",
        )  # fmt: skip
    assert response.status_code == 201

    [message] = push_service.received
    headers = {k.lower(): v for k, v in message["headers"].items()}
    verify_vapid(headers["authorization"], vapid, push_service.origin)
    shown = browser.decrypt(message["body"])
    assert shown["title"] == "Leon · New in your course"
    assert shown["body"] == "New discussion in CS 201: Hash collisions"
    assert shown["url"] == f"/lms/courses/{course.id}/assignments/{response.data['id']}"
    assert [a["action"] for a in shown["actions"]] == ["open"]
    assert Notification.objects.get(student=student).channels == ["inapp", "push"]


def test_expired_subscription_is_removed(push_service, vapid):
    student = StudentFactory()
    PushSubscription.objects.create(
        user=student, endpoint=f"{push_service.origin}/gone/old", keys=Browser().keys
    )
    assert send_to_devices(student, json.dumps({"title": "x"})) == 0
    assert len(push_service.received) == 1
    assert not PushSubscription.objects.filter(user=student).exists()


def test_push_test_button_reaches_every_device(push_service, vapid):
    from .test_teaching import client_for

    student = StudentFactory()
    phone, laptop = Browser(), Browser()
    for name, browser in (("phone", phone), ("laptop", laptop)):
        PushSubscription.objects.create(
            user=student, endpoint=f"{push_service.origin}/push/{name}", keys=browser.keys
        )
    response = client_for(student).post("/api/v1/push/test")
    assert response.status_code == 200 and response.data["sent"] == 2
    by_path = {m["path"]: m["body"] for m in push_service.received}
    assert phone.decrypt(by_path["/push/phone"])["body"].startswith("Push works.")
    assert laptop.decrypt(by_path["/push/laptop"])["body"].startswith("Push works.")
