import json
from typing import Optional
import aiohttp
import asyncio
from typing import Any
import logging

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


from src.enums import AudioFormat, TaskStatus
from src.schemas import Audio, TranscriptionItem

from src.handler import Handler

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class SaluteSpeechConfig(BaseSettings):
    credentials: str = Field(..., alias="SALUTE_CREDENTIALS")
    scope: str = Field("SALUTE_SPEECH_PERS", alias="SALUTE_SCOPE")
    url_access_token: str = Field(
        "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        alias="SALUTE_ACCESS_TOKEN_URL",
    )
    url_rest: str = Field(
        "https://smartspeech.sber.ru/rest/v1", alias="SALUTE_REST_URL"
    )
    check_interval: float = Field(2.0, alias="CHECK_INTERVAL")

    model_config = SettingsConfigDict(extra="ignore")


class SaluteSpeechHandler(Handler):
    class Config(SaluteSpeechConfig):
        name: str = Field(default="SaluteSpeechASR")

    def __init__(self, *args, **kwargs) -> None:
        self.access_token = None
        self._is_running = False
        self.config = self.Config(*args, **kwargs)
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def credentials(self) -> str:
        return self.config.credentials

    @property
    def scope(self) -> str:
        return self.config.scope

    @property
    def url_access_token(self) -> str:
        return self.config.url_access_token

    @property
    def url_rest(self) -> str:
        return self.config.url_rest

    @property
    def check_interval(self) -> float:
        return self.config.check_interval

    async def _handle(self, action: str, *args: Any, **kwargs: Any) -> Any:
        if not self._is_running:
            raise RuntimeError("Handler not started")

        handler = getattr(self, f"handle_{action}", None)
        if not handler:
            raise ValueError(f"Unknown action: {action}")

        return await handler(*args, **kwargs)

    @property
    def session(self) -> aiohttp.ClientSession:
        if not self._session:
            resolver = aiohttp.AsyncResolver()
            connector = aiohttp.TCPConnector(resolver=resolver)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def start(self) -> None:
        await self._get_access_token()
        self._is_running = True

    async def stop(self) -> None:
        if self.session is not None:
            await self.session.close()
        self._is_running = False

    async def _get_access_token(self):
        headers = {
            "RqUID": "6f0b1291-c7f3-43c6-bb2e-9f3efb2dc98e",
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Bearer {self.credentials}",
        }
        resp: aiohttp.ClientResponse
        async with self.session.post(
            self.url_access_token,
            headers=headers,
            data={"scope": self.scope},
        ) as resp:
            resp.raise_for_status()

            data = await resp.json()
            self.access_token = f"Bearer {data['access_token']}"

    async def handle_upload(self, file: Audio) -> str:
        url = f"{self.url_rest}/data:upload"
        form = aiohttp.FormData()
        form.add_field(
            name="audio_file1",
            value=file.file,
            filename=f"{file}",
            content_type="application/octet-stream",
        )
        logger.info(f"Request URL: {url}")
        logger.info(f"Payload size: {len(file.file)} bytes")
        logger.info(f"Payload: {form}")
        async with self.session.post(
            url,
            headers={
                "Authorization": self.access_token or "",
            },
            data={"file": file.file},
        ) as resp:
            if resp.status > 299:
                logger.error(f"{resp}", exc_info=True)
                raise aiohttp.ClientError(f"Error uploading file: {resp.status}")
            data = await resp.json()
            return data["result"]["request_file_id"]

    async def handle_recognize(self, file_id: str, codec: AudioFormat) -> str:
        url = f"{self.url_rest}/speech:async_recognize"
        payload = {
            "options": {
                "model": "general",
                "audio_encoding": codec,
                "sample_rate": 16000,
                "channels_count": 1,
            },
            "request_file_id": file_id,
        }
        async with self.session.post(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": self.access_token or "",
            },
            json=payload,
        ) as resp:
            data = await resp.json()
            return data["result"]["id"]

    async def handle_status(self, task_id: str) -> tuple[TaskStatus, str]:
        url = f"{self.url_rest}/task:get?id={task_id}"

        # type: ignore
        async with self.session.get(
            url, headers={"Authorization": self.access_token}, verify_ssl=False
        ) as resp:  # type: ignore
            data = await resp.json()
            status = TaskStatus(data["result"]["status"])
            response_id = data["result"].get("response_file_id", "")
            return status, response_id

    async def handle_download(self, file_id: str) -> bytes:
        url = f"{self.url_rest}/data:download?response_file_id={file_id}"

        async with self.session.get(
            url,
            headers={"Authorization": self.access_token or ""},
        ) as resp:
            return await resp.read()

    async def handle_codec(self, file: Audio) -> str:
        """
        Определяет кодек аудиофайла на основе его расширения.
        """
        codec = AudioFormat.get_codec(file.format)
        if not codec:
            raise ValueError(f"Unsupported audio format: {file}")
        return codec

    async def handle(self, file: Audio) -> list[TranscriptionItem] | None:
        result = None
        try:
            # self.handel_codec(file_path)
            # 1. Загрузка файла
            file_id = await self._handle("upload", file)
            logger.info(f"Файл загружен: {file_id}")

            codec = await self._handle("codec", file)
            logger.info(f"Кодек: {codec}")
            # 2. Запуск распознавания
            task_id = await self._handle("recognize", file_id, codec)
            logger.info(f"Задача создана: {task_id}")

            # 3. Отслеживание статуса
            while True:
                await asyncio.sleep(self.check_interval)
                status, response_id = await self._handle("status", task_id)

                match status:
                    case TaskStatus.NEW:
                        logger.info("Задача создана")
                    case TaskStatus.RUNNING:
                        logger.info("Задача в обработке")
                    case TaskStatus.CANCELED:
                        logger.info("\nЗадача отменена")
                        break
                    case TaskStatus.ERROR:
                        error = (await self._handle("status", task_id))[1]
                        logger.error(f"\nОшибка задачи: {error}", exc_info=True)
                        break
                    case TaskStatus.DONE:
                        logger.info(f"\nЗадача завершена: {response_id}")

                        # 4. Загрузка результатов
                        output = await self._handle("download", response_id)
                        result = [
                            TranscriptionItem(**item) for item in json.loads(output)
                        ]
                        break

        except aiohttp.ClientError as e:
            logger.error(f"Ошибка соединения: {str(e)}", exc_info=True)
        except Exception as e:
            logger.error(f"Ошибка: {str(e)}", exc_info=True)
        return result
