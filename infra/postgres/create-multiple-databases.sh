#!/bin/bash
# ---------------------------------------------------------------------------
# create-multiple-databases.sh
#
# PostgreSQL Docker entrypoint init script.
# Runs ONCE on a fresh volume via /docker-entrypoint-initdb.d/
#
# Creates additional databases listed in POSTGRES_MULTIPLE_DATABASES
# (comma-separated) using POSTGRES_USER as the owner.
#
# Example:
#   POSTGRES_MULTIPLE_DATABASES=auditplatform,keycloak
#   → creates "auditplatform" and "keycloak" owned by POSTGRES_USER
#
# The "keycloak" database is required when KC_DB=postgres so that Keycloak
# persists sessions and realm config across container restarts.
# ---------------------------------------------------------------------------
set -e

function create_database() {
    local database=$1
    echo "  Creating database: $database"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
        SELECT 'CREATE DATABASE "$database" OWNER "$POSTGRES_USER"'
        WHERE NOT EXISTS (
            SELECT FROM pg_database WHERE datname = '$database'
        )\gexec
SQL
}

if [ -n "$POSTGRES_MULTIPLE_DATABASES" ]; then
    echo "Multiple databases requested: $POSTGRES_MULTIPLE_DATABASES"
    for db in $(echo "$POSTGRES_MULTIPLE_DATABASES" | tr ',' ' '); do
        create_database "$db"
    done
    echo "All databases ready."
fi
