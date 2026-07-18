from django.test import TestCase

from apps.core.utils import extract_placeholders, fill_template


class ExtractPlaceholdersTests(TestCase):
    def test_word_placeholders(self):
        self.assertEqual(
            extract_placeholders("Hello {{name}}, order {{order_id}}."),
            ["name", "order_id"],
        )

    def test_underscore_placeholders(self):
        self.assertEqual(
            extract_placeholders(
                "Contact {{Your_Contact_Info}} or {{YourContactInfo}}."
            ),
            ["Your_Contact_Info", "YourContactInfo"],
        )

    def test_rejects_spaced_placeholders(self):
        self.assertEqual(
            extract_placeholders("Contact {{Your Contact Info}} please."),
            [],
        )

    def test_strips_inner_edge_whitespace(self):
        self.assertEqual(
            extract_placeholders("Hi {{  order_id  }}"),
            ["order_id"],
        )

    def test_deduplicates_preserving_order(self):
        self.assertEqual(
            extract_placeholders(
                "{{name}} then {{Your_Contact_Info}} then {{name}}"
            ),
            ["name", "Your_Contact_Info"],
        )


class FillTemplateTests(TestCase):
    def test_fills_underscore_placeholder(self):
        body = "Reach us at {{Your_Contact_Info}}."
        result = fill_template(
            body, {"Your_Contact_Info": "support@example.com"}
        )
        self.assertEqual(result, "Reach us at support@example.com.")

    def test_fills_with_spaces_around_key(self):
        body = "Reach us at {{  Your_Contact_Info  }}."
        result = fill_template(
            body, {"Your_Contact_Info": "support@example.com"}
        )
        self.assertEqual(result, "Reach us at support@example.com.")

    def test_fills_mixed_placeholders(self):
        body = "Hi {{name}}, code {{order_id}}."
        result = fill_template(body, {"name": "Alice", "order_id": "42"})
        self.assertEqual(result, "Hi Alice, code 42.")
