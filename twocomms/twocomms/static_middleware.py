from whitenoise.middleware import WhiteNoiseMiddleware
from whitenoise.responders import SlicedFile


class LsapiSafeWhiteNoiseMiddleware(WhiteNoiseMiddleware):
    """Keep ranged static responses away from LSAPI's fileno-only wrapper."""

    @staticmethod
    def serve(static_file, request):
        response = WhiteNoiseMiddleware.serve(static_file, request)
        if isinstance(response.file_to_stream, SlicedFile):
            response.file_to_stream = None
        return response
