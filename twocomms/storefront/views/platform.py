from pathlib import Path

from django.http import Http404, HttpResponse
from django.contrib.staticfiles import finders

from twocomms.cache_headers import add_cache_headers


def service_worker_script(request):
    sw_path = finders.find("sw.js")
    if isinstance(sw_path, (list, tuple)):
        sw_path = sw_path[0] if sw_path else None
    if not sw_path:
        raise Http404("sw.js not found")

    file_path = Path(sw_path)
    content = file_path.read_text(encoding="utf-8")
    response = HttpResponse(content, content_type="application/javascript; charset=utf-8")
    add_cache_headers(response, str(file_path), request.path)
    response["Service-Worker-Allowed"] = "/"
    return response
