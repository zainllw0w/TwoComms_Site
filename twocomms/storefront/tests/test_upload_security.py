from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from storefront.upload_security import validate_image_file

PNG_PIXEL = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class UploadSecurityTests(SimpleTestCase):
    def test_valid_image_is_accepted_and_renamed(self):
        upload = SimpleUploadedFile("avatar.PNG", PNG_PIXEL, content_type="image/png")

        validated = validate_image_file(upload, field_name="avatar", max_size=1024 * 1024)

        self.assertTrue(validated.name.startswith("avatar-"))
        self.assertTrue(validated.name.endswith(".png"))

    def test_invalid_extension_is_rejected(self):
        upload = SimpleUploadedFile("avatar.txt", PNG_PIXEL, content_type="image/png")

        with self.assertRaises(ValidationError):
            validate_image_file(upload, field_name="avatar")

    def test_invalid_image_payload_is_rejected(self):
        upload = SimpleUploadedFile("avatar.png", b"not-a-real-image", content_type="image/png")

        with self.assertRaises(ValidationError):
            validate_image_file(upload, field_name="avatar")

    def test_oversized_image_is_rejected(self):
        upload = SimpleUploadedFile("avatar.png", PNG_PIXEL, content_type="image/png")

        with self.assertRaises(ValidationError):
            validate_image_file(upload, field_name="avatar", max_size=1)
