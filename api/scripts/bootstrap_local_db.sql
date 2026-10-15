-- Run as a Postgres superuser once on a fresh machine:
--   psql -h 127.0.0.1 -d postgres -f scripts/bootstrap_local_db.sql
--
-- Creates the databuddy database and login roles used by Alembic / FastAPI.

SELECT format('CREATE DATABASE %I', 'databuddy')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'databuddy')\gexec

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'databuddy') THEN
    CREATE ROLE databuddy LOGIN PASSWORD 'databuddy' SUPERUSER;
  END IF;
END $$;

GRANT ALL PRIVILEGES ON DATABASE databuddy TO databuddy;
