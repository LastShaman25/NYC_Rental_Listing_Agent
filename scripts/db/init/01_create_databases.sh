#!/bin/bash
# Runs once on first container start. Creates the test database alongside the
# default rental_dev database and enables required extensions in both.
set -e

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres <<'SQL'
CREATE DATABASE rental_test OWNER rental;
SQL

for db in rental_dev rental_test; do
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$db" <<'SQL'
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
SQL
done
