import asyncio
from io import BytesIO
from typing import Any

import aiohttp
from pydub import AudioSegment

from src.handler import Handler
from src.schemas import Audio, Audios


class AudioHandler(Handler):
    """
    Handler for audio files.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._is_running = False
        self.files = []

    def handle(self, files: Audios, *args: Any, **kwargs: Any) -> Audio:
        response = None
        if not self._is_running:
            raise RuntimeError("Handler not started")
        if isinstance(files.files, list):
            all_files: list[AudioSegment] = self._get_audio_segments(files.files)
            response = self._join_audio_files(all_files, files.format)
            return Audio(file=response, format=files.format)

        elif isinstance(files.files, bytes):
            response = self._get_audio_segment(files.files)
        else:
            raise TypeError("Invalid type for files")
        return Audio(file=response.raw_data, format=files.format)

    def _get_audio_segment(self, input_file: bytes | BytesIO) -> AudioSegment:
        """
        Convert audio file to the specified format.
        """
        if isinstance(input_file, bytes):
            input_file = BytesIO(input_file)
        audio: AudioSegment = AudioSegment.from_file(input_file)
        return audio

    def _get_audio_segments(
        self, input_files: list[bytes | BytesIO]
    ) -> list[AudioSegment]:
        """
        Convert a list of audio files to the specified format.
        """
        audio_segments = []
        for input_file in input_files:
            audio_segment: AudioSegment = self._get_audio_segment(input_file)
            audio_segments.append(audio_segment)
        return audio_segments

    def _join_audio_files(
        self, audio_segments: list[AudioSegment], output_format: str
    ) -> bytes:
        """
        Join a list of audio segments into a single audio segment.
        """
        combined = AudioSegment.empty()
        for audio in audio_segments:
            combined += audio
        buffer = BytesIO()
        combined.export(buffer, format=output_format)

        return buffer.getvalue()

    def start(self):
        self._is_running = True
        return super().start()

    def stop(self):
        return super().stop()


def create_audio_from_files_paths(files: list[str]) -> Audios:
    """
    Create an Audio object from a list of file paths.
    """

    audio_files = []
    format_file = files[0].split(".")[-1]
    for file in files:
        with open(file, "rb") as f:
            audio_files.append(f.read())
    return Audios(files=audio_files, format=format_file)


async def download_audio_file(session: aiohttp.ClientSession, url: str) -> bytes:
    async with session.get(url) as response:
        if response.status != 200:
            raise ValueError("Failed to fetch audio file")
        return await response.read()


async def create_audio_from_links(links: list[str]) -> Audios:
    """
    Create an Audio object from a list of file links.
    """
    async with aiohttp.ClientSession() as session:
        tasks = [download_audio_file(session, link) for link in links]
        audio_files = await asyncio.gather(*tasks)
        format_file = "mp3"

    return Audios(files=audio_files, format=format_file)
