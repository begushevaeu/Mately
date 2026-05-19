from aiogram.fsm.state import State, StatesGroup


class ShoppingStates(StatesGroup):
    waiting_for_title = State()
