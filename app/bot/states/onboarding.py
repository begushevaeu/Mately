from aiogram.fsm.state import State, StatesGroup


class JoinCoupleStates(StatesGroup):
    waiting_for_invite_code = State()
