-- SmartStock PostgreSQL Database Setup
-- Run these commands in psql or PostgreSQL management tool

-- Create database
CREATE DATABASE smartstock;

-- Create user with password
CREATE USER smartstock_user WITH PASSWORD 'password';

-- Grant privileges to user
ALTER ROLE smartstock_user SET client_encoding TO 'utf8';
ALTER ROLE smartstock_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE smartstock_user SET default_transaction_deferrable TO on;
ALTER ROLE smartstock_user SET default_transaction_READ COMMITTED;
ALTER ROLE smartstock_user SET timezone TO 'Asia/Karachi';

-- Grant all privileges on the database
GRANT ALL PRIVILEGES ON DATABASE smartstock TO smartstock_user;

-- Connect to the new database and grant schema privileges
\c smartstock
GRANT ALL ON SCHEMA public TO smartstock_user;

-- Display confirmation
\l smartstock
