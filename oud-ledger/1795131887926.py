from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///:memory:")
    shop_name: str = os.getenv("SHOP_NAME", "Example Oud Shop")
    currency: str = os.getenv("CURRENCY", "USD")


settings = Settings()