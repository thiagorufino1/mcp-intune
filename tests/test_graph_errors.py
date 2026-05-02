from mcp_intune.graph.errors import (
    GraphError, ThrottlingError, NotFoundError,
    AuthError, GraphValidationError, ServiceUnavailableError, BetaApiNotAllowedError,
)


def test_throttling_error_stores_retry_after():
    exc = ThrottlingError("throttled", retry_after_seconds=45)
    assert isinstance(exc, GraphError)
    assert exc.retry_after_seconds == 45


def test_throttling_error_default_retry_after():
    exc = ThrottlingError("throttled")
    assert exc.retry_after_seconds == 30


def test_beta_api_not_allowed_error_message():
    exc = BetaApiNotAllowedError("/beta/deviceHealthScripts")
    assert "/beta/deviceHealthScripts" in str(exc)
    assert isinstance(exc, GraphError)


def test_all_errors_inherit_from_graph_error():
    for cls in [ThrottlingError, NotFoundError, AuthError,
                GraphValidationError, ServiceUnavailableError, BetaApiNotAllowedError]:
        exc = cls("msg") if cls not in (ThrottlingError, BetaApiNotAllowedError) else (
            cls("msg", retry_after_seconds=1) if cls == ThrottlingError else cls("/beta/test")
        )
        assert isinstance(exc, GraphError)
