class DataLoadError(RuntimeError):
    """Processed public data could not be loaded safely."""


class RouteNotFoundError(RuntimeError):
    """No valid path exists for the selected places and preferences."""

