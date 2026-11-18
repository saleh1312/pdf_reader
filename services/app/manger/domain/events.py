"""Things that have happened in the domain, raised by aggregates."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    pass


@dataclass(frozen=True)
class Logging(Event):
    message: str
