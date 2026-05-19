from aiogram.fsm.state import State, StatesGroup


class ContentStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_comment = State()
    choosing_rating = State()
    choosing_reaction = State()
