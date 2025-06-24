-- Initialize Plytix-Webflow Integration Database
-- This script runs when the PostgreSQL container starts for the first time

-- Create additional database for testing if needed
CREATE DATABASE IF NOT EXISTS integration_test_db;

-- Create user for the application (if needed)
-- DO $$ BEGIN
--     CREATE USER plytix_user WITH PASSWORD 'secure_password';
-- EXCEPTION WHEN duplicate_object THEN
--     NULL; -- User already exists
-- END $$;

-- Grant permissions
-- GRANT ALL PRIVILEGES ON DATABASE integration_db TO plytix_user;
-- GRANT ALL PRIVILEGES ON DATABASE integration_test_db TO plytix_user;

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Plytix-Webflow Integration database initialized successfully';
END $$;