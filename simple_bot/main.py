from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram import Bot, Dispatcher, F
import asyncio
import logging
import sys
from os import getenv
from dotenv import load_dotenv

from aiogram.types.file import File

from helpers import adapter_salute_speech, get_url, is_valid_message
from keyboards import KeyboardEnum, keyboard_with_extra
from src import TranscriptionItem, init_bootstrap, create_audio_from_links, welcome_text

dp = Dispatcher()


load_dotenv()


class UserState(StatesGroup):
    waiting_for_audio = State()  # Waiting for audio files
    action_selected = State()  # Action has been selected by user


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    """Handle /start command: reset state and show main keyboard"""
    await state.clear()
    await message.answer(
        f"Добро пожаловать {message.from_user.full_name}! \n {welcome_text}",
    )


@dp.message(F.text & ~F.command)
async def handle_text(message: Message, state: FSMContext):
    """Handle text messages from user"""
    current_state = await state.get_state()

    if current_state == UserState.action_selected:
        await message.answer("Выберите тему, пожалуйста")
    elif message.text == KeyboardEnum.CANCEL.value:
        STORE.pop(message.chat.id, [])
        await state.clear()
        await message.answer(
            "Аудиозаписи удалены из обработки",
        )
    elif is_valid_message(message.text) and message.text != KeyboardEnum.CANCEL.value:
        await state.set_state(UserState.action_selected)

        # Process stored audio files
        audio_list = STORE.pop(message.chat.id, [])
        if not audio_list:
            await message.answer(
                "Нет сохраненных аудио для обработки",
            )
            return

        # Process audio and perform transcription
        await message.answer("Началась обработка аудиозаписи(ей)")
        audio = await create_audio_from_links(audio_list)
        logging.info(f"Created audio from links: {len(audio_list)} files")
        joined_audio = audio_handler.handle(audio)
        logging.info(f"Joined audio size: {len(joined_audio) if joined_audio else 0}")
        sst_result: list[TranscriptionItem] | None = await stt_handler.handle(
            joined_audio
        )
        logging.info(
            f"STT processing complete, results: {len(sst_result) if sst_result else 0}"
        )
        combined_stt = adapter_salute_speech(sst_result)

        # Process with LLM based on selected action
        logging.info(f"Selected action: {message.text}")
        match message.text:
            case KeyboardEnum.MAKE_TO_DO_LIST.value:
                llm_result = await llm.handle("task_summary", combined_stt)
            case KeyboardEnum.MAKE_WORKING_SUMMARIZE.value:
                llm_result = await llm.handle("day_summary", combined_stt)
            case _:
                llm_result = await llm.handle("simple_summary", combined_stt)
        logging.info("LLM processing complete")
        if len(llm_result.content) + len(combined_stt) <= MAX_TEXT_LENGTH - 1:
            await bot.send_message(
                chat_id=message.chat.id,
                text=(
                    f"{llm_result.content}\n\n\n\n\n"
                    "Транскрибация:\n"
                    f"<blockquote>{combined_stt}</blockquote>"
                ),
                parse_mode="HTML",
            )
        else:
            await bot.send_message(
                # llm_result.content,
                chat_id=message.chat.id,
                text=(
                    f"{llm_result.content}\n\n\n\n\n"
                    "Транскрибация слишком большая для отправки. "
                    "Попробуйте отправить меньше аудиозаписей."
                ),
            )

    else:
        if not is_valid_message(message.text):
            await message.answer("Бот работает только с голосовыми сообщениями")


@dp.message(F.voice | F.audio)
async def handle_audio(message: Message, state: FSMContext):
    """Handle voice or audio messages"""
    curr_state = await state.get_state()
    if curr_state != UserState.waiting_for_audio:
        await state.set_state(UserState.waiting_for_audio)

    # Get file info and generate URL
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file_info: File = await bot.get_file(file_id)
    file_path = file_info.file_path
    media_url = get_url(bot, file_path)

    # Store media URL for later processing
    chat_id = message.chat.id
    if chat_id not in STORE:
        STORE[chat_id] = []
    STORE[chat_id].append(media_url)

    await message.answer(
        "Аудио получено. Можете отправить еще или выбрать действие в клавиатуре.",
        reply_markup=keyboard_with_extra,
    )


@dp.message(
    F.text.in_(
        {
            KeyboardEnum.MAKE_TO_DO_LIST.value,
            KeyboardEnum.MAKE_WORKING_SUMMARIZE.value,
            KeyboardEnum.MAKE_JUST_SUMMARIZE.value,
            KeyboardEnum.CANCEL.value,
        }
    )
)
async def handle_button(message: Message, state: FSMContext):
    """Handle main action buttons"""
    current_state = await state.get_state()

    if current_state == UserState.waiting_for_audio:
        await message.answer(f"Вы выбрали: {message.text}")
        await state.set_state(UserState.action_selected)
    else:
        await message.answer("Пожалуйста, сначала отправьте аудиосообщение")


async def main():
    """Main function to initialize components and start the bot"""
    global llm, audio_handler, stt_handler, STORE, bot, MAX_TEXT_LENGTH
    MAX_TEXT_LENGTH = 4096
    # Bot token from environment variable
    TOKEN = getenv("BOT_TOKEN")

    # In-memory storage for audio links
    STORE = {}

    # User states for FSM

    bot = Bot(token=TOKEN)
    llm, audio_handler, stt_handler = init_bootstrap()

    logging.info("Starting bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
