import os

from llama_index.vector_stores.postgres import PGVectorStore
from psycopg2 import connect, sql
from sqlalchemy import select
from sqlalchemy.engine import URL, make_url


TRUTHY_VALUES = {"1", "true", "yes", "on"}
DEFAULT_POSTGRES_DB = "vector_db"
DEFAULT_POSTGRES_HOST = "localhost"
DEFAULT_POSTGRES_PORT = 5432
DEFAULT_POSTGRES_USER = "postgres"
PLACEHOLDER_PASSWORD = "password"


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in TRUTHY_VALUES


def embedding_dim() -> int:
    explicit_dim = os.getenv("EMBED_DIM")
    if explicit_dim:
        return int(explicit_dim)

    embed_model = os.getenv("EMBED_MODEL", "")
    if embed_model == "text-embedding-3-large":
        return 3072
    return 1536


def local_postgres_url() -> URL:
    return URL.create(
        drivername="postgresql",
        username=os.getenv("POSTGRES_USER", DEFAULT_POSTGRES_USER),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST", DEFAULT_POSTGRES_HOST),
        port=int(os.getenv("POSTGRES_PORT", DEFAULT_POSTGRES_PORT)),
        database=os.getenv("POSTGRES_DB", DEFAULT_POSTGRES_DB),
    )


def _reject_placeholder_password(url: URL) -> None:
    if url.password == PLACEHOLDER_PASSWORD:
        raise RuntimeError(
            "Postgres password is still the placeholder value 'password'. "
            "Set POSTGRES_URL with the real Postgres password, or remove "
            "POSTGRES_URL and set POSTGRES_PASSWORD to the real password."
        )


def _postgres_dsn(url: URL) -> str:
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def _sqlalchemy_url(url: URL) -> str:
    return url.render_as_string(hide_password=False)


def ensure_database_exists(url: URL) -> None:
    database = url.database
    if not database:
        raise RuntimeError("Postgres URL must include a database name.")

    maintenance_url = url.set(database=os.getenv("POSTGRES_MAINTENANCE_DB", "postgres"))
    connection = None
    try:
        connection = connect(_postgres_dsn(maintenance_url))
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (database,),
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database))
                )
    except Exception as exc:
        raise RuntimeError(
            "Could not connect to Postgres or create the database "
            f"{database!r} on {url.host or DEFAULT_POSTGRES_HOST}:{url.port or DEFAULT_POSTGRES_PORT}. "
            "Check POSTGRES_URL, or configure POSTGRES_HOST, POSTGRES_PORT, "
            "POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB."
        ) from exc
    finally:
        if connection is not None:
            connection.close()


def postgres_urls():
    connection_url = os.getenv("POSTGRES_URL")
    url = make_url(connection_url) if connection_url else local_postgres_url()
    if not url.database:
        raise RuntimeError("POSTGRES_URL must include a database name.")
    _reject_placeholder_password(url)

    auto_create_db = env_flag("POSTGRES_AUTO_CREATE_DB", default=not bool(connection_url))
    if auto_create_db:
        ensure_database_exists(url)

    sync_url = url.set(drivername="postgresql+psycopg2")
    async_url = os.getenv("POSTGRES_ASYNC_URL")
    if async_url:
        async_url = make_url(async_url).set(drivername="postgresql+asyncpg")
    else:
        async_url = url.set(drivername="postgresql+asyncpg")

    return sync_url, async_url


def get_vector_store() -> PGVectorStore:
    sync_url, async_url = postgres_urls()
    embed_dim = embedding_dim()
    hnsw_kwargs = None
    if embed_dim <= 2000:
        hnsw_kwargs = {
            "hnsw_m": 16,
            "hnsw_ef_construction": 64,
            "hnsw_ef_search": 40,
            "hnsw_dist_method": "vector_cosine_ops",
        }

    return PGVectorStore.from_params(
        connection_string=_sqlalchemy_url(sync_url),
        async_connection_string=_sqlalchemy_url(async_url),
        table_name=os.getenv("PGVECTOR_TABLE", "documents"),
        schema_name=os.getenv("PGVECTOR_SCHEMA", "public"),
        embed_dim=embed_dim,
        use_jsonb=True,
        hnsw_kwargs=hnsw_kwargs,
    )


def clear_vector_store(vector_store: PGVectorStore) -> None:
    vector_store.clear()


def indexed_sources(vector_store: PGVectorStore) -> set[str]:
    vector_store._initialize()
    with vector_store._session() as session:
        source_field = vector_store._table_class.metadata_["source"].astext
        stmt = select(source_field).distinct()
        return {row[0] for row in session.execute(stmt) if row[0]}


def indexed_ingestion_versions(vector_store: PGVectorStore) -> set[str]:
    vector_store._initialize()
    with vector_store._session() as session:
        version_field = vector_store._table_class.metadata_["ingestion_version"].astext
        stmt = select(version_field).distinct()
        return {row[0] for row in session.execute(stmt) if row[0]}
