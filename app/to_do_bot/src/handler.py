from typing import Any, Protocol

from abc import ABC, abstractmethod


class Handler(Protocol):
    """
    Protocol for a handler that can process messages.
    """

    @abstractmethod
    def handle(self, *args: Any, **kwargs: Any):
        """
        Handle a message.
        """
        pass

    def start(self) -> None:
        """
        Start the handler.
        """
        pass

    def stop(self) -> None:
        """
        Stop the handler.
        """
        pass


class BaseWorker(ABC):
    """
    Abstract base class for workers
    """

    def __init__(self, handler: Handler):
        super().__init__()
        self.handler = handler
        self.handler.start()
