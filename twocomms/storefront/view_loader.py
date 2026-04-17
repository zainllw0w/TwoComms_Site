from importlib import import_module, reload


def load_view_attr(module_path: str, attr_name: str):
    """Load a view attribute and retry with module reload if the process is stale."""
    module = import_module(module_path)
    handler = getattr(module, attr_name, None)
    if handler is not None:
        return handler

    reloaded_module = reload(module)
    reloaded_handler = getattr(reloaded_module, attr_name, None)
    if reloaded_handler is not None:
        return reloaded_handler

    raise AttributeError(
        f"Module '{module_path}' has no attribute '{attr_name}' after reload"
    )
