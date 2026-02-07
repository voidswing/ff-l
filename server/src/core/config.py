from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Judge API"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.2"
    openai_timeout_seconds: float = 20.0
    db_host: str = "ff-postgres"
    db_port: int = 5432
    db_name: str = "l"
    db_user: str = "postgres"
    db_password: str = "postgres"
    database_url: str | None = None
    db_echo: bool = False
    slack_token: str | None = None
    slack_log_channel: str = "#l"
    cors_allow_origins: list[str] = ["*"]
    cors_allow_credentials: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def resolved_database_url(self) -> str:
        if self.database_url and self.database_url.strip():
            return self.database_url.strip()
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
