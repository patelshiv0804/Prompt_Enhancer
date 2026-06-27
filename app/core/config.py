from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    pgvector_extension: str = "vector"
    llm_provider: str = "mistral"
    mistral_api_key: str = ""
    mistral_model: str = "mistral-mini"
    mistral_timeout: float = 30.0
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    top_k_results: int = 5
    similarity_threshold: float = 0.65

    # JWT Authentication Config
    secret_key: str = "supersecretkey_change_me_in_production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # SMTP & OTP Config
    smtp_user: str = ""
    smtp_password: str = ""
    from_email: str = "noreply@promptiq.com"
    otp_expire_minutes: int = 15
    smtp_host: str = "localhost"
    smtp_port: int = 587

    @property
    def SMTP_USER(self) -> str:
        return self.smtp_user

    @property
    def SMTP_PASSWORD(self) -> str:
        return self.smtp_password

    @property
    def FROM_EMAIL(self) -> str:
        return self.from_email

    @property
    def OTP_EXPIRE_MINUTES(self) -> int:
        return self.otp_expire_minutes

    @property
    def SMTP_HOST(self) -> str:
        return self.smtp_host

    @property
    def SMTP_PORT(self) -> int:
        return self.smtp_port

    # Map settings for jose library case sensitivity
    @property
    def SECRET_KEY(self) -> str:
        return self.secret_key

    @property
    def ALGORITHM(self) -> str:
        return self.algorithm

    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        return self.access_token_expire_minutes

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()

def get_settings() -> Settings:
    return settings
