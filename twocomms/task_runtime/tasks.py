from django.tasks import task

from .runtime import register_task


@task(backend="durable")
def no_send_canary(*, marker):
    """Exercise durable execution without provider calls or domain writes."""
    return {"external_io": False, "marker": str(marker)}


register_task(no_send_canary.module_path, no_send_canary)
