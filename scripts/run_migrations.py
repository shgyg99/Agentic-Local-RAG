from pathlib import Path

from psycopg2 import connect

from packages.retrieval.vector_db import postgres_urls

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "infrastructure" / "migrations"


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def run_migrations() -> None:
    sync_url, _ = postgres_urls()
    dsn = sync_url.set(drivername="postgresql").render_as_string(hide_password=False)
    with connect(dsn) as connection:
        with connection.cursor() as cursor:
            for migration_file in migration_files():
                cursor.execute(migration_file.read_text(encoding="utf-8"))
        connection.commit()


if __name__ == "__main__":
    run_migrations()
    print("Migrations applied.")
