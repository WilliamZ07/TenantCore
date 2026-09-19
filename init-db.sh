#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER $APP_DB_USER WITH PASSWORD '$APP_DB_PASSWORD';
    GRANT CONNECT ON DATABASE $POSTGRES_DB TO $APP_DB_USER;
    
    -- Grant read/write usage on public schema, but NO table creation permissions
    GRANT USAGE ON SCHEMA public TO $APP_DB_USER;
    
    -- Default privileges strictly restricted to DML
    ALTER DEFAULT PRIVILEGES IN SCHEMA public 
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO $APP_DB_USER;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public 
        GRANT USAGE, SELECT ON SEQUENCES TO $APP_DB_USER;
EOSQL