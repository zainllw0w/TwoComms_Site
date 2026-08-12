import json

from django.test import TestCase, override_settings

from storefront.seo_utils import StructuredDataGenerator


@override_settings(SITE_BASE_URL="https://twocomms.shop")
class MemberProgramSchemaTests(TestCase):
    def test_unverified_loyalty_program_is_not_published_as_member_program(self):
        schema = StructuredDataGenerator.generate_organization_schema()
        serialized = json.dumps(schema, ensure_ascii=False)

        self.assertNotIn("hasMemberProgram", schema)
        self.assertNotIn("MemberProgramTierBenefit", serialized)
