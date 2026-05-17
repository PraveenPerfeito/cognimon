import logging

audit_logger = logging.getLogger("app.audit")


def log_auth_audit_event(event: str, **fields: str) -> None:
    serialized_fields = " ".join(
        f"{key}={value}"
        for key, value in sorted(fields.items())
    )
    message = f"audit_event={event}"
    if serialized_fields:
        message = f"{message} {serialized_fields}"
    audit_logger.info(message)
