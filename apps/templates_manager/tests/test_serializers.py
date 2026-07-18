from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from apps.templates_manager.serializers import EmailTemplateSerializer

User = get_user_model()


class EmailTemplateSerializerPlaceholderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tpl_user", password="x")
        self.factory = RequestFactory()
        self.request = self.factory.post("/api/templates/")
        self.request.user = self.user

    def _serializer(self, body: str, subject: str = "Hello {{name}}"):
        return EmailTemplateSerializer(
            data={
                "name": "Underscore Template",
                "subject": subject,
                "description": "Test",
                "body": body,
            },
            context={"request": self.request},
        )

    def test_accepts_underscore_placeholders(self):
        serializer = self._serializer(
            "Please reply to {{Your_Contact_Info}} soon.",
            subject="Hello {{Your_Contact_Info}}",
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_spaced_placeholders_only(self):
        serializer = self._serializer(
            "Please reply to {{Your Contact Info}} soon.",
            subject="Hello {{Your Contact Info}}",
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("body", serializer.errors)

    def test_rejects_body_without_placeholders(self):
        serializer = self._serializer("No placeholders here.")
        self.assertFalse(serializer.is_valid())
        self.assertIn("body", serializer.errors)
