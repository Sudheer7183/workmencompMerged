# from __future__ import annotations

# from functools import lru_cache

# from pydantic import field_validator
# from pydantic_settings import BaseSettings, SettingsConfigDict


# class Settings(BaseSettings):
#     """
#     Platform-wide configuration loaded from environment variables.

#     All fields are explicitly typed.
#     Validation is performed at startup; a missing required variable
#     raises an immediate, descriptive error rather than a runtime crash.
#     """

#     model_config = SettingsConfigDict(
#         env_file=".env",
#         env_file_encoding="utf-8",
#         case_sensitive=True,
#     )

#     # -------------------------------------------------------------------------
#     # Database
#     # -------------------------------------------------------------------------
#     DATABASE_URL: str

#     # -------------------------------------------------------------------------
#     # Redis
#     # -------------------------------------------------------------------------
#     REDIS_URL: str

#     # -------------------------------------------------------------------------
#     # Keycloak / Auth
#     # -------------------------------------------------------------------------
#     KEYCLOAK_URL: str = "http://localhost:8080"
#     KEYCLOAK_REALM: str = "audit-platform"
#     KEYCLOAK_CLIENT_ID: str = "audit-platform-backend"
#     KEYCLOAK_CLIENT_SECRET: str = ""
#     """
#     Client secret for the backend service account.
#     Required in Phase 2 for client_credentials token fetch.
#     """
#     KEYCLOAK_FRONTEND_CLIENT_ID: str = "audit-platform-frontend"

#     SKIP_JWT_VERIFICATION: bool = False
#     """
#     Phase 1 only — set to True to decode JWTs without RS256 signature check.
#     Must be False in any environment that processes real data.
#     """

#     # -------------------------------------------------------------------------
#     # Anthropic API
#     # -------------------------------------------------------------------------
#     ANTHROPIC_API_KEY: str = ""
#     ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
#     ANTHROPIC_MAX_TOKENS: int = 800
#     ANTHROPIC_TEMPERATURE: float = 0.3
#     ANTHROPIC_TIMEOUT_SECONDS: float = 10.0

    # -------------------------------------------------------------------------
    # Phase 7C — LLM Key Vault
    # -------------------------------------------------------------------------
    # LLM_KEY_ENCRYPTION_SECRET: str = ""
    # """
    # Fernet key for encrypting LLM API keys at rest.
    # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Must be set when using carrier-scoped LLM configuration.
    # """

#     # -------------------------------------------------------------------------
#     # S3 — File storage for uploaded assets and reports
#     # -------------------------------------------------------------------------
#     S3_BUCKET: str = "audit-platform-uploads"
#     S3_ENDPOINT_URL: str = ""
#     AWS_ACCESS_KEY_ID: str = ""
#     AWS_SECRET_ACCESS_KEY: str = ""
#     AWS_REGION: str = "us-east-1"

#     # -------------------------------------------------------------------------
#     # Application runtime
#     # -------------------------------------------------------------------------
#     ENVIRONMENT: str = "development"
#     LOG_LEVEL: str = "INFO"
#     PLATFORM_DOMAIN: str = "localhost"

#     # -------------------------------------------------------------------------
#     # CORS
#     # -------------------------------------------------------------------------
#     ALLOWED_ORIGINS: list[str] = [
#         "http://localhost:5173",
#         "http://localhost:3000",
#     ]

#     # -------------------------------------------------------------------------
#     # Computed convenience properties
#     # -------------------------------------------------------------------------
#     @property
#     def is_development(self) -> bool:
#         return self.ENVIRONMENT.lower() == "development"

#     @property
#     def is_production(self) -> bool:
#         return self.ENVIRONMENT.lower() == "production"

#     @property
#     def keycloak_jwks_url(self) -> str:
#         return (
#             f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}"
#             "/protocol/openid-connect/certs"
#         )

#     @property
#     def keycloak_token_url(self) -> str:
#         return (
#             f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}"
#             "/protocol/openid-connect/token"
#         )

#     @field_validator("LOG_LEVEL")
#     @classmethod
#     def normalise_log_level(cls, value: str) -> str:
#         valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
#         upper = value.upper()
#         if upper not in valid_levels:
#             raise ValueError(f"LOG_LEVEL must be one of {valid_levels}; got '{value}'")
#         return upper

#     @field_validator("SKIP_JWT_VERIFICATION")
#     @classmethod
#     def warn_if_skip_in_production(cls, value: bool) -> bool:
#         return value


# @lru_cache(maxsize=1)
# def get_settings() -> Settings:
#     """
#     Returns the singleton Settings instance.
#     Cached after the first call — settings are immutable at runtime.
#     """
#     return Settings()


from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Platform-wide configuration loaded from environment variables.

    All fields are explicitly typed.
    Validation is performed at startup; a missing required variable
    raises an immediate, descriptive error rather than a runtime crash.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    DATABASE_URL: str

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    REDIS_URL: str

    # -------------------------------------------------------------------------
    # Keycloak / Auth
    # -------------------------------------------------------------------------
    KEYCLOAK_URL: str = "http://localhost:8080"
    KEYCLOAK_REALM: str = "audit-platform"
    KEYCLOAK_CLIENT_ID: str = "audit-platform-backend"
    KEYCLOAK_CLIENT_SECRET: str = ""
    """
    Client secret for the backend service account.
    Required in Phase 2 for client_credentials token fetch.
    """
    KEYCLOAK_FRONTEND_CLIENT_ID: str = "audit-platform-frontend"

    SKIP_JWT_VERIFICATION: bool = False
    """
    Phase 1 only — set to True to decode JWTs without RS256 signature check.
    Must be False in any environment that processes real data.
    """

    # -------------------------------------------------------------------------
    # Anthropic API
    # -------------------------------------------------------------------------
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    ANTHROPIC_MAX_TOKENS: int = 800
    ANTHROPIC_TEMPERATURE: float = 0.3
    ANTHROPIC_TIMEOUT_SECONDS: float = 10.0
    
    LLM_KEY_ENCRYPTION_SECRET: str = ""

    # -------------------------------------------------------------------------
    # S3 — File storage for uploaded assets and reports
    # -------------------------------------------------------------------------
    S3_BUCKET: str = "audit-platform-uploads"
    S3_ENDPOINT_URL: str = ""
    """
    Internal S3/MinIO endpoint used by the backend container for upload and
    presigning operations. In Docker this is the container-network address,
    e.g. http://minio:9000.
    """
    S3_PUBLIC_URL: str = ""
    """
    Public-facing S3/MinIO URL reachable from the browser.
    When set, presigned URLs have their internal hostname replaced with this
    value before being returned to the frontend.

    Example (docker-compose local dev):
      S3_ENDPOINT_URL = http://minio:9000   (container-internal)
      S3_PUBLIC_URL   = http://localhost:9000 (browser-reachable)

    Leave empty in production — AWS presigned URLs already use the public
    endpoint and no rewriting is needed.
    """
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"

    # -------------------------------------------------------------------------
    # Application runtime
    # -------------------------------------------------------------------------
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    PLATFORM_DOMAIN: str = "localhost"

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # -------------------------------------------------------------------------
    # Computed convenience properties
    # -------------------------------------------------------------------------
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def keycloak_jwks_url(self) -> str:
        return (
            f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}"
            "/protocol/openid-connect/certs"
        )

    @property
    def keycloak_token_url(self) -> str:
        return (
            f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}"
            "/protocol/openid-connect/token"
        )

    @field_validator("LOG_LEVEL")
    @classmethod
    def normalise_log_level(cls, value: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}; got '{value}'")
        return upper

    @field_validator("SKIP_JWT_VERIFICATION")
    @classmethod
    def warn_if_skip_in_production(cls, value: bool) -> bool:
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns the singleton Settings instance.
    Cached after the first call — settings are immutable at runtime.
    """
    return Settings()
