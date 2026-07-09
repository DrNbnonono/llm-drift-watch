#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = Path(os.environ.get("QUESTION_BANK_SQLITE_PATH", ROOT / "manifests" / "evaluation.sqlite"))
DEFAULT_LEGACY_CONFIG_PATH = ROOT / "config" / "providers.json"
DEFAULT_RUNS_DIR = ROOT / "manifests" / "evaluation_runs"
DEFAULT_BANK_ITEMS_PATH = ROOT / "final_bank_specs" / "generated" / "final_bank_items.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def json_loads(value: str | None, default: Any) -> Any:
    if value in (None, ""):
        return default
    return json.loads(value)


class SQLiteStore:
    def __init__(
        self,
        db_path: Path | None = None,
        legacy_config_path: Path | None = None,
        runs_dir: Path | None = None,
        bank_items_path: Path | None = None,
    ):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.legacy_config_path = Path(legacy_config_path or DEFAULT_LEGACY_CONFIG_PATH)
        self.runs_dir = Path(runs_dir or DEFAULT_RUNS_DIR)
        self.bank_items_path = Path(bank_items_path or DEFAULT_BANK_ITEMS_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self.bootstrap_legacy()

    def _connect(self) -> sqlite3.Connection:
        def _open() -> sqlite3.Connection:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        conn = _open()
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            return conn
        except sqlite3.OperationalError as exc:
            if "disk I/O error" not in str(exc):
                conn.close()
                raise
            conn.close()
            for suffix in ("-shm", "-wal"):
                sidecar = Path(f"{self.db_path}{suffix}")
                if sidecar.exists():
                    try:
                        sidecar.unlink()
                    except OSError:
                        pass
            conn = _open()
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("PRAGMA synchronous=NORMAL")
            return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS providers (
                    provider_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    protocol TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    auth_scheme TEXT NOT NULL,
                    auth_env TEXT NOT NULL,
                    headers_template_json TEXT NOT NULL,
                    model_lookup_mode TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS models (
                    model_alias TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    default_timeout INTEGER NOT NULL,
                    default_max_tokens INTEGER NOT NULL,
                    supports_multi_turn INTEGER NOT NULL DEFAULT 1,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (provider_id) REFERENCES providers(provider_id) ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    connection_id TEXT,
                    connection_name TEXT,
                    provider_id TEXT,
                    model_alias TEXT,
                    model_name TEXT,
                    base_url TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    bank_version TEXT,
                    status TEXT,
                    execution_status TEXT,
                    run_kind TEXT,
                    parent_run_id TEXT,
                    retry_policy TEXT,
                    source_failed_question_ids_json TEXT,
                    config_json TEXT,
                    progress_json TEXT,
                    totals_json TEXT,
                    summary_metrics_json TEXT,
                    report_path TEXT,
                    canonical_summary_path TEXT,
                    error TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS bank_items (
                    question_id TEXT PRIMARY KEY,
                    version TEXT,
                    module TEXT NOT NULL,
                    subtype TEXT,
                    item_format TEXT NOT NULL,
                    prompt_template TEXT,
                    turn_script_json TEXT,
                    ground_truth_json TEXT,
                    scoring_method TEXT NOT NULL,
                    scoring_params_json TEXT,
                    rotation_policy_json TEXT,
                    provenance_json TEXT,
                    search_text TEXT NOT NULL,
                    full_item_json TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS model_connections (
                    connection_id TEXT PRIMARY KEY,
                    vendor_name TEXT NOT NULL,
                    note TEXT,
                    homepage_url TEXT,
                    display_name TEXT NOT NULL,
                    protocol TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    auth_scheme TEXT NOT NULL,
                    auth_env TEXT NOT NULL,
                    encrypted_api_key TEXT,
                    provider_id TEXT NOT NULL,
                    model_alias TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    default_timeout INTEGER NOT NULL,
                    default_max_tokens INTEGER NOT NULL,
                    supports_multi_turn INTEGER NOT NULL DEFAULT 1,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    headers_template_json TEXT NOT NULL,
                    model_lookup_mode TEXT NOT NULL,
                    advanced_json TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (provider_id) REFERENCES providers(provider_id) ON DELETE RESTRICT,
                    FOREIGN KEY (model_alias) REFERENCES models(model_alias) ON DELETE RESTRICT
                );
                CREATE INDEX IF NOT EXISTS idx_model_connections_vendor ON model_connections(vendor_name);
                CREATE INDEX IF NOT EXISTS idx_model_connections_enabled ON model_connections(enabled);

                CREATE TABLE IF NOT EXISTS run_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    module TEXT NOT NULL,
                    item_format TEXT NOT NULL,
                    score_method TEXT NOT NULL,
                    primary_score REAL,
                    aux_score REAL,
                    status TEXT NOT NULL,
                    response_json TEXT,
                    score_details_json TEXT,
                    error TEXT,
                    failure_type TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    latency_ms INTEGER,
                    provider_id TEXT,
                    model_alias TEXT,
                    attempt_run_id TEXT,
                    source_run_id TEXT,
                    is_retry_attempt INTEGER NOT NULL DEFAULT 0,
                    canonical_selected INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(run_id, question_id, attempt_run_id),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_run_items_run_id ON run_items(run_id);
                CREATE INDEX IF NOT EXISTS idx_run_items_question_id ON run_items(question_id);
                CREATE INDEX IF NOT EXISTS idx_runs_parent_run_id ON runs(parent_run_id);
                CREATE INDEX IF NOT EXISTS idx_bank_items_module ON bank_items(module);
                CREATE INDEX IF NOT EXISTS idx_bank_items_subtype ON bank_items(subtype);
                CREATE INDEX IF NOT EXISTS idx_bank_items_item_format ON bank_items(item_format);

                CREATE TABLE IF NOT EXISTS module_dict (
                    code TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    parent_group TEXT NOT NULL DEFAULT 'capability',
                    color_token TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_module_dict_parent ON module_dict(parent_group);

                CREATE TABLE IF NOT EXISTS subtype_dict (
                    code TEXT PRIMARY KEY,
                    module_code TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (module_code) REFERENCES module_dict(code) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_subtype_dict_module ON subtype_dict(module_code);

                CREATE TABLE IF NOT EXISTS quota_tag_dict (
                    code TEXT PRIMARY KEY,
                    module_code TEXT,
                    display_name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (module_code) REFERENCES module_dict(code) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_quota_tag_dict_module ON quota_tag_dict(module_code);
                """
            )
            self._ensure_column(conn, "runs", "connection_id", "TEXT")
            self._ensure_column(conn, "runs", "connection_name", "TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_connection_id ON runs(connection_id)")
            self._ensure_column(conn, "bank_items", "version", "TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_items_version ON bank_items(version)")
            self._ensure_column(conn, "bank_items", "qa_status", "TEXT NOT NULL DEFAULT 'ready'")
            conn.execute("UPDATE bank_items SET qa_status = 'ready' WHERE qa_status IS NULL OR qa_status = ''")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_items_qa_status ON bank_items(qa_status)")
            self._ensure_column(conn, "bank_items", "difficulty", "TEXT")
            self._ensure_column(conn, "bank_items", "drift_role", "TEXT")
            self._ensure_column(conn, "bank_items", "module_quota_tag", "TEXT")
            self._ensure_column(conn, "bank_items", "notes", "TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_items_difficulty ON bank_items(difficulty)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_items_drift_role ON bank_items(drift_role)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_items_module_quota_tag ON bank_items(module_quota_tag)")
            # Backfill: copy from full_item_json for any rows missing the new columns
            for col in ("difficulty", "drift_role", "module_quota_tag", "notes"):
                nulls = conn.execute(
                    f"SELECT question_id, full_item_json FROM bank_items WHERE {col} IS NULL OR {col} = ''"
                ).fetchall()
                for row in nulls:
                    item = json_loads(row["full_item_json"], {})
                    value = item.get(col) or ""
                    conn.execute(
                        f"UPDATE bank_items SET {col} = ? WHERE question_id = ?",
                        (str(value), row["question_id"]),
                    )
            rows = conn.execute(
                "SELECT question_id, full_item_json FROM bank_items WHERE version IS NULL OR version = ''"
            ).fetchall()
            for row in rows:
                item = json_loads(row["full_item_json"], {})
                conn.execute(
                    "UPDATE bank_items SET version = ? WHERE question_id = ?",
                    (item.get("version") or "", row["question_id"]),
                )

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, sql_type: str) -> None:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        if any(row["name"] == column for row in rows):
            return
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")

    def bootstrap_legacy(self) -> None:
        self.bootstrap_bank_items()
        if self.count_rows("providers") == 0 and self.legacy_config_path.exists():
            payload = json.loads(self.legacy_config_path.read_text(encoding="utf-8"))
            for provider in payload.get("providers", []):
                self.upsert_provider(provider)
            for model in payload.get("models", []):
                self.upsert_model(model)
        self.import_all_runs()

    def count_rows(self, table: str) -> int:
        with self._connect() as conn:
            row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
        return int(row["n"])

    def bootstrap_bank_items(self) -> None:
        if not self.bank_items_path.exists():
            return
        on_disk = load_jsonl(self.bank_items_path)
        if self.count_rows("bank_items") != len(on_disk):
            self.replace_bank_items(on_disk)

    def upsert_provider(self, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO providers (
                    provider_id, display_name, protocol, base_url, auth_scheme, auth_env,
                    headers_template_json, model_lookup_mode, enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    protocol=excluded.protocol,
                    base_url=excluded.base_url,
                    auth_scheme=excluded.auth_scheme,
                    auth_env=excluded.auth_env,
                    headers_template_json=excluded.headers_template_json,
                    model_lookup_mode=excluded.model_lookup_mode,
                    enabled=excluded.enabled,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    payload["provider_id"],
                    payload["display_name"],
                    payload["protocol"],
                    payload["base_url"],
                    payload["auth_scheme"],
                    payload.get("auth_env", ""),
                    json_dumps(payload.get("headers_template", {})),
                    payload.get("model_lookup_mode", "skip"),
                    1 if payload.get("enabled", True) else 0,
                ),
            )

    def upsert_model(self, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO models (
                    model_alias, provider_id, display_name, model_name,
                    default_timeout, default_max_tokens, supports_multi_turn, enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(model_alias) DO UPDATE SET
                    provider_id=excluded.provider_id,
                    display_name=excluded.display_name,
                    model_name=excluded.model_name,
                    default_timeout=excluded.default_timeout,
                    default_max_tokens=excluded.default_max_tokens,
                    supports_multi_turn=excluded.supports_multi_turn,
                    enabled=excluded.enabled,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    payload["model_alias"],
                    payload["provider_id"],
                    payload["display_name"],
                    payload["model_name"],
                    int(payload.get("default_timeout", 45)),
                    int(payload.get("default_max_tokens", 512)),
                    1 if payload.get("supports_multi_turn", True) else 0,
                    1 if payload.get("enabled", True) else 0,
                ),
            )

    def delete_provider(self, provider_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM providers WHERE provider_id = ?", (provider_id,))

    def delete_model(self, model_alias: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM models WHERE model_alias = ?", (model_alias,))

    def upsert_model_connection(self, payload: dict[str, Any]) -> None:
        connection_id = payload.get("connection_id") or f"conn_{uuid.uuid4().hex[:12]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO model_connections (
                    connection_id, vendor_name, note, homepage_url, display_name, protocol,
                    base_url, auth_scheme, auth_env, encrypted_api_key, provider_id, model_alias,
                    model_name, default_timeout, default_max_tokens, supports_multi_turn, enabled,
                    headers_template_json, model_lookup_mode, advanced_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(connection_id) DO UPDATE SET
                    vendor_name=excluded.vendor_name,
                    note=excluded.note,
                    homepage_url=excluded.homepage_url,
                    display_name=excluded.display_name,
                    protocol=excluded.protocol,
                    base_url=excluded.base_url,
                    auth_scheme=excluded.auth_scheme,
                    auth_env=excluded.auth_env,
                    encrypted_api_key=excluded.encrypted_api_key,
                    provider_id=excluded.provider_id,
                    model_alias=excluded.model_alias,
                    model_name=excluded.model_name,
                    default_timeout=excluded.default_timeout,
                    default_max_tokens=excluded.default_max_tokens,
                    supports_multi_turn=excluded.supports_multi_turn,
                    enabled=excluded.enabled,
                    headers_template_json=excluded.headers_template_json,
                    model_lookup_mode=excluded.model_lookup_mode,
                    advanced_json=excluded.advanced_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    connection_id,
                    payload["vendor_name"],
                    payload.get("note"),
                    payload.get("homepage_url"),
                    payload["display_name"],
                    payload["protocol"],
                    payload["base_url"],
                    payload["auth_scheme"],
                    payload.get("auth_env", ""),
                    payload.get("encrypted_api_key"),
                    payload["provider_id"],
                    payload["model_alias"],
                    payload["model_name"],
                    int(payload.get("default_timeout", 45)),
                    int(payload.get("default_max_tokens", 512)),
                    1 if payload.get("supports_multi_turn", True) else 0,
                    1 if payload.get("enabled", True) else 0,
                    json_dumps(payload.get("headers_template", {})),
                    payload.get("model_lookup_mode", "skip"),
                    json_dumps(payload.get("advanced", {})),
                ),
            )

    def delete_model_connection(self, connection_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM model_connections WHERE connection_id = ?", (connection_id,))

    def load_model_connections(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM model_connections ORDER BY updated_at DESC, connection_id DESC").fetchall()
        return [
            {
                "connection_id": row["connection_id"],
                "vendor_name": row["vendor_name"],
                "note": row["note"],
                "homepage_url": row["homepage_url"],
                "display_name": row["display_name"],
                "protocol": row["protocol"],
                "base_url": row["base_url"],
                "auth_scheme": row["auth_scheme"],
                "auth_env": row["auth_env"],
                "encrypted_api_key": row["encrypted_api_key"],
                "provider_id": row["provider_id"],
                "model_alias": row["model_alias"],
                "model_name": row["model_name"],
                "default_timeout": int(row["default_timeout"]),
                "default_max_tokens": int(row["default_max_tokens"]),
                "supports_multi_turn": bool(row["supports_multi_turn"]),
                "enabled": bool(row["enabled"]),
                "headers_template": json_loads(row["headers_template_json"], {}),
                "model_lookup_mode": row["model_lookup_mode"],
                "advanced": json_loads(row["advanced_json"], {}),
            }
            for row in rows
        ]

    def load_providers(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM providers ORDER BY provider_id").fetchall()
        return [
            {
                "provider_id": row["provider_id"],
                "display_name": row["display_name"],
                "protocol": row["protocol"],
                "base_url": row["base_url"],
                "auth_scheme": row["auth_scheme"],
                "auth_env": row["auth_env"],
                "headers_template": json_loads(row["headers_template_json"], {}),
                "model_lookup_mode": row["model_lookup_mode"],
                "enabled": bool(row["enabled"]),
            }
            for row in rows
        ]

    def load_models(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM models ORDER BY model_alias").fetchall()
        return [
            {
                "model_alias": row["model_alias"],
                "provider_id": row["provider_id"],
                "display_name": row["display_name"],
                "model_name": row["model_name"],
                "default_timeout": int(row["default_timeout"]),
                "default_max_tokens": int(row["default_max_tokens"]),
                "supports_multi_turn": bool(row["supports_multi_turn"]),
                "enabled": bool(row["enabled"]),
            }
            for row in rows
        ]

    def upsert_run(self, meta: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, connection_id, connection_name, provider_id, model_alias, model_name, base_url, started_at, finished_at,
                    bank_version, status, execution_status, run_kind, parent_run_id, retry_policy,
                    source_failed_question_ids_json, config_json, progress_json, totals_json,
                    summary_metrics_json, report_path, canonical_summary_path, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    connection_id=excluded.connection_id,
                    connection_name=excluded.connection_name,
                    provider_id=excluded.provider_id,
                    model_alias=excluded.model_alias,
                    model_name=excluded.model_name,
                    base_url=excluded.base_url,
                    started_at=excluded.started_at,
                    finished_at=excluded.finished_at,
                    bank_version=excluded.bank_version,
                    status=excluded.status,
                    execution_status=excluded.execution_status,
                    run_kind=excluded.run_kind,
                    parent_run_id=excluded.parent_run_id,
                    retry_policy=excluded.retry_policy,
                    source_failed_question_ids_json=excluded.source_failed_question_ids_json,
                    config_json=excluded.config_json,
                    progress_json=excluded.progress_json,
                    totals_json=excluded.totals_json,
                    summary_metrics_json=excluded.summary_metrics_json,
                    report_path=excluded.report_path,
                    canonical_summary_path=excluded.canonical_summary_path,
                    error=excluded.error
                """,
                (
                    meta["run_id"],
                    meta.get("connection_id"),
                    meta.get("connection_name"),
                    meta.get("provider_id"),
                    meta.get("model_alias"),
                    meta.get("model_name"),
                    meta.get("base_url"),
                    meta.get("started_at"),
                    meta.get("finished_at"),
                    meta.get("bank_version"),
                    meta.get("status"),
                    meta.get("execution_status"),
                    meta.get("run_kind"),
                    meta.get("parent_run_id"),
                    meta.get("retry_policy"),
                    json_dumps(meta.get("source_failed_question_ids", [])),
                    json_dumps(meta.get("config", {})),
                    json_dumps(meta.get("progress", {})),
                    json_dumps(meta.get("totals", {})),
                    json_dumps(meta.get("summary_metrics", {})),
                    meta.get("report_path"),
                    meta.get("canonical_summary_path"),
                    meta.get("error"),
                ),
            )

    def delete_run(self, run_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))

    def replace_bank_items(self, rows: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM bank_items")
            for row in rows:
                self._insert_bank_item(conn, row)

    def get_bank_item(self, question_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM bank_items WHERE question_id = ?", (question_id,)).fetchone()
        if not row:
            return None
        return json_loads(row["full_item_json"], {})

    def list_bank_items(
        self,
        *,
        version: str | None = None,
        module: str | None = None,
        subtype: str | None = None,
        item_format: str | None = None,
        qa_status: str | None = None,
        include_archived: bool = True,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        params: list[Any] = []
        if version:
            clauses.append("version = ?")
            params.append(version)
        if module:
            clauses.append("module = ?")
            params.append(module)
        if subtype:
            clauses.append("subtype = ?")
            params.append(subtype)
        if item_format:
            clauses.append("item_format = ?")
            params.append(item_format)
        if qa_status:
            clauses.append("qa_status = ?")
            params.append(qa_status)
        elif not include_archived:
            clauses.append("qa_status != 'retired'")
        if keyword:
            clauses.append("search_text LIKE ?")
            params.append(f"%{keyword.lower()}%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            total_row = conn.execute(f"SELECT COUNT(*) AS n FROM bank_items {where}", params).fetchone()
            rows = conn.execute(
                f"""
                SELECT full_item_json FROM bank_items
                {where}
                ORDER BY question_id
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        return {
            "items": [json_loads(row["full_item_json"], {}) for row in rows],
            "total": int(total_row["n"]),
            "offset": offset,
            "limit": limit,
        }

    def create_bank_item(self, row: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT question_id FROM bank_items WHERE question_id = ?",
                (row["question_id"],),
            ).fetchone()
            if existing:
                raise ValueError(f"question_id already exists: {row['question_id']}")
            self._insert_bank_item(conn, row)
        return row

    def update_bank_item(self, question_id: str, row: dict[str, Any]) -> dict[str, Any]:
        row["question_id"] = question_id
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT question_id FROM bank_items WHERE question_id = ?",
                (question_id,),
            ).fetchone()
            if not existing:
                raise KeyError(question_id)
            self._insert_bank_item(conn, row)
        return row

    def delete_bank_item(self, question_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM bank_items WHERE question_id = ?",
                (question_id,),
            )
        return cursor.rowcount > 0

    def archive_bank_item(self, question_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT full_item_json FROM bank_items WHERE question_id = ?",
                (question_id,),
            ).fetchone()
            if not row:
                return None
            item = json_loads(row["full_item_json"], {})
            item["qa_status"] = "retired"
            self._insert_bank_item(conn, item)
        return item

    def restore_bank_item(
        self, question_id: str, qa_status: str = "ready"
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT full_item_json FROM bank_items WHERE question_id = ?",
                (question_id,),
            ).fetchone()
            if not row:
                return None
            item = json_loads(row["full_item_json"], {})
            item["qa_status"] = qa_status
            self._insert_bank_item(conn, item)
        return item

    def get_all_bank_items(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT full_item_json FROM bank_items ORDER BY question_id"
            ).fetchall()
        return [json_loads(row["full_item_json"], {}) for row in rows]

    def get_bank_facets(self) -> dict[str, Any]:
        with self._connect() as conn:
            total_row = conn.execute("SELECT COUNT(*) AS n FROM bank_items").fetchone()
            versions = conn.execute(
                "SELECT version AS value, COUNT(*) AS count FROM bank_items GROUP BY version ORDER BY version"
            ).fetchall()
            modules = conn.execute(
                "SELECT module AS value, COUNT(*) AS count FROM bank_items GROUP BY module ORDER BY module"
            ).fetchall()
            item_formats = conn.execute(
                "SELECT item_format AS value, COUNT(*) AS count FROM bank_items GROUP BY item_format ORDER BY item_format"
            ).fetchall()
            qa_statuses = conn.execute(
                "SELECT qa_status AS value, COUNT(*) AS count FROM bank_items GROUP BY qa_status ORDER BY qa_status"
            ).fetchall()
            subtypes = conn.execute(
                """
                SELECT subtype AS value, module, COUNT(*) AS count
                FROM bank_items
                WHERE subtype IS NOT NULL AND subtype != ''
                GROUP BY subtype, module
                ORDER BY module, subtype
                """
            ).fetchall()
        subtype_meta: dict[str, dict[str, Any]] = {}
        for row in subtypes:
            entry = subtype_meta.setdefault(row["value"], {"value": row["value"], "count": 0, "modules": []})
            entry["count"] += int(row["count"])
            entry["modules"].append(row["module"])
        return {
            "total": int(total_row["n"]),
            "versions": [{"value": row["value"], "count": int(row["count"])} for row in versions],
            "modules": [{"value": row["value"], "count": int(row["count"])} for row in modules],
            "qa_statuses": [
                {"value": row["value"], "count": int(row["count"])} for row in qa_statuses
            ],
            "subtypes": sorted(
                [
                    {"value": meta["value"], "count": meta["count"], "modules": sorted(meta["modules"])}
                    for meta in subtype_meta.values()
                ],
                key=lambda item: (item["modules"][0] if item["modules"] else "", item["value"]),
            ),
            "item_formats": [{"value": row["value"], "count": int(row["count"])} for row in item_formats],
        }

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if not row:
            return None
        return self._decode_run_row(row)

    def list_runs(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY COALESCE(started_at, created_at) DESC, run_id DESC"
            ).fetchall()
        return [self._decode_run_row(row) for row in rows]

    def has_run(self, run_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM runs WHERE run_id = ? LIMIT 1", (run_id,)).fetchone()
        return row is not None

    def replace_run_items(self, run_id: str, rows: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM run_items WHERE run_id = ?", (run_id,))
            for row in rows:
                self._insert_run_item(conn, row)

    def upsert_run_item(self, row: dict[str, Any]) -> None:
        with self._connect() as conn:
            self._insert_run_item(conn, row)

    def list_run_items(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM run_items
                WHERE run_id = ?
                ORDER BY COALESCE(finished_at, started_at, created_at), id
                """,
                (run_id,),
            ).fetchall()
        return [self._decode_item_row(row) for row in rows]

    def import_all_runs(self, *, force: bool = False) -> None:
        if not self.runs_dir.exists():
            return
        for meta_path in sorted(self.runs_dir.glob("*/evaluation_run.json")):
            self.import_run_dir(meta_path.parent, force=force)

    def import_run_dir(self, run_dir: Path | str, *, force: bool = False) -> None:
        run_dir = Path(run_dir)
        meta_path = run_dir / "evaluation_run.json"
        if not meta_path.exists():
            return
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if not force and self.has_run(meta["run_id"]):
            return
        self.upsert_run(meta)
        items_path = run_dir / "item_scores.jsonl"
        if items_path.exists():
            self.replace_run_items(meta["run_id"], load_jsonl(items_path))

    def _insert_run_item(self, conn: sqlite3.Connection, row: dict[str, Any]) -> None:
        conn.execute(
            """
            INSERT INTO run_items (
                run_id, question_id, module, item_format, score_method, primary_score, aux_score,
                status, response_json, score_details_json, error, failure_type, started_at, finished_at,
                latency_ms, provider_id, model_alias, attempt_run_id, source_run_id, is_retry_attempt, canonical_selected
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, question_id, attempt_run_id) DO UPDATE SET
                module=excluded.module,
                item_format=excluded.item_format,
                score_method=excluded.score_method,
                primary_score=excluded.primary_score,
                aux_score=excluded.aux_score,
                status=excluded.status,
                response_json=excluded.response_json,
                score_details_json=excluded.score_details_json,
                error=excluded.error,
                failure_type=excluded.failure_type,
                started_at=excluded.started_at,
                finished_at=excluded.finished_at,
                latency_ms=excluded.latency_ms,
                provider_id=excluded.provider_id,
                model_alias=excluded.model_alias,
                source_run_id=excluded.source_run_id,
                is_retry_attempt=excluded.is_retry_attempt,
                canonical_selected=excluded.canonical_selected
            """,
            (
                row["run_id"],
                row["question_id"],
                row["module"],
                row["item_format"],
                row["score_method"],
                row.get("primary_score"),
                row.get("aux_score"),
                row["status"],
                json_dumps(row.get("response")),
                json_dumps(row.get("score_details", {})),
                row.get("error"),
                row.get("failure_type"),
                row.get("started_at"),
                row.get("finished_at"),
                row.get("latency_ms"),
                row.get("provider_id"),
                row.get("model_alias"),
                row.get("attempt_run_id") or row["run_id"],
                row.get("source_run_id") or row["run_id"],
                1 if row.get("is_retry_attempt") else 0,
                1 if row.get("canonical_selected") else 0,
            ),
        )

    def _insert_bank_item(self, conn: sqlite3.Connection, row: dict[str, Any]) -> None:
        search_text = json.dumps(
            {
                "question_id": row.get("question_id"),
                "module": row.get("module"),
                "subtype": row.get("subtype"),
                "prompt_template": row.get("prompt_template"),
                "turn_script": row.get("turn_script"),
                "ground_truth": row.get("ground_truth"),
            },
            ensure_ascii=False,
        ).lower()
        conn.execute(
            """
            INSERT INTO bank_items (
                question_id, version, module, subtype, item_format, prompt_template,
                turn_script_json, ground_truth_json, scoring_method, scoring_params_json,
                rotation_policy_json, provenance_json, qa_status, search_text, full_item_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(question_id) DO UPDATE SET
                version=excluded.version,
                module=excluded.module,
                subtype=excluded.subtype,
                item_format=excluded.item_format,
                prompt_template=excluded.prompt_template,
                turn_script_json=excluded.turn_script_json,
                ground_truth_json=excluded.ground_truth_json,
                scoring_method=excluded.scoring_method,
                scoring_params_json=excluded.scoring_params_json,
                rotation_policy_json=excluded.rotation_policy_json,
                provenance_json=excluded.provenance_json,
                qa_status=excluded.qa_status,
                search_text=excluded.search_text,
                full_item_json=excluded.full_item_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                row["question_id"],
                row.get("version"),
                row["module"],
                row.get("subtype"),
                row["item_format"],
                row.get("prompt_template"),
                json_dumps(row.get("turn_script")),
                json_dumps(row.get("ground_truth")),
                row["scoring_method"],
                json_dumps(row.get("scoring_params", {})),
                json_dumps(row.get("rotation_policy", {})),
                json_dumps(row.get("provenance", {})),
                row.get("qa_status") or "ready",
                search_text,
                json_dumps(row),
            ),
        )

    def _decode_run_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "run_id": row["run_id"],
            "connection_id": row["connection_id"],
            "connection_name": row["connection_name"],
            "provider_id": row["provider_id"],
            "model_alias": row["model_alias"],
            "model_name": row["model_name"],
            "base_url": row["base_url"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "bank_version": row["bank_version"],
            "status": row["status"],
            "execution_status": row["execution_status"],
            "run_kind": row["run_kind"],
            "parent_run_id": row["parent_run_id"],
            "retry_policy": row["retry_policy"],
            "source_failed_question_ids": json_loads(row["source_failed_question_ids_json"], []),
            "config": json_loads(row["config_json"], {}),
            "progress": json_loads(row["progress_json"], {}),
            "totals": json_loads(row["totals_json"], {}),
            "summary_metrics": json_loads(row["summary_metrics_json"], {}),
            "report_path": row["report_path"],
            "canonical_summary_path": row["canonical_summary_path"],
            "error": row["error"],
        }

    def _decode_item_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "run_id": row["run_id"],
            "attempt_run_id": row["attempt_run_id"],
            "source_run_id": row["source_run_id"],
            "provider_id": row["provider_id"],
            "model_alias": row["model_alias"],
            "question_id": row["question_id"],
            "module": row["module"],
            "item_format": row["item_format"],
            "score_method": row["score_method"],
            "primary_score": row["primary_score"],
            "aux_score": row["aux_score"],
            "status": row["status"],
            "response": json_loads(row["response_json"], None),
            "score_details": json_loads(row["score_details_json"], {}),
            "error": row["error"],
            "failure_type": row["failure_type"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "latency_ms": row["latency_ms"],
            "is_retry_attempt": bool(row["is_retry_attempt"]),
            "canonical_selected": bool(row["canonical_selected"]),
        }

    # ------------------------------------------------------------------
    # Module / Subtype / QuotaTag dictionary CRUD (Phase 3)
    # ------------------------------------------------------------------
    _DICT_KINDS = {
        "module": ("module_dict", ("code", "display_name", "description", "sort_order", "parent_group", "color_token", "is_active"), "code"),
        "subtype": ("subtype_dict", ("code", "module_code", "display_name", "description", "sort_order", "is_active"), "code"),
        "quota_tag": ("quota_tag_dict", ("code", "module_code", "display_name", "description", "sort_order", "is_active"), "code"),
    }

    def _dict_kind(self, kind: str) -> tuple[str, tuple[str, ...], str]:
        normalized = (kind or "").strip().lower()
        if normalized not in self._DICT_KINDS:
            raise ValueError(f"unknown dict kind: {kind}")
        table, columns, pk = self._DICT_KINDS[normalized]
        return table, columns, pk

    def list_dict(self, kind: str, include_inactive: bool = True) -> list[dict[str, Any]]:
        table, _, _ = self._dict_kind(kind)
        where = "" if include_inactive else " WHERE is_active = 1"
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM {table}{where} ORDER BY sort_order, code"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_dict(self, kind: str, code: str) -> dict[str, Any] | None:
        table, _, _ = self._dict_kind(kind)
        with self._connect() as conn:
            row = conn.execute(f"SELECT * FROM {table} WHERE code = ?", (code,)).fetchone()
        return dict(row) if row else None

    def upsert_dict(self, kind: str, row: dict[str, Any]) -> dict[str, Any]:
        table, columns, pk = self._dict_kind(kind)
        clean: dict[str, Any] = {}
        for col in columns:
            if col == "is_active":
                value = row.get(col, 1)
                clean[col] = 1 if value in (1, True, "1", "true", "True", 1.0) else 0
            elif col in ("sort_order",):
                value = row.get(col, 0)
                clean[col] = int(value) if value not in (None, "") else 0
            else:
                value = row.get(col, "")
                clean[col] = "" if value is None else str(value).strip()
        if not clean.get(pk):
            raise ValueError(f"{kind} {pk} is required")
        with self._connect() as conn:
            placeholders = ", ".join(["?"] * len(columns))
            update_cols = ", ".join([f"{col}=excluded.{col}" for col in columns if col != pk])
            conn.execute(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
                f"ON CONFLICT({pk}) DO UPDATE SET {update_cols}, updated_at=CURRENT_TIMESTAMP",
                tuple(clean[col] for col in columns),
            )
        result = self.get_dict(kind, clean[pk])
        return result or clean

    def delete_dict(self, kind: str, code: str, hard: bool = False) -> bool:
        table, _, _ = self._dict_kind(kind)
        with self._connect() as conn:
            if hard:
                cursor = conn.execute(f"DELETE FROM {table} WHERE code = ?", (code,))
            else:
                cursor = conn.execute(
                    f"UPDATE {table} SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE code = ?",
                    (code,),
                )
        return cursor.rowcount > 0

    def bulk_upsert_dict(self, kind: str, rows: list[dict[str, Any]]) -> int:
        count = 0
        for row in rows:
            self.upsert_dict(kind, row)
            count += 1
        return count

    def get_module_display_names(self) -> dict[str, str]:
        return {row["code"]: row["display_name"] for row in self.list_dict("module", include_inactive=True)}
