from aiogram.fsm.state import State, StatesGroup


class PartnerAliasStates(StatesGroup):
    waiting_for_emoji = State()
    waiting_for_nominative = State()
    waiting_for_genitive = State()
    waiting_for_dative = State()
