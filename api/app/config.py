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


settings = Settings()
