from pydantic_settings import BaseSettings,SettingsConfigDict


class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "hcp_crm"

    GROQ_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()