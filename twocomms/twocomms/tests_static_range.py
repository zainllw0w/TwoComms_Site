import io
import tempfile
from pathlib import Path
from wsgiref.util import setup_testing_defaults

from django.conf import settings
from django.core.handlers.wsgi import WSGIHandler
from django.test import SimpleTestCase, override_settings


STATIC_MIDDLEWARE = next(
    middleware
    for middleware in settings.MIDDLEWARE
    if middleware.endswith("WhiteNoiseMiddleware")
)


class _FilenoFileWrapper:
    calls = 0

    def __init__(self, filelike, block_size=8192):
        type(self).calls += 1
        self.filelike = filelike
        self.block_size = block_size
        filelike.fileno()

    def __iter__(self):
        return iter(lambda: self.filelike.read(self.block_size), b"")

    def close(self):
        self.filelike.close()


class StaticRangeLsapiTests(SimpleTestCase):
    static_path = "/static/range-test.bin"
    content = b"0123456789abcdef"

    def _request_static(self, static_root, *, range_header=None):
        environ = {}
        setup_testing_defaults(environ)
        environ.update(
            PATH_INFO=self.static_path,
            REQUEST_METHOD="GET",
            SERVER_NAME="testserver",
            SERVER_PORT="80",
            **{"wsgi.input": io.BytesIO(), "wsgi.file_wrapper": _FilenoFileWrapper},
        )
        if range_header is not None:
            environ["HTTP_RANGE"] = range_header

        captured = {}

        def start_response(status, headers, exc_info=None):
            captured["status"] = status
            captured["headers"] = dict(headers)

        _FilenoFileWrapper.calls = 0
        with override_settings(
            ALLOWED_HOSTS=["testserver"],
            MIDDLEWARE=[STATIC_MIDDLEWARE],
            STATIC_ROOT=static_root,
            STATIC_URL="/static/",
            WHITENOISE_AUTOREFRESH=False,
            WHITENOISE_USE_FINDERS=False,
        ):
            response = WSGIHandler()(environ, start_response)
            try:
                body = b"".join(response)
            finally:
                if hasattr(response, "close"):
                    response.close()

        return captured, body, _FilenoFileWrapper.calls

    def test_range_response_bypasses_fileno_file_wrapper(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "range-test.bin").write_bytes(self.content)

            captured, body, wrapper_calls = self._request_static(
                directory,
                range_header="bytes=2-5",
            )

        self.assertEqual(captured["status"], "206 Partial Content")
        self.assertEqual(captured["headers"]["Content-Range"], "bytes 2-5/16")
        self.assertEqual(captured["headers"]["Content-Length"], "4")
        self.assertEqual(body, b"2345")
        self.assertEqual(wrapper_calls, 0)

    def test_regular_static_get_keeps_file_wrapper_fast_path(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "range-test.bin").write_bytes(self.content)

            captured, body, wrapper_calls = self._request_static(directory)

        self.assertEqual(captured["status"], "200 OK")
        self.assertEqual(body, self.content)
        self.assertEqual(wrapper_calls, 1)
