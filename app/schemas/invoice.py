from datetime import datetime
from decimal import Decimal
from enum import Enum
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    VOID = "void"


# Allowed state transitions
VALID_TRANSITIONS: dict[InvoiceStatus, set[InvoiceStatus]] = {
    InvoiceStatus.DRAFT: {InvoiceStatus.ISSUED, InvoiceStatus.VOID},
    InvoiceStatus.ISSUED: {InvoiceStatus.PAID, InvoiceStatus.VOID},
    InvoiceStatus.PAID: set(),  # Terminal state
    InvoiceStatus.VOID: set(),  # Terminal state
}


class InvoiceBase(BaseModel):
    customer_name: str = Field(..., min_length=2, max_length=255)
    amount: Decimal = Field(..., gt=Decimal("0.00"), max_digits=12, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, v: str) -> str:
        return v.upper()


class InvoiceCreate(InvoiceBase):
    pass


class InvoiceStatusUpdate(BaseModel):
    status: InvoiceStatus


class InvoiceResponse(InvoiceBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    status: InvoiceStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)