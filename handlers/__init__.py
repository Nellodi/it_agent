# Файл: it_ecosystem_bot/handlers/__init__.py

from .auth import router as auth_router
from .start import router as start_router
from .profile import router as profile_router
from .tickets import router as tickets_router
from .admin import router as admin_router
from .admin_tickets import router as admin_tickets_router
from .equipment import router as equipment_router
from .workplaces import router as workplaces_router