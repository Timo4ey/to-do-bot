import abc
from enum import Enum
from typing import Optional, Union, overload
import logging

import aiohttp


class HTTPMethods(str, Enum):
    GET = "get"
    POST = "post"
    PUT = "put"
    DELETE = "delete"


class AbstractClient(abc.ABC):
    @abc.abstractmethod
    async def make_request(self, *args, **kwargs):
        pass

    @abc.abstractmethod
    async def start(self):
        pass

    @abc.abstractmethod
    async def stop(self):
        pass


class BaseHTTPClient(AbstractClient):
    def __init__(self, connector: aiohttp.BaseConnector = None):
        super().__init__()
        self._connector = connector
        self._session = None
        self.logger = logging.getLogger(self.__class__.__name__)

    @property
    def session(self) -> aiohttp.ClientSession:
        if not self._session:
            self._session = aiohttp.ClientSession(connector=self._connector)
        return self._session

    @overload
    async def make_request(
        self,
        url: str,
        method: HTTPMethods = HTTPMethods.GET,
        headers: dict = None,
        data: str | bytes | dict = None,
        json: dict = None,
    ) -> dict:
        pass

    @overload
    async def make_request(
        self,
        url: str,
        method: HTTPMethods = HTTPMethods.GET,
        headers: dict = None,
        data: str | bytes | dict = None,
        json: dict = None,
    ) -> bytes:
        pass

    async def make_request(
        self,
        method: HTTPMethods,
        url: str,
        headers: Optional[dict] = None,
        data: Optional[Union[str, bytes, dict, aiohttp.FormData]] = None,
        json: Optional[dict] = None,
    ):
        output = None
        self.logger.info(f"Making request to {url} with method {method}")
        if method := getattr(self.session, method, None):
            kwargs = {}
            if headers:
                kwargs["headers"] = headers
            if data:
                kwargs["data"] = data
            if json:
                kwargs["json"] = json

            response: aiohttp.ClientResponse | None
            async with method(url, **kwargs) as response:
                self.logger.info(f"Status: {response.status}")
                self.logger.info(f"{response.headers.get("Content-Type")=}")
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "").split(";")[0]
                match content_type:
                    case "application/json":
                        output = await response.json()
                    case _:
                        output = await response.read()
            self.logger.info(f"Response: {output}")
            return output
        raise ValueError("Unknown method")

    async def start(self):
        if not self._session:
            self._session = aiohttp.ClientSession(connector=self._connector)
        self.logger.info("Started client")

    async def stop(self):
        await self._session.close()
        self.logger.info("Stopped client")

    async def restart(self):
        await self.stop()
        await self.start()
