import json
from typing import Coroutine
import aiohttp
import asyncio
from typing import Any
import logging
import datetime
import ssl
import aiohttp.client_exceptions as aiohttp_client_exp
import backoff
import certifi
import uuid

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


from src.client import BaseHTTPClient, HTTPMethods
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
    simultaneous_requests: int = Field(3, alias="SALUTE_SIMULTANEOUS_REQUESTS")


class SaluteSpeechHandler(Handler):
    class Config(SaluteSpeechConfig):
        name: str = Field(default="SaluteSpeechASR")

    def __init__(self, *args, **kwargs) -> None:
        self._access_token = None
        self._is_running = False
        self.config = self.Config(*args, **kwargs)
        self.ssl_default_context = ssl.create_default_context(cadata=certifi.contents())
        self._connector = None
        self.timeout = aiohttp.ClientTimeout(total=30, connect=10)
        resolver = aiohttp.AsyncResolver()
        self._connector = aiohttp.TCPConnector(
            resolver=resolver,
            ssl_context=self.ssl_default_context,
            keepalive_timeout=15,
            limit=None,
            limit_per_host=0,
            enable_cleanup_closed=True,
        )
        self.http_client = BaseHTTPClient(self._connector)
        self.semaphore = asyncio.Semaphore(self.config.simultaneous_requests)

    token_lock = asyncio.Lock()

    async def get_access_token(self):
        async with self.token_lock:
            return self.access_token

    async def set_access_token(self, token: str):
        async with self.token_lock:
            self.access_token = token

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

    async def make_request(
        self,
        method: str,
        url: str,
        data: dict = None,
        headers: dict = None,
        json: dict = None,
    ) -> dict | bytes:
        async with self.semaphore:
            return await self.http_client.make_request(
                url=url,
                method=method,
                headers=headers,
                data=data,
                json=json,
            )

    async def start(self) -> None:
        await self.http_client.start()
        await self._get_access_token()
        self._is_running = True

    async def stop(self) -> None:
        self._is_running = False

        if self._connector:
            await self._connector.close()

    async def suspended_task(task: Coroutine, timeout: int):
        await asyncio.sleep(timeout)
        asyncio.create_task(task, name=task.__name__)

    async def callback_get_access_token(self, timestamp_ms):
        dt = datetime.datetime.fromtimestamp(timestamp_ms / 1000)  # UTC время
        logger.info(f"Token will be expired in {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        now = datetime.datetime.now()
        two_minutes = datetime.timedelta(minutes=2.0)
        time_to_sleep = 0
        if now < dt:
            time_to_sleep = (dt - now - two_minutes).seconds

        await asyncio.sleep(time_to_sleep)
        logger.info("Token has been expired")
        logger.info("Start updating token")
        try:
            await self._get_access_token()
        except aiohttp.ClientConnectorError as _ex:
            logger.error(f"Got client error {_ex}", exc_info=True)
            asyncio.create_task(self.suspended_task(self._access_token(), 30))
        except TimeoutError as _ex:
            logger.error(f"Got {_ex}", exc_info=True)
            asyncio.create_task(self.suspended_task(self._access_token(), 30))
        except Exception as _ex:
            logger.error(f"Got another error {_ex}", exc_info=True)
            asyncio.create_task(self.suspended_task(self._access_token(), 30))

        logger.info("Token has been updated")

    @backoff.on_exception(
        backoff.expo,
        (
            TimeoutError,
            aiohttp_client_exp.ConnectionTimeoutError,
            aiohttp.ClientConnectorError,
            aiohttp_client_exp.ClientConnectionError,
            aiohttp.ClientResponseError,
            aiohttp.ServerTimeoutError,
            asyncio.TimeoutError,
            RuntimeError,
        ),
        max_tries=5,
        max_time=30,
        jitter=backoff.full_jitter,
    )
    async def _get_access_token(self):
        headers = {
            "RqUID": f"{uuid.uuid4()}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Bearer {self.credentials}",
        }
        data = {"scope": self.config.scope}
        data = await self.make_request(
            HTTPMethods.POST, self.url_access_token, headers=headers, data=data
        )

        access_token, exp = data["access_token"], data["expires_at"]
        await self.set_access_token(f"Bearer {access_token}")

        asyncio.create_task(
            self.callback_get_access_token(exp),
            name=self.callback_get_access_token.__name__,
        )

    @backoff.on_exception(
        backoff.expo,
        (
            TimeoutError,
            aiohttp_client_exp.ConnectionTimeoutError,
            aiohttp.ClientConnectorError,
            aiohttp_client_exp.ClientConnectionError,
            aiohttp.ClientResponseError,
            aiohttp.ServerTimeoutError,
            asyncio.TimeoutError,
            RuntimeError,
        ),
        max_tries=5,
        max_time=30,
        jitter=backoff.full_jitter,
    )
    async def handle_upload(self, file: Audio) -> str:
        url = f"{self.url_rest}/data:upload"
        form = aiohttp.FormData()
        form.add_field(
            name="audio_file1",
            value=file.file,
            filename=str(file),
            content_type="application/octet-stream",
        )
        logger.info(f"Request URL: {url}")
        logger.info(f"Payload size: {len(file.file)} bytes")
        logger.info(f"Payload: {form}")
        headers = {
            "Authorization": await self.get_access_token() or "",
        }

        data = await self.make_request(
            method=HTTPMethods.POST, url=url, headers=headers, data=form
        )

        return data["result"]["request_file_id"]

    @backoff.on_exception(
        backoff.expo,
        (
            TimeoutError,
            aiohttp_client_exp.ConnectionTimeoutError,
            aiohttp.ClientConnectorError,
            aiohttp_client_exp.ClientConnectionError,
            aiohttp.ClientResponseError,
            aiohttp.ServerTimeoutError,
            asyncio.TimeoutError,
            RuntimeError,
        ),
        max_tries=5,
        max_time=30,
        jitter=backoff.full_jitter,
    )
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
        headers = {
            "Content-Type": "application/json",
            "Authorization": await self.get_access_token() or "",
        }

        data = await self.make_request(
            method=HTTPMethods.POST, url=url, headers=headers, json=payload
        )
        return data["result"]["id"]

    @backoff.on_exception(
        backoff.expo,
        (
            TimeoutError,
            aiohttp_client_exp.ConnectionTimeoutError,
            aiohttp.ClientConnectorError,
            aiohttp_client_exp.ClientConnectionError,
            aiohttp.ClientResponseError,
            aiohttp.ServerTimeoutError,
            asyncio.TimeoutError,
            RuntimeError,
        ),
        max_tries=5,
        max_time=30,
        jitter=backoff.full_jitter,
    )
    async def handle_status(self, task_id: str) -> tuple[TaskStatus, str]:
        url = f"{self.url_rest}/task:get?id={task_id}"

        # type: ignore
        headers = {"Authorization": await self.get_access_token()}

        data = await self.make_request(HTTPMethods.GET, url, headers=headers)
        status = TaskStatus(data["result"]["status"])
        response_id = data["result"].get("response_file_id", "")
        return status, response_id

    async def handle_download(self, file_id: str) -> bytes:
        url = f"{self.url_rest}/data:download?response_file_id={file_id}"

        headers = {"Authorization": await self.get_access_token() or ""}

        return await self.make_request(HTTPMethods.GET, url, headers=headers)

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
                        logger.info("Задача отменена")
                        break
                    case TaskStatus.ERROR:
                        error = (await self._handle("status", task_id))[1]
                        logger.error(f"Ошибка задачи: {error}", exc_info=True)
                        break
                    case TaskStatus.DONE:
                        logger.info(f"Задача завершена: {response_id}")

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
