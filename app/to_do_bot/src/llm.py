import asyncio
import logging
from gigachat import GigaChat as CoreGigaChat
import yaml  # type: ignore
import ssl

from pydantic_settings import BaseSettings, SettingsConfigDict
import certifi
import pydantic
from langchain_gigachat import GigaChat
from langchain_core.messages import BaseMessage
import backoff
import httpx
import httpcore

from src.handler import Handler


class GigaChatLLMConfig(BaseSettings):
    system_prompts: dict[str, str] = pydantic.Field(
        default={
            "system": "You are a helpful assistant.",
            "user": "How can I assist you today?",
        },
        alias="GIGACHAT_SYSTEM_PROMPTS",
    )
    api_key: str = pydantic.Field(..., alias="GIGACHAT_API_KEY")
    temperature: float = pydantic.Field(0.43, alias="GIGACHAT_TEMPERATURE")
    simultaneous_requests: int = pydantic.Field(
        1, alias="GIGACHAT_SIMULTANEOUS_REQUESTS"
    )

    model_config = SettingsConfigDict(extra="ignore")


class GigaChatLLM(Handler):
    class Config(GigaChatLLMConfig):
        name: str = pydantic.Field(default="GigaChatLLM")

    @property
    def api_key(self) -> str:
        return self.config.api_key

    @property
    def system_prompts(self) -> dict[str, str]:
        return self.config.system_prompts

    @property
    def temperature(self) -> float:
        return self.config.temperature

    def __init__(self, *args, **kwargs) -> None:
        self.llm = None
        self.config = self.Config(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

    @property
    def client(self) -> CoreGigaChat:
        return self.llm._client

    def start(self) -> None:
        self.llm = GigaChat(
            credentials=self.api_key,  # type: ignore
            temperature=self.temperature,
            ssl_context=ssl.create_default_context(cadata=certifi.contents()),
            # model="GigaChat-MA"
        )
        self.logger.info(f"LLM initialized with model: {self.llm.model}")
        self.logger.info(f"Simultaneous requests: {self.config.simultaneous_requests}")
        self.semaphore = asyncio.Semaphore(self.config.simultaneous_requests)
        self.logger.info("LLM started")

    @backoff.on_exception(
        backoff.expo,
        (TimeoutError, httpcore.ConnectTimeout, httpx.ConnectTimeout),
        max_tries=5,
        max_time=30,
        jitter=backoff.full_jitter,
    )
    async def handle(self, topic: str, message: str) -> BaseMessage:
        if topic not in self.system_prompts:
            self.logger.error(f"The topic {topic} has not been found")
            raise ValueError(
                f"Unknown topic: {topic}. Available topics: {list(self.system_prompts.keys())}"
            )
        self.logger.info(f"Start processing {topic}: {message}")
        system_message: str = self.system_prompts[topic]
        tokens = self.client.tokens_count(
            [system_message, message], model=self.llm.model
        )
        self.logger.info(f"Total tokens: {tokens}")
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": message},
        ]
        async with self.semaphore:
            response: BaseMessage = await self.llm.ainvoke(messages)
        self.logger.info(f"Response: {response=}")
        return response

    def stop(self):
        return super().stop()


def parse_config(file_path: str) -> dict:
    with open(file_path, "r") as f:
        return yaml.safe_load(f)
