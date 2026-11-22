"""Routes commands and events to their handlers.

After every handler, the bus asks the unit of work for the events the touched
users raised and queues them, so events caused by events are handled too.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from manger.domain import commands, events
from manger.services.unit_of_work import AbstractUnitOfWork

logger = logging.getLogger(__name__)

Message = commands.Command | events.Event
EventHandlers = dict[type[events.Event], list[Callable[[events.Event], None]]]
CommandHandlers = dict[type[commands.Command], Callable[[Any, AbstractUnitOfWork], Any]]


class MessageBus:
    def __init__(
        self,
        uow: AbstractUnitOfWork,
        event_handlers: EventHandlers,
        command_handlers: CommandHandlers,
    ):
        self.uow = uow
        self.event_handlers = event_handlers
        self.command_handlers = command_handlers

    def handle(self, message: Message) -> Any:
        """Handle the message and every event it leads to.

        Returns the command handler's result (e.g. the user id from sign in).
        """
        result = None
        self.queue: list[Message] = [message]
        while self.queue:
            message = self.queue.pop(0)
            if isinstance(message, events.Event):
                self.handle_event(message)
            elif isinstance(message, commands.Command):
                result = self.handle_command(message)
            else:
                raise Exception(f"{message} was not an Event or Command")
        return result

    def handle_event(self, event: events.Event) -> None:
        # A failing event handler is logged and skipped so the others still run.
        for handler in self.event_handlers[type(event)]:
            try:
                logger.debug("handling event %s with handler %s", event, handler)
                handler(event)
                self.queue.extend(self.uow.collect_new_events())
            except Exception:
                logger.exception("Exception handling event %s", event)
                continue

    def handle_command(self, command: commands.Command) -> Any:
        logger.debug("handling command %s", command)
        try:
            handler = self.command_handlers[type(command)]
            result = handler(command, self.uow)
            self.queue.extend(self.uow.collect_new_events())
            return result
        except Exception:
            logger.exception("Exception handling command %s", command)
            raise
