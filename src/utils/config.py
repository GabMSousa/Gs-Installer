"""Configuration boundary."""

from app.core.config import AppConfig


def load_config() -> AppConfig:
    return AppConfig.load()


def save_config(config: AppConfig) -> None:
    config.save()

__all__ = ["AppConfig", "load_config", "save_config"]
