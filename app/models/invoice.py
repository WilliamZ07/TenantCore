import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), server_default="USD", nullable=False)
    status: Mapped[str] = mapped_column(String(50), server_default="PENDING", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("TIMEZONE('utc', NOW())"), nullable=False
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="invoices")