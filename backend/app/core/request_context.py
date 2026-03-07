import contextvars


request_id_var = contextvars.ContextVar("request_id", default=None)
session_id_var = contextvars.ContextVar("session_id", default=None)
canary_var = contextvars.ContextVar("canary", default=None)
user_id_var = contextvars.ContextVar("user_id", default=None)


def set_request_context(request_id: str | None, session_id: str | None) -> None:
    request_id_var.set(request_id)
    session_id_var.set(session_id)


def get_request_id() -> str | None:
    return request_id_var.get()


def get_session_id() -> str | None:
    return session_id_var.get()


def set_canary(canary: bool | None) -> None:
    canary_var.set(None if canary is None else bool(canary))


def get_canary() -> bool | None:
    v = canary_var.get()
    return None if v is None else bool(v)


def set_user_id(user_id: int | None) -> None:
    try:
        user_id_var.set(None if user_id is None else int(user_id))
    except Exception:
        user_id_var.set(None)


def get_user_id() -> int | None:
    v = user_id_var.get()
    try:
        return None if v is None else int(v)
    except Exception:
        return None
