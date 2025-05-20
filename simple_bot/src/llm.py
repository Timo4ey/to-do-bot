import httpcore
import yaml  # type: ignore
import pydantic
from pydantic_settings import BaseSettings, SettingsConfigDict
import certifi
import ssl


from langchain_gigachat import GigaChat
from langchain_core.messages import BaseMessage
import backoff
import httpx

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

    def start(self) -> None:
        self.llm = GigaChat(
            credentials=self.api_key,  # type: ignore
            temperature=self.temperature,
            ssl_context=ssl.create_default_context(cadata=certifi.contents()),
        )

    @backoff.on_exception(
        backoff.expo,
        (TimeoutError, httpcore.ConnectTimeout, httpx.ConnectTimeout),
        max_tries=5,
        max_time=30,
        jitter=backoff.full_jitter,
    )
    async def handle(self, topic: str, message: str) -> BaseMessage:
        if topic not in self.system_prompts:
            raise ValueError(
                f"Unknown topic: {topic}. Available topics: {list(self.system_prompts.keys())}"
            )
        system_message: str = self.system_prompts[topic]

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": message},
        ]
        response: BaseMessage = await self.llm.ainvoke(messages)

        return response

    def stop(self):
        return super().stop()


def parse_config(file_path: str) -> dict:
    with open(file_path, "r") as f:
        return yaml.safe_load(f)
