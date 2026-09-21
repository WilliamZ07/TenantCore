import os
import sys

# Ensure project root (TenantCore) is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
import hashlib
import uuid
from decimal import Decimal
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings
from app.models.tenant import Tenant
from app.models.invoice import Invoice

# Connect to database using app_user credentials from settings
engine = create_async_engine(settings.async_database_uri, echo=False)
Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


def get_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def run_verification():
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    print("\n--- 1. Seeding Tenants and Invoices ---")
    async with Session() as session:
        async with session.begin():
            # Seed tenant parents first
            t1 = Tenant(id=tenant_a_id, name="Acme Corp", api_key_hash=get_hash("acme_secret"))
            t2 = Tenant(id=tenant_b_id, name="Stark Industries", api_key_hash=get_hash("stark_secret"))
            session.add_all([t1, t2])
            await session.flush()

            # Set transaction-local context for Tenant A via set_config
            await session.execute(
                text("SELECT set_config('app.current_tenant', :id, true)"),
                {"id": str(tenant_a_id)},
            )
            inv_a = Invoice(
                tenant_id=tenant_a_id,
                customer_name="Customer A1",
                amount=Decimal("1500.00"),
            )
            session.add(inv_a)
            await session.flush()

            # Set transaction-local context for Tenant B via set_config
            await session.execute(
                text("SELECT set_config('app.current_tenant', :id, true)"),
                {"id": str(tenant_b_id)},
            )
            inv_b = Invoice(
                tenant_id=tenant_b_id,
                customer_name="Customer B1",
                amount=Decimal("9900.00"),
            )
            session.add(inv_b)

    print("Seeding operations successfully executed.")

    print("\n--- 2. Testing Isolation for Tenant A ---")
    async with Session() as session:
        async with session.begin():
            # Inject context token strictly into this transaction
            await session.execute(
                text("SELECT set_config('app.current_tenant', :id, true)"),
                {"id": str(tenant_a_id)},
            )
            
            # Explicit unconstrained query (Zero Application-Layer Filters)
            result = await session.execute(select(Invoice))
            invoices = result.scalars().all()
            
            print(f"Tenant A context isolated {len(invoices)} row record(s).")
            for inv in invoices:
                print(f" -> Found invoice ID: {inv.id} for customer: {inv.customer_name} (Tenant ID: {inv.tenant_id})")
                assert inv.tenant_id == tenant_a_id, "CRITICAL ERROR: Data Bleeding Event Detected!"

    print("\n--- 3. Testing Context without app.current_tenant (Zero-Trust Assertion) ---")
    async with Session() as session:
        async with session.begin():
            # Executing query without injecting session properties
            result = await session.execute(select(Invoice))
            invoices = result.scalars().all()
            print(f"Unauthenticated transactional channel surfaced {len(invoices)} row record(s).")
            assert len(invoices) == 0, "CRITICAL ERROR: Structural RLS Bypass Detected!"

    print("\n[SUCCESS] PostgreSQL Storage-Level RLS isolated resources flawlessly across independent contexts.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_verification())