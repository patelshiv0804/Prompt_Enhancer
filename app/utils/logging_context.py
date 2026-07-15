import contextvars
from typing import Optional

correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)

def get_correlation_id() -> Optional[str]:
    return correlation_id_var.get()

def set_correlation_id(val: Optional[str]) -> None:
    correlation_id_var.set(val)
