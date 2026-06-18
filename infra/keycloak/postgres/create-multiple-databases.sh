#!/bin/bash
# ---------------------------------------------------------------------------
# create-multiple-databases.sh
#
# Runs on first postgres startup via /docker-entrypoint-initdb.d/
# Creates additional databases listed in POSTGRES_MULTIPLE_DATABASES
# (comma-separated) using the same POSTGRES_USER.
#
# Example: POSTGRES_MULTIPLE_DATABASES=auditplatform,keycloak
# creates both "auditplatform" and "keycloak" databases owned by
# POSTGRES_USER.
# ---------------------------------------------------------------------------
set -e

function create_database() {
    local database=$1
    echo "Creating database: $database"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-SQL
        SELECT 'CREATE DATABASE $database OWNER $POSTGRES_USER'
        WHERE NOT EXISTS (
            SELECT FROM pg_database WHERE datname = '$database'
        )\gexec
SQL
}

if [ -n "$POSTGRES_MULTIPLE_DATABASES" ]; then
    echo "Multiple databases requested: $POSTGRES_MULTIPLE_DATABASES"
    for db in $(echo $POSTGRES_MULTIPLE_DATABASES | tr ',' ' '); do
        create_database "$db"
    done
    echo "All databases created."
fi
