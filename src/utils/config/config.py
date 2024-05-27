from pydantic import Field
from pydantic_settings import BaseSettings

class AppSettings(BaseSettings):
    master_services_key_seed: str = Field('dummy')

app_settings = AppSettings()