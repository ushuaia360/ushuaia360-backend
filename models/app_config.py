"""
Modelo para la tabla app_config (mantenimiento y actualización requerida).
"""
from models.base import BaseModel


class AppConfig(BaseModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get("id")
        self.type = kwargs.get("type")
        self.is_active = kwargs.get("is_active", False)
        self.title = kwargs.get("title", "")
        self.message = kwargs.get("message", "")
        self.ios_min_build = kwargs.get("ios_min_build")
        self.android_min_build = kwargs.get("android_min_build")
        self.created_at = kwargs.get("created_at")
        self.updated_at = kwargs.get("updated_at")
