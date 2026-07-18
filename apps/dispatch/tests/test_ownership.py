from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import ClerkIdentity
from apps.dispatch.models import DispatchJob
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
class DispatchOwnershipTests(TestCase):
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
        self.job = DispatchJob.objects.create(
            owner=self.owner,
            template=self.template,
            total_recipients=1,
            status=DispatchJob.Status.PENDING,
        )

    def test_job_detail_requires_auth(self):
        response = self.client.get(f"/api/dispatch/jobs/{self.job.id}/")
        self.assertEqual(response.status_code, 401)

    def test_cross_user_job_detail_is_404(self):
        with _auth_as(self.other):
            response = self.client.get(f"/api/dispatch/jobs/{self.job.id}/")
        self.assertEqual(response.status_code, 404)

    def test_owner_can_fetch_job(self):
        with _auth_as(self.owner):
            response = self.client.get(f"/api/dispatch/jobs/{self.job.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job"]["id"], str(self.job.id))

    def test_generate_csv_rejects_foreign_template(self):
        with _auth_as(self.other):
            response = self.client.post(
                "/api/dispatch/generate-csv/",
                {"template_id": str(self.template.id)},
                format="json",
            )
        self.assertEqual(response.status_code, 404)
