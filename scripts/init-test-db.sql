-- Create test database for running tests against PostgreSQL.
-- Mounted into postgres container's /docker-entrypoint-initdb.d/ for auto-creation.
-- Uses the same user as the dev database.

SELECT 'CREATE DATABASE inxr2_test OWNER inxr2_user'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'inxr2_test')\gexec
