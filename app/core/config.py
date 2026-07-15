from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    environment: str = "development"
    pgvector_extension: str = "vector"
    llm_provider: str = "mistral"
    mistral_api_key: str = ""
    mistral_model: str = "mistral-large-latest"
    mistral_timeout: float = 30.0
    mistral_temperature: float = 0.3
    mistral_max_tokens: int = 1024
    max_retries: int = 3
    prompt_analysis_model: str = "mistral-large-latest"
    prompt_analysis_temperature: float = 0.2
    prompt_score_threshold: float = 5.0
    quality_threshold: float = 0.70
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    top_k_results: int = 5
    similarity_threshold: float = 0.05
    role_match_threshold: float = 0.50
    mode_match_threshold: float = 0.50
    cache_model: bool = True
    enable_soft_delete: bool = True
    max_version_history: int = 50
    auto_generate_embedding: bool = True
    prompt_top_k: int = 10
    duplicate_threshold: float = 0.90
    enable_recommendations: bool = True
    enable_dev_auth_bypass: bool = False

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
