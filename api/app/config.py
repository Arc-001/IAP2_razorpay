from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://ap2:ap2@localhost:5432/ap2"

    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    # HMAC-SHA256 secret for signing Intent/Cart mandates (see CLAUDE.md §1).
    mandate_signing_secret: str = "dev-only-change-me"

    anthropic_api_key: str = ""

    # LLM tool-calling goes through OpenRouter (OpenAI-compatible API), not
    # a direct Anthropic SDK call — see CLAUDE.md Commands note on this deviation.
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "google/gemini-3.7-flash"


settings = Settings()
