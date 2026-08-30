from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://ap2:ap2@localhost:5432/ap2"

    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    # HMAC-SHA256 secret for signing Intent/Cart mandates (see CLAUDE.md §1).
    mandate_signing_secret: str = "dev-only-change-me"

    # Separate secret for HTTP bearer-token auth (login sessions) — deliberately
    # not shared with mandate_signing_secret: a leaked login token shouldn't be
    # replayable against mandate-verification code, and rotating one shouldn't
    # force rotating the other.
    auth_jwt_secret: str = "dev-only-change-me-auth"
    auth_jwt_algorithm: str = "HS256"
    auth_jwt_expires_minutes: int = 1440

    anthropic_api_key: str = ""

    # LLM tool-calling goes through OpenRouter (OpenAI-compatible API), not
    # a direct Anthropic SDK call — see CLAUDE.md Commands note on this deviation.
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "google/gemini-3.7-flash"

    # Bounded-mandate rules (CLAUDE.md §11 P2.3)
    intent_expiry_minutes: int = 15
    price_rise_threshold: float = 0.10

    # Browser origins allowed to call this API (SCRUM-37) — 5173 is Vite's
    # default dev port for the customer chat frontend (web/).
    cors_origins: list[str] = ["http://localhost:5173"]

    # OAuth 2.1 + PKCE for the MCP server's connector flow (see plan "Add
    # real OAuth to the MCP server"). Exactly one pre-registered client —
    # no Dynamic Client Registration, no CIMD — client_id is ours to name,
    # claude.ai enters it verbatim in "Use your own OAuth client" mode.
    oauth_client_id: str = "ap2-claude-connector"
    # Populated once the claude.ai live spike (plan Phase 6) reveals its
    # actual callback URL. Validated as an exact match, never a prefix.
    oauth_redirect_uris: list[str] = []
    oauth_authorization_code_ttl_seconds: int = 60
    # Short — OAuth-issued access tokens have a refresh path, unlike the
    # website's own 24h login token (auth_jwt_expires_minutes), so there's
    # no cost to rotating them often, and doing so shrinks the blast radius
    # of a leaked token.
    oauth_access_token_ttl_minutes: int = 60
    oauth_refresh_token_ttl_days: int = 30


settings = Settings()
