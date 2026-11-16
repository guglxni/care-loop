"""JSON error envelope: {"error": {"code", "message", "details"}}."""

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int,
        details: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = list(details or [])


class NotFoundError(ApiError):
    def __init__(self, message: str, details: list[str] | None = None) -> None:
        super().__init__("not_found", message, 404, details)


class ValidationError(ApiError):
    def __init__(
        self,
        message: str = "Request validation failed",
        details: list[str] | None = None,
    ) -> None:
        super().__init__("validation_error", message, 400, details)


class UnauthorizedError(ApiError):
    def __init__(self, message: str, details: list[str] | None = None) -> None:
        super().__init__("unauthorized", message, 401, details)


class ConflictError(ApiError):
    def __init__(self, message: str, details: list[str] | None = None) -> None:
        super().__init__("conflict", message, 409, details)


def error_payload(code: str, message: str, details: list[str]) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(err: ApiError):
        return jsonify(error_payload(err.code, err.message, err.details)), err.status

    @app.errorhandler(HTTPException)
    def handle_http(err: HTTPException):
        status = err.code or 500
        code = {
            400: "validation_error",
            401: "unauthorized",
            404: "not_found",
            405: "method_not_allowed",
            409: "conflict",
        }.get(status, "http_error")
        message = err.description or err.name
        return jsonify(error_payload(code, message, [])), status

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        app.logger.exception("Unhandled error")
        details: list[str] = []
        if app.config.get("TESTING"):
            details = [f"{type(err).__name__}: {err}"]
        return jsonify(error_payload("internal_error", "Internal server error", details)), 500
