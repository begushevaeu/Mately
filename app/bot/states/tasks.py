from aiogram.fsm.state import State, StatesGroup


class TaskCreationStates(StatesGroup):
    waiting_for_title = State()
    choosing_recurring = State()
    choosing_recurrence = State()
    choosing_assignment = State()
    waiting_for_deadline = State()
