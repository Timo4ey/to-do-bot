from enum import Enum
from typing import Optional


class TaskStatus(str, Enum):
    NEW = "NEW"
    RUNNING = "RUNNING"
    CANCELED = "CANCELED"
    DONE = "DONE"
    ERROR = "ERROR"


class AudioFormat(str, Enum):
    ogg = "OPUS"
    opus = "audio/opus"
    wav = "PCM_S16LE"
    mp3 = "MP3"
    flac = "FLAC"

    @classmethod
    def get_extension(cls, codec: str) -> Optional[str]:
        """Возвращает расширение файла по кодеку (например, 'OPUS' → 'ogg')"""
        for fmt in cls:
            if fmt.value == codec:
                return fmt.name
        return None

    @classmethod
    def get_codec(cls, extension: str) -> Optional[str]:
        """Возвращает кодек по расширению файла (например, 'ogg' → 'OPUS')"""
        try:
            return cls[extension.lower()].value
        except KeyError:
            return None

    @classmethod
    def all_extensions(cls) -> list[str]:
        """Возвращает список всех поддерживаемых расширений"""
        return [fmt.name for fmt in cls]

    @classmethod
    def all_codecs(cls) -> list[str]:
        """Возвращает список всех поддерживаемых кодеков"""
        return [fmt.value for fmt in cls]
