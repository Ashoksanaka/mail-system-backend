from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import ClerkIdentity
from apps.templates_manager.models import EmailTemplate

User = get_user_model()


def _auth_as(user):
    payload = {"sub": user.clerk_identity.clerk_user_id}

    def _authenticate(request):
        return (user, payload)

    return patch(
        "apps.accounts.authentication.ClerkAuthentication.authenticate",
        side_effect=_authenticate,
    )


@override_settings(
    CLERK_SECRET_KEY="sk_test_dummy",
    CLERK_JWT_KEY="",
    CLERK_AUTHORIZED_PARTIES=["http://localhost:3000"],
)
class TemplateOwnershipTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="owner", password="x")
        self.owner.set_unusable_password()
        self.owner.save()
        ClerkIdentity.objects.create(
            user=self.owner, clerk_user_id="user_owner", email="owner@example.com"
        )

        self.other = User.objects.create_user(username="other", password="x")
        self.other.set_unusable_password()
        self.other.save()
        ClerkIdentity.objects.create(
            user=self.other, clerk_user_id="user_other", email="other@example.com"
        )

        self.template = EmailTemplate.objects.create(
            owner=self.owner,
            name="Welcome",
            subject="Hi {{name}}",
            description="Welcome email",
            body="Hello {{name}}",
        )

    def test_unauthenticated_list_is_401(self):
        response = self.client.get("/api/templates/")
        self.assertEqual(response.status_code, 401)

    def test_owner_can_list_own_templates_only(self):
        EmailTemplate.objects.create(
            owner=self.other,
            name="Other",
            subject="Hi {{name}}",
            description="Other",
            body="Hello {{name}}",
        )
        with _auth_as(self.owner):
            response = self.client.get("/api/templates/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["name"], "Welcome")

    def test_cross_user_detail_is_404(self):
        with _auth_as(self.other):
            response = self.client.get(f"/api/templates/{self.template.id}/")
        self.assertEqual(response.status_code, 404)

    def test_create_assigns_owner(self):
        with _auth_as(self.owner):
            response = self.client.post(
                "/api/templates/",
                {
                    "name": "Billing",
                    "subject": "Invoice {{id}}",
                    "description": "Billing notice",
                    "body": "Invoice {{id}}",
                },
                format="json",
            )
        self.assertEqual(response.status_code, 201)
        created = EmailTemplate.objects.get(id=response.json()["id"])
        self.assertEqual(created.owner_id, self.owner.id)
