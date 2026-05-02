class GraphError(Exception):
    pass


class ThrottlingError(GraphError):
    def __init__(self, message: str, retry_after_seconds: int = 30) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class NotFoundError(GraphError):
    pass


class AuthError(GraphError):
    pass


class GraphValidationError(GraphError):
    pass


class ServiceUnavailableError(GraphError):
    pass


class BetaApiNotAllowedError(GraphError):
    def __init__(self, path: str) -> None:
        super().__init__(f"Beta API not allowed: {path}. Set ALLOW_BETA_APIS=true to enable.")
        self.path = path
