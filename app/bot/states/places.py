from aiogram.fsm.state import State, StatesGroup


class PlaceStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_comment = State()
    choosing_rating = State()
