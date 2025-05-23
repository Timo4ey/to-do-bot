from typing import List
from aiogram.types import Message
from aiogram import Bot


from keyboards import KeyboardEnum
from src import TranscriptionItem, Result


def adapter_salute_speech(data: list[TranscriptionItem]) -> str:
    """Convert transcription items to a single text string"""
    res = []
    results: list[List[Result]] = [x.results for x in data]
    if not results:
        return ""
    for item in results:
        [result] = item
        res.append(f"{result.text}")
    return " ".join(res)


def get_url(bot: Bot, file_path: str) -> str:
    """Generate direct URL for accessing file through Telegram API"""
    return f"https://api.telegram.org/file/bot{bot.token}/{file_path}"


def is_valid_message(message_text: str) -> bool:
    """Check if the message text matches any keyboard enum value"""
    return any(message_text == item.value for item in KeyboardEnum)


def has_media_file(message: Message) -> bool:
    """Check if message contains audio file"""
    return message.audio is not None
