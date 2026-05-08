"""Application settings — Pydantic Settings sobre env vars (.env / Doppler).

Single source of truth: cualquier env var nueva se documenta primero en
`.env.example`, luego se añade aquí con tipo + default. NO leer `os.environ`
directamente desde otros módulos — siempre via `from app.core.config import settings`.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "mt-pricing-backend"
    APP_VERSION: str = "0.1.0"
    ENV: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    ENABLE_DOCS: bool = True

    # --- Server ---
    HOST: str = "0.0.0.0"  # noqa: S104 — bind explícito para contenedor
    PORT: int = 8000

    # --- Database ---
    # async URL para SQLAlchemy (asyncpg)
    DATABASE_URL: PostgresDsn = Field(
        default="postgresql+asyncpg://mt_app:devpassword@localhost:5432/mt_pricing_dev",  # type: ignore[arg-type]
    )
    # sync URL para Alembic (psycopg)
    ALEMBIC_DATABASE_URL: PostgresDsn = Field(
        default="postgresql+psycopg://mt_app:devpassword@localhost:5432/mt_pricing_dev",  # type: ignore[arg-type]
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_PRE_PING: bool = True
    DATABASE_ECHO: bool = False

    # --- Redis / Celery ---
    REDIS_URL: RedisDsn = Field(default="redis://localhost:6379/0")  # type: ignore[arg-type]
    CELERY_BROKER_URL: RedisDsn = Field(default="redis://localhost:6379/1")  # type: ignore[arg-type]
    CELERY_RESULT_BACKEND: RedisDsn = Field(default="redis://localhost:6379/2")  # type: ignore[arg-type]

    # --- Supabase ---
    SUPABASE_URL: str = "https://your-project.supabase.co"
    SUPABASE_ANON_KEY: SecretStr = SecretStr("your-anon-key")
    SUPABASE_SERVICE_ROLE_KEY: SecretStr = SecretStr("your-service-role-key")
    SUPABASE_JWT_SECRET: SecretStr = SecretStr("your-jwt-secret")
    SUPABASE_STORAGE_BUCKET_IMAGES: str = "product-images"
    SUPABASE_STORAGE_BUCKET_IMPORTS: str = "imports-raw"
    SUPABASE_STORAGE_BUCKET_EXPORTS: str = "exports"
    SUPABASE_STORAGE_BUCKET_DATASHEETS: str = "product-datasheets"

    # --- Sentry ---
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    SENTRY_PROFILES_SAMPLE_RATE: float = 0.0

    # --- CORS ---
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8055"],
    )

    # --- Observability ---
    BETTER_STACK_LOGS_TOKEN: str = ""
    BETTER_STACK_LOGS_HOST: str = ""
    PROMETHEUS_ENABLED: bool = False
    PROMETHEUS_PORT: int = 9090

    # --- Auth ---
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    # Modo de verificación del access_token de Supabase:
    #   - "hs256": HS256 con `SUPABASE_JWT_SECRET` (default Supabase legacy).
    #   - "jwks": RS256/ES256 contra JWKS de Supabase (asymmetric signing keys).
    SUPABASE_JWT_VERIFICATION_MODE: Literal["hs256", "jwks"] = "hs256"
    # Si vacío, se infiere desde SUPABASE_URL → `${SUPABASE_URL}/auth/v1/.well-known/jwks.json`.
    SUPABASE_JWKS_URL: str = ""
    SUPABASE_JWKS_CACHE_TTL_SECONDS: int = 3600
    # URL del healthcheck de Supabase Auth — chequeada por /health/ready.
    # Vacío = no se chequea (útil en dev/tests sin Supabase real).
    SUPABASE_AUTH_HEALTH_URL: str = ""
    SUPABASE_AUTH_HEALTH_TIMEOUT_S: float = 2.0

    # --- Healthcheck auth ---
    HEALTH_BASIC_AUTH_USER: str = "monitoring"
    HEALTH_BASIC_AUTH_PASSWORD: SecretStr = SecretStr("change-me")
    # Token alternativo para monitores que no soportan basic-auth (header X-Healthcheck-Token).
    HEALTH_TOKEN: SecretStr = SecretStr("")

    # --- External APIs ---
    OPENAI_API_KEY: SecretStr = SecretStr("")
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # --- Timezone (MT — Asia/Dubai) ---
    TIMEZONE: str = "Asia/Dubai"

    # --- Feature flags ---
    FEATURE_KB_ENABLED: bool = False
    FEATURE_COMPARATOR_ENABLED: bool = False
    FEATURE_OCR_ENABLED: bool = False

    # --- GraphRAG (Sprint 6) ---
    # Backend del graph store. `stub` = Neo4jStubGraphStore in-memory (default
    # Fase 1). `neo4j` = driver real contra Neo4j 5 (Docker local o managed).
    GRAPHRAG_BACKEND: Literal["stub", "neo4j"] = "stub"
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: SecretStr = SecretStr("devpassword")
    NEO4J_DATABASE: str = "neo4j"
    NEO4J_CONNECTION_TIMEOUT_S: float = 10.0
    NEO4J_MAX_CONNECTION_POOL_SIZE: int = 50

    # --- SSRF / image probe (ADR-055, R-022, R-044) ---
    # Permitir HTTP plano sólo en dev (e.g. fixtures locales con httpbin).
    ALLOW_HTTP_PROBE: bool = False
    # Gate del feature flag PIM España hasta firma de Q-09 (R-044).
    ALLOW_PROBE_FROM_PIM_ES: bool = False
    # Hosts considerados "PIM España" para el gating arriba. Vacío usa default.
    PIM_ES_HOST_ALLOWLIST: list[str] = Field(default_factory=list)
    # CIDRs extra a bloquear (p. ej. rangos Hetzner vSwitch privado MT). TI MT
    # debe confirmar y poblar via env. Default vacío (denylist canónica cubre RFC1918).
    SSRF_EXTRA_BLOCKED_CIDRS: list[str] = Field(default_factory=list)
    # Cap de tamaño imagen probe — 10 MB.
    SSRF_MAX_BYTES: int = 10 * 1024 * 1024
    # Hops máximos siguiendo redirects.
    SSRF_MAX_REDIRECTS: int = 3
    # Timeout total para descarga (segundos).
    SSRF_FETCH_TIMEOUT_S: float = 30.0

    @property
    def is_prod(self) -> bool:
        return self.ENV == "production"

    @property
    def is_dev(self) -> bool:
        return self.ENV == "development"


@lru_cache
def get_settings() -> Settings:
    """Singleton cacheado — evita releer el archivo `.env` en cada request."""
    return Settings()


settings: Settings = get_settings()
