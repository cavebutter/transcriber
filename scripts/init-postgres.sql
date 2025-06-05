-- PostgreSQL initialization script for RealRecap
-- This script runs when the PostgreSQL container starts for the first time

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Create additional indexes for performance (will be created by Flask-Migrate)
-- These are here for reference and will be handled by migrations

-- Grant permissions (redundant but explicit)
GRANT ALL PRIVILEGES ON DATABASE realrecap TO realrecap;

-- Set timezone
SET timezone = 'UTC';

-- Performance settings (some may be overridden by command-line params)
-- These are documented here for reference
-- ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
-- ALTER SYSTEM SET max_connections = 200;
-- ALTER SYSTEM SET shared_buffers = '256MB';
-- ALTER SYSTEM SET effective_cache_size = '1GB';

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'RealRecap PostgreSQL database initialized successfully';
    RAISE NOTICE 'Database: %', current_database();
    RAISE NOTICE 'User: %', current_user;
    RAISE NOTICE 'Timezone: %', current_setting('timezone');
END $$;