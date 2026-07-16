# Infrastructure

Development infrastructure is defined in `docker-compose.yml`.

Database initialization currently consists of enabling the PostgreSQL `vector`
extension. The SQL migration is mirrored in
`infrastructure/migrations/001_create_vector_extension.sql` and in the Docker
Postgres init folder so new local databases are initialized automatically.
