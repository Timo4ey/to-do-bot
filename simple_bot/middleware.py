from logging import Logger
import pathlib

from aiogram.types import InputMediaPhoto, FSInputFile, Message
from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramAPIError


class ErrorHandlerMiddleware(BaseMiddleware):
    def __init__(self, logger: Logger):
        super().__init__()
        self.logger = logger
        self.error_file = pathlib.Path(__file__).parent / "static" / "bad_request.png"

    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        except Exception as e:
            self.logger.error(f"Unhandled exception: {e}", exc_info=True)
            # Отправляем пользователю сообщение об ошибке
            if isinstance(event, Message):
                try:
                    await event.answer_media_group(
                        [
                            InputMediaPhoto(
                                media=FSInputFile(self.error_file), caption="Ой, ой, ой"
                            )
                        ]
                    )
                except TelegramAPIError:
                    self.logger.warning("Не удалось отправить сообщение пользователю")
            raise  # Передаём ошибку дальше, если нужно
