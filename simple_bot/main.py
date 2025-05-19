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
from middleware import ErrorHandlerMiddleware
from src import init_bootstrap, create_audio_from_links, welcome_text, TranscriptionItem


logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)
logger.info("Starting bot...")

dp = Dispatcher()


load_dotenv()


dp.message.middleware(ErrorHandlerMiddleware(logger))


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

    # Case 1: Already in action_selected state
    if current_state == UserState.action_selected:
        await message.answer("Выберите тему, пожалуйста")
        return

    # Case 2: User wants to cancel
    if message.text == KeyboardEnum.CANCEL.value:
        await handle_cancel(message, state)
        return

    # Case 3: Valid message for processing
    if is_valid_message(message.text) and message.text != KeyboardEnum.CANCEL.value:
        await process_audio_with_text(message, state)
        return

    # Case 4: Invalid message
    await message.answer("Бот работает только с голосовыми сообщениями")


async def handle_cancel(message: Message, state: FSMContext):
    """Handle cancellation of audio processing"""
    STORE.pop(message.chat.id, [])
    await state.clear()
    await message.answer("Аудиозаписи удалены из обработки")


async def process_audio_with_text(message: Message, state: FSMContext):
    """Process stored audio files with text prompt"""
    await state.set_state(UserState.action_selected)

    # Get and check stored audio
    audio_list = STORE.pop(message.chat.id, [])
    if not audio_list:
        await message.answer("Нет сохраненных аудио для обработки")
        return

    # Process audio files
    await message.answer("Началась обработка аудиозаписи(ей)")
    transcription = await transcribe_audio_files(audio_list)
    if not transcription:
        await message.answer("Не удалось обработать аудиозаписи")
        return

    # Generate response based on selected action
    llm_result = await generate_llm_response(message.text, transcription)

    # Send response to user
    await send_formatted_response(message.chat.id, llm_result, transcription)


async def transcribe_audio_files(audio_list) -> list[TranscriptionItem] | str | None:
    """Transcribe audio files and return the combined text"""
    audio = await create_audio_from_links(audio_list)
    logging.info(f"Created audio from links: {len(audio_list)} files")

    joined_audio = audio_handler.handle(audio)
    logging.info(f"Joined audio size: {len(joined_audio) if joined_audio else 0}")

    sst_result = await stt_handler.handle(joined_audio)
    logging.info(
        f"STT processing complete, results: {len(sst_result) if sst_result else 0}"
    )

    return adapter_salute_speech(sst_result) if sst_result else None


async def generate_llm_response(action_text, transcription):
    """Generate LLM response based on the selected action"""
    logging.info(f"Selected action: {action_text}")

    if action_text == KeyboardEnum.MAKE_TO_DO_LIST.value:
        result = await llm.handle("task_summary", transcription)
    elif action_text == KeyboardEnum.MAKE_WORKING_SUMMARIZE.value:
        result = await llm.handle("day_summary", transcription)
    else:
        result = await llm.handle("simple_summary", transcription)

    logging.info("LLM processing complete")
    return result


async def send_formatted_response(chat_id, llm_result, transcription):
    """Send the formatted response to the user"""
    try:
        if len(llm_result.content) + len(transcription) <= MAX_TEXT_LENGTH - 1:
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    f"{llm_result.content}\n\n\n\n\n"
                    "Транскрибация:\n"
                    f"<blockquote>{transcription}</blockquote>"
                ),
                parse_mode="HTML",
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    f"{llm_result.content}\n\n\n\n\n"
                    "Транскрибация слишком большая для отправки. "
                    "Попробуйте отправить меньше аудиозаписей."
                ),
            )
    except Exception as _ex:
        logger.error("Bad format from llm", exc_info=True)
        await bot.send_message(
            chat_id=chat_id,
            text=(f"{llm_result.content}\n\n\n\n\nТранскрибация:\n{transcription}"),
        )


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

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
