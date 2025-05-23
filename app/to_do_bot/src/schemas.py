from typing import List, Union
from enum import Enum
from io import BytesIO

from pydantic import BaseModel, ConfigDict, field_validator


class WordAlignment(BaseModel):
    word: str
    start: str
    end: str


class Result(BaseModel):
    text: str
    normalized_text: str
    start: str
    end: str
    word_alignments: List[WordAlignment]


class EmotionResult(BaseModel):
    positive: float
    neutral: float
    negative: float


class BackendInfo(BaseModel):
    model_name: str
    model_version: str
    server_version: str


class SpeakerInfo(BaseModel):
    speaker_id: int
    main_speaker_confidence: float


class PersonIdentityAge(str, Enum):
    AGE_NONE = "AGE_NONE"


class PersonIdentityGender(str, Enum):
    GENDER_NONE = "GENDER_NONE"


class PersonIdentity(BaseModel):
    age: PersonIdentityAge
    gender: PersonIdentityGender
    age_score: float
    gender_score: float


class TranscriptionItem(BaseModel):
    results: List[Result]
    eou: bool
    emotions_result: EmotionResult
    processed_audio_start: str
    processed_audio_end: str
    backend_info: BackendInfo
    channel: int
    speaker_info: SpeakerInfo
    eou_reason: str
    insight: str
    person_identity: PersonIdentity


class Audio(BaseModel):
    """
    Audio data class for single file.
    """

    file: bytes
    format: str

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _truncate_data(self, data: bytes) -> str:
        """Сокращает отображение байтов для печати"""
        MAX_PREVIEW = 10  # Первые N байт для предпросмотра

        preview = data[:MAX_PREVIEW].hex(" ", 1)
        if len(data) > MAX_PREVIEW:
            preview += "..."
        return f"bytes(length={len(data)}, data={preview})"

    def __repr__(self) -> str:
        truncated = self._truncate_data(self.file)
        return f"Audio(file={truncated}, format='{self.format}')"

    def __str__(self) -> str:
        return self.__repr__()

    def __len__(self) -> int:
        return len(self.file)


class Audios(BaseModel):
    """
    Audio data class for multiple files.
    """

    files: list[Union[bytes, BytesIO]]
    format: str

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("files")
    def validate_files(cls, v):
        validated = []
        for item in v:
            if isinstance(item, bytes):
                validated.append(BytesIO(item))
            elif isinstance(item, BytesIO):
                validated.append(item)
            else:
                raise ValueError("File must be bytes or BytesIO")
        return validated

    def _truncate_data(self, data: Union[bytes, BytesIO]) -> str:
        """Сокращает отображение байтов/BytesIO для печати"""
        MAX_PREVIEW = 10  # Первые N байт для предпросмотра

        if isinstance(data, BytesIO):
            raw = data.getvalue()
            preview = raw[:MAX_PREVIEW].hex(" ", 1) + (
                "..." if len(raw) > MAX_PREVIEW else ""
            )
            return f"BytesIO(length={len(raw)})"

        preview = data[:MAX_PREVIEW].hex(" ", 1) + (
            "..." if len(data) > MAX_PREVIEW else ""
        )
        return f"bytes(length={len(data)}, data={preview})"

    def __repr__(self) -> str:
        MAX_ITEMS = 3  # Максимум элементов для показа
        truncated = [self._truncate_data(f) for f in self.files[:MAX_ITEMS]]
        if len(self.files) > MAX_ITEMS:
            truncated.append(f"...(+{len(self.files) - MAX_ITEMS} more)")
        return f"Audio(files={truncated}, format='{self.format}')"

    def __str__(self) -> str:
        return self.__repr__()

    def __len__(self) -> int:
        return len(self.files)
