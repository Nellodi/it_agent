from aiogram.fsm.state import State, StatesGroup

class AuthStates(StatesGroup):
    """Состояния для авторизации"""
    waiting_for_login = State()
    waiting_for_password = State()

class TicketStates(StatesGroup):
    """Состояния для создания заявки"""
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_category = State()
    waiting_for_priority = State()