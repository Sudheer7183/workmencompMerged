# ---------------------------------------------------------------------------
# Keycloak 24 — no extra build stages needed.
#
# The previous Dockerfile pulled registry.access.redhat.com/ubi9 solely to
# install curl for the Docker healthcheck. That registry times out in many
# environments (WSL2, corporate proxies, CI runners).
#
# The healthcheck in docker-compose.yml uses a pure bash /dev/tcp check
# instead — no external tool required. The base Keycloak image alone is
# sufficient.
# ---------------------------------------------------------------------------
FROM quay.io/keycloak/keycloak:24.0.0

EXPOSE 8080
