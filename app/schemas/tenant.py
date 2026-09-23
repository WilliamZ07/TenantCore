import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class TenantBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Organization or company name")


class TenantCreate(TenantBase):
    pass


class TenantResponse(TenantBase):
    id: uuid.UUID
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TenantProvisionResponse(TenantResponse):
    """
    Returned strictly once upon tenant registration.
    Contains the raw plaintext key that the client must store securely.
    """
    api_key: str = Field(..., description="Plaintext secret key. Never shown again.")