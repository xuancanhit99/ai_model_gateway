from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_pool_lock = threading.Lock()
_pool: Optional[ConnectionPool] = None
_client: Optional["PostgresCompatClient"] = None


def _parse_columns(select_clause: str) -> List[str]:
    if select_clause.strip() == "*":
        return ["*"]
    return [part.strip() for part in select_clause.split(",") if part.strip()]


@dataclass
class DBResponse:
    data: Any = None
    error: Optional[str] = None


class TableQuery:
    def __init__(self, pool: ConnectionPool, table_name: str) -> None:
        self.pool = pool
        self.table_name = table_name
        self._action: Optional[str] = None
        self._select_columns: List[str] = ["*"]
        self._insert_rows: Optional[List[Dict[str, Any]]] = None
        self._update_data: Optional[Dict[str, Any]] = None
        self._filters: List[tuple[str, Any]] = []
        self._order_by: List[tuple[str, bool]] = []
        self._limit: Optional[int] = None
        self._maybe_single = False

    def select(self, columns: str) -> "TableQuery":
        self._action = "select"
        self._select_columns = _parse_columns(columns)
        return self

    def insert(self, rows: Dict[str, Any] | List[Dict[str, Any]]) -> "TableQuery":
        self._action = "insert"
        self._insert_rows = rows if isinstance(rows, list) else [rows]
        return self

    def update(self, data: Dict[str, Any]) -> "TableQuery":
        self._action = "update"
        self._update_data = data
        return self

    def delete(self) -> "TableQuery":
        self._action = "delete"
        return self

    def eq(self, column: str, value: Any) -> "TableQuery":
        self._filters.append((column, value))
        return self

    def order(self, column: str, desc: bool = False) -> "TableQuery":
        self._order_by.append((column, desc))
        return self

    def limit(self, value: int) -> "TableQuery":
        self._limit = value
        return self

    def maybe_single(self) -> "TableQuery":
        self._maybe_single = True
        return self

    def _build_where(self) -> tuple[sql.SQL, List[Any]]:
        if not self._filters:
            return sql.SQL(""), []

        clauses: List[sql.Composable] = []
        params: List[Any] = []
        for column, value in self._filters:
            clauses.append(sql.SQL("{} = %s").format(sql.Identifier(column)))
            params.append(value)
        where_sql = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(clauses)
        return where_sql, params

    def execute(self) -> DBResponse:
        action = self._action or "select"
        table_ident = sql.Identifier(self.table_name)

        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                if action == "select":
                    if self._select_columns == ["*"]:
                        columns_sql = sql.SQL("*")
                    else:
                        columns_sql = sql.SQL(", ").join(
                            [sql.Identifier(col) for col in self._select_columns]
                        )
                    where_sql, params = self._build_where()
                    query = sql.SQL("SELECT {} FROM {}").format(columns_sql, table_ident) + where_sql
                    if self._order_by:
                        order_parts = []
                        for col, desc in self._order_by:
                            order_parts.append(
                                sql.SQL("{} {}").format(
                                    sql.Identifier(col),
                                    sql.SQL("DESC" if desc else "ASC"),
                                )
                            )
                        query += sql.SQL(" ORDER BY ") + sql.SQL(", ").join(order_parts)
                    if self._limit is not None:
                        query += sql.SQL(" LIMIT %s")
                        params.append(self._limit)
                    cur.execute(query, params)
                    rows = cur.fetchall()
                    if self._maybe_single:
                        return DBResponse(data=rows[0] if rows else None)
                    return DBResponse(data=rows)

                if action == "insert":
                    rows = self._insert_rows or []
                    if not rows:
                        return DBResponse(data=[])
                    columns = list(rows[0].keys())
                    values_sql_parts: List[sql.Composable] = []
                    params: List[Any] = []
                    for row in rows:
                        row_values = [row.get(col) for col in columns]
                        params.extend(row_values)
                        values_sql_parts.append(
                            sql.SQL("(") + sql.SQL(", ").join([sql.Placeholder()] * len(columns)) + sql.SQL(")")
                        )
                    query = (
                        sql.SQL("INSERT INTO {} ({}) VALUES ").format(
                            table_ident,
                            sql.SQL(", ").join([sql.Identifier(col) for col in columns]),
                        )
                        + sql.SQL(", ").join(values_sql_parts)
                        + sql.SQL(" RETURNING *")
                    )
                    cur.execute(query, params)
                    data = cur.fetchall()
                    conn.commit()
                    return DBResponse(data=data)

                if action == "update":
                    if not self._update_data:
                        return DBResponse(data=[])
                    set_clauses = []
                    params: List[Any] = []
                    for col, value in self._update_data.items():
                        set_clauses.append(sql.SQL("{} = %s").format(sql.Identifier(col)))
                        params.append(value)
                    where_sql, where_params = self._build_where()
                    params.extend(where_params)
                    query = (
                        sql.SQL("UPDATE {} SET ").format(table_ident)
                        + sql.SQL(", ").join(set_clauses)
                        + where_sql
                        + sql.SQL(" RETURNING *")
                    )
                    cur.execute(query, params)
                    data = cur.fetchall()
                    conn.commit()
                    return DBResponse(data=data)

                if action == "delete":
                    where_sql, params = self._build_where()
                    query = sql.SQL("DELETE FROM {}").format(table_ident) + where_sql + sql.SQL(" RETURNING *")
                    cur.execute(query, params)
                    data = cur.fetchall()
                    conn.commit()
                    return DBResponse(data=data)

                raise ValueError(f"Unsupported query action: {action}")


class PostgresCompatClient:
    def __init__(self, pool: ConnectionPool) -> None:
        self.pool = pool

    def table(self, table_name: str) -> TableQuery:
        return TableQuery(self.pool, table_name)

    def fetch_all(self, query: str, params: Sequence[Any] | None = None) -> List[Dict[str, Any]]:
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, params or ())
                return cur.fetchall()

    def fetch_one(self, query: str, params: Sequence[Any] | None = None) -> Optional[Dict[str, Any]]:
        rows = self.fetch_all(query, params)
        return rows[0] if rows else None

    def execute(self, query: str, params: Sequence[Any] | None = None) -> None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                conn.commit()

    def execute_returning(self, query: str, params: Sequence[Any] | None = None) -> List[Dict[str, Any]]:
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, params or ())
                rows = cur.fetchall()
                conn.commit()
                return rows


def _run_db_migrations(pool: ConnectionPool) -> None:
    settings = get_settings()
    if not settings.DB_AUTO_MIGRATE:
        logger.info("DB auto-migration disabled (DB_AUTO_MIGRATE=false).")
        return

    migrations_dir = Path(__file__).resolve().parents[2] / "db" / "migrations"
    sql_files = sorted(migrations_dir.glob("*.sql"))
    if not sql_files:
        logger.warning("No migration files found in %s", migrations_dir)
        return

    with pool.connection() as conn:
        conn.autocommit = True
        migration_error: Optional[Exception] = None
        with conn.cursor() as cur:
            # Cross-process lock so multiple workers do not run DDL concurrently.
            cur.execute("SELECT pg_advisory_lock(hashtext('ai_gateway_schema_migrate'));")
            try:
                for sql_file in sql_files:
                    sql_content = sql_file.read_text(encoding="utf-8")
                    if not sql_content.strip():
                        continue
                    cur.execute(sql_content)
                    logger.info("Applied migration: %s", sql_file.name)
            except Exception as err:
                migration_error = err
                # Clear failed transaction state (BEGIN/COMMIT files can leave the session aborted).
                conn.rollback()
            finally:
                try:
                    cur.execute("SELECT pg_advisory_unlock(hashtext('ai_gateway_schema_migrate'));")
                except Exception:
                    logger.exception("Failed to release migration advisory lock.")

        if migration_error:
            raise migration_error


def init_db_pool() -> ConnectionPool:
    global _pool, _client
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                settings = get_settings()
                if not settings.DATABASE_URL:
                    raise ValueError("DATABASE_URL is not configured.")
                _pool = ConnectionPool(
                    conninfo=settings.DATABASE_URL,
                    min_size=max(settings.DB_POOL_MIN_SIZE, 1),
                    max_size=max(settings.DB_POOL_MAX_SIZE, 1),
                    kwargs={"row_factory": dict_row},
                    open=True,
                )
                _client = PostgresCompatClient(_pool)
                _run_db_migrations(_pool)
                logger.info("PostgreSQL connection pool initialized.")
    return _pool


def close_db_pool() -> None:
    global _pool, _client
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None
            _client = None
            logger.info("PostgreSQL connection pool closed.")


def get_db_client() -> PostgresCompatClient:
    init_db_pool()
    assert _client is not None
    return _client
