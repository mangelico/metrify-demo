from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    anthropic_api_key: str
    openai_api_key: str
    stability_api_key: str = ""
    assemblyai_api_key: str = ""
    apify_api_token: str = ""
    platform_fee_pct: float = 0.05
    secret_key: str
    admin_token: str

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
