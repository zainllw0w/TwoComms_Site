from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from storefront.utm_utils import get_geolocation


EMPTY_GEOLOCATION = {
    "country": None,
    "country_name": None,
    "city": None,
    "region": None,
    "timezone": None,
}


class GeoIPFailSoftTests(SimpleTestCase):
    @override_settings(GEOIP_PATH=None)
    @patch("django.contrib.gis.geoip2.GeoIP2")
    def test_missing_path_skips_geoip_constructor_without_warning(self, geoip):
        with patch("storefront.utm_utils.logger.warning") as warning:
            result = get_geolocation("8.8.8.8")

        self.assertEqual(result, EMPTY_GEOLOCATION)
        geoip.assert_not_called()
        warning.assert_not_called()

    def test_existing_database_path_preserves_geoip_lookup(self):
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "GeoLite2-City.mmdb"
            database.touch()
            fake_geoip = type("FakeGeoIP", (), {})()
            fake_geoip.city = lambda _ip: {
                "country_code": "UA",
                "country_name": "Ukraine",
                "city": "Kyiv",
                "region": "Kyiv",
                "time_zone": "Europe/Kyiv",
            }
            fake_geoip.country = lambda _ip: None

            with override_settings(GEOIP_PATH=temp_dir):
                with patch(
                    "django.contrib.gis.geoip2.GeoIP2", return_value=fake_geoip
                ) as geoip:
                    result = get_geolocation("8.8.8.8")

        self.assertEqual(result["country"], "UA")
        self.assertEqual(result["city"], "Kyiv")
        geoip.assert_called_once_with(path=temp_dir)

    def test_empty_database_directory_skips_geoip_constructor_without_warning(self):
        with TemporaryDirectory() as temp_dir:
            with override_settings(GEOIP_PATH=temp_dir):
                with patch("django.contrib.gis.geoip2.GeoIP2") as geoip:
                    with patch("storefront.utm_utils.logger.warning") as warning:
                        result = get_geolocation("8.8.8.8")

        self.assertEqual(result, EMPTY_GEOLOCATION)
        geoip.assert_not_called()
        warning.assert_not_called()
