# Database (PostgreSQL)

Local PostgreSQL 16 for the pdf_reader services, run with Docker Compose.

## Run

From this directory (`services/db`):

```bash
docker compose up -d
```

Check that it is healthy:

```bash
docker compose ps
```

## Connect

```
postgresql://postgres:postgres@localhost:5432/pdf_reader
```

Open a `psql` shell inside the container:

```bash
docker compose exec postgres psql -U postgres -d pdf_reader
```

## Configuration

Override any of these with environment variables or a `.env` file in this directory:

| Variable            | Default      |
| ------------------- | ------------ |
| `POSTGRES_USER`     | `postgres`   |
| `POSTGRES_PASSWORD` | `postgres`   |
| `POSTGRES_DB`       | `pdf_reader` |
| `POSTGRES_PORT`     | `5432`       |

The defaults are for local development only. Set a real password anywhere else.

## Stop

```bash
docker compose down        # stop and remove the container, keep data
docker compose down -v     # also delete the data volume
```
