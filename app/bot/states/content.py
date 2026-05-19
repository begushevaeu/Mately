from aiogram.fsm.state import State, StatesGroup


class ContentStates(StatesGroup):
    waiting_for_title = State()
    choosing_rating = State()
    choosing_reaction = State()
