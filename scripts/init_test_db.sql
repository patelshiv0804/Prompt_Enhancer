-- Create test database if it doesn't exist
-- This runs automatically when using docker-compose
SELECT 'CREATE DATABASE prompt_enhancer_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'prompt_enhancer_test')\gexec
