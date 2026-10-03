"""baseline_schema_and_rls

Revision ID: fbb93c553c44
Revises: 001_rls_base
Create Date: 2026-10-01 22:22:23.395463

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'fbb93c553c44'
down_revision: Union[str, None] = '001_rls_base'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable & Force Row-Level Security (idempotent in Postgres)
    op.execute("ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE invoices FORCE ROW LEVEL SECURITY;")

    # 2. Idempotent Tenant Isolation Policy (Permissive default with explicit WITH CHECK)
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON invoices;")
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON invoices
        FOR ALL
        USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
    """)

    # 3. Least-Privilege Role Grants
    op.execute("GRANT USAGE ON SCHEMA public TO app_user;")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;"
    )
    op.execute(
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app_user;"
    )

def downgrade() -> None:
    # --- Revert Role Default Privileges ---
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE USAGE, SELECT ON SEQUENCES FROM app_user;")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM app_user;")

    # --- Revoke Runtime Privileges ---
    op.execute("REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public FROM app_user;")
    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM app_user;")

    # --- Drop RLS Policy & Disable Security Enforcement ---
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON invoices;")
    op.execute("ALTER TABLE invoices NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE invoices DISABLE ROW LEVEL SECURITY;")

    # --- Drop Tables in Reverse Dependency Order ---
    # op.drop_table('invoices')
    # op.drop_table('tenants')