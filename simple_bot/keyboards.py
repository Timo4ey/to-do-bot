from enum import Enum
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


class KeyboardEnum(Enum):
    MAKE_TO_DO_LIST = "Составить список задач"
    MAKE_WORKING_SUMMARIZE = "Саммаризировать день"
    MAKE_JUST_SUMMARIZE = "Самаризовать"
    CANCEL = "Сбросить"


keyboard_base = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=KeyboardEnum.MAKE_TO_DO_LIST.value)],
        [KeyboardButton(text=KeyboardEnum.MAKE_WORKING_SUMMARIZE.value)],
        [KeyboardButton(text=KeyboardEnum.MAKE_JUST_SUMMARIZE.value)],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)

# Клавиатура с кнопкой "Send one more"
keyboard_with_extra = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=KeyboardEnum.MAKE_TO_DO_LIST.value)],
        [KeyboardButton(text=KeyboardEnum.MAKE_WORKING_SUMMARIZE.value)],
        [KeyboardButton(text=KeyboardEnum.MAKE_JUST_SUMMARIZE.value)],
        [KeyboardButton(text=KeyboardEnum.CANCEL.value)],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)
