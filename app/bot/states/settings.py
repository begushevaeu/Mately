from aiogram.fsm.state import State, StatesGroup


class ReminderSettingsStates(StatesGroup):
    waiting_for_morning_time = State()
    waiting_for_evening_time = State()
