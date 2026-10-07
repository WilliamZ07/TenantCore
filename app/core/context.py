from contextvars import ContextVar
from typing import Optional
import uuid

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
tenant_id_ctx: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)


def get_request_id() -> str:
    return request_id_ctx.get()


def set_request_id(request_id: str) -> None:
    request_id_ctx.set(request_id)


def get_tenant_id() -> Optional[str]:
    return tenant_id_ctx.get()


def set_tenant_id(tenant_id: str) -> None:
    tenant_id_ctx.set(tenant_id)