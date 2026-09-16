from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    google_maps_api_key: str = ""
    fcm_server_key: str = ""
    gemini_api_key: str = ""
    textlk_api_token: str = ""

    class Config:
        env_file = ".env"

settings = Settings()