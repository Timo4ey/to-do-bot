import asyncio

from src.llm import GigaChatLLM
from src.audio_handler import AudioHandler
from src.salute_speech_stt import SaluteSpeechHandler
from src.static import task_prompt, done_deals, simple_summary


def init_bootstrap(
    *args, **kwargs
) -> tuple[GigaChatLLM, AudioHandler, SaluteSpeechHandler]:
    llm = _init_llm_handler(*args, **kwargs)
    audio = _init_audio_handler(*args, **kwargs)
    speech_stt = _init_speech_stt_handler(*args, **kwargs)
    return llm, audio, speech_stt


def _init_llm_handler(*args, **kwargs) -> GigaChatLLM:
    giga = GigaChatLLM(
        *args,
        GIGACHAT_SYSTEM_PROMPTS={
            "task_summary": task_prompt,
            "day_summary": done_deals,
            "simple_summary": simple_summary,
        },
        **kwargs,
    )
    giga.start()
    return giga


def _init_audio_handler(*args, **kwargs) -> AudioHandler:
    audio_handler = AudioHandler(*args, **kwargs)
    audio_handler.start()
    return audio_handler


def _init_speech_stt_handler(*args, **kwargs) -> SaluteSpeechHandler:
    speech_stt_handler = SaluteSpeechHandler(*args, **kwargs)

    loop = asyncio.get_event_loop()
    loop.create_task(speech_stt_handler.start())

    return speech_stt_handler
