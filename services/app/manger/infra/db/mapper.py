"""SQLAlchemy imperative (classical) mapping for the domain model.

Tables are defined here and attached to the plain domain classes at runtime,
so `manger.domain` stays free of any ORM imports. Call `start_mappers()` once
at application startup, before any session is used.
"""

from sqlalchemy import (
    Column,
    Engine,
    Enum,
    ForeignKey,
    MetaData,
    String,
    Table,
    Uuid,
    event,
)
from sqlalchemy.orm import composite, registry, relationship

from manger.domain import Book, StorageLocation, StorageProvider, User

metadata = MetaData()
mapper_registry = registry(metadata=metadata)

users = Table(
    "users",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("name", String(255), nullable=False),
    Column("username", String(255), nullable=False, unique=True),
    Column("password_hash", String(255), nullable=False),
)

books = Table(
    "books",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "user_id",
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("name", String(255), nullable=False),
    Column(
        "storage_provider",
        Enum(
            StorageProvider,
            name="storage_provider",
            values_callable=lambda e: [m.value for m in e],  # store "s3"/"local"
        ),
        nullable=False,
    ),
    Column("storage_key", String(1024), nullable=False),
)

_mapped = False


def start_mappers() -> None:
    global _mapped
    if _mapped:
        return

    mapper_registry.map_imperatively(
        Book,
        books,
        properties={
            "location": composite(
                StorageLocation, books.c.storage_provider, books.c.storage_key
            ),
        },
    )
    mapper_registry.map_imperatively(
        User,
        users,
        properties={
            # Books belong to exactly one user: User is the aggregate root,
            # so books are saved and deleted through it.
            "books": relationship(
                Book, cascade="all, delete-orphan", lazy="selectin"
            ),
        },
    )
    event.listen(User, "load", _init_user_events)
    _mapped = True


def _init_user_events(user: User, _context) -> None:
    # Users loaded from the database skip __init__, so `events` is never set.
    user.events = []


def init_db(engine: Engine) -> None:
    """Create any missing tables and types; existing ones are left untouched."""
    metadata.create_all(engine, checkfirst=True)


def drop_db(engine: Engine) -> None:
    """Drop every table and type defined here, deleting all their data."""
    metadata.drop_all(engine, checkfirst=True)


def clear_db(engine: Engine) -> None:
    """Delete every row from every table, keeping the schema."""
    with engine.begin() as connection:
        # Children before parents, so foreign keys are never violated.
        for table in reversed(metadata.sorted_tables):
            connection.execute(table.delete())
