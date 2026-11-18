"""Requests for the system to do something; each has exactly one handler."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Command:
    pass


# Passwords are excluded from repr so commands can be logged safely.


@dataclass(frozen=True)
class SignUp(Command):
    name: str
    username: str
    password: str = field(repr=False)


@dataclass(frozen=True)
class SignIn(Command):
    username: str
    password: str = field(repr=False)
