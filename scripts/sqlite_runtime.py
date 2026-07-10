#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = Path(os.environ.get("QUESTION_BANK_SQLITE_PATH", ROOT / "manifests" / "evaluation.sqlite"))
DEFAULT_LEGACY_CONFIG_PATH = ROOT / "config" / "providers.json"
DEFAULT_RUNS_DIR = ROOT / "manifests" / "evaluation_runs"
DEFAULT_BANK_ITEMS_PATH = ROOT / "final_bank_specs" / "generated" / "final_bank_items.jsonl"
CURRENT_BANK_VERSION = "QB-v1.3"
EDITABLE_BANK_VERSIONS = {"QB-v1.3", "QB-v1.3-pilot"}
SNAPSHOT_FILENAMES = (
    "final_bank_items_qbv1_0.jsonl",
    "final_bank_items_qbv1_1.jsonl",
    "final_bank_items_qbv1_2.jsonl",
    "final_bank_items_qbv1_3.jsonl",
    "final_bank_items_qbv1_3_pilot.jsonl",
)


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

    @contextmanager
    def _connect(self):
        def _open() -> sqlite3.Connection:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        conn = _open()
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
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
        try:
            with conn:
                yield conn
        finally:
            conn.close()

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
                    question_id TEXT NOT NULL,
                    version TEXT NOT NULL,
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
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (version, question_id)
                );

                CREATE TABLE IF NOT EXISTS bank_versions (
                    version TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    item_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    is_runnable INTEGER NOT NULL DEFAULT 1,
                    is_editable INTEGER NOT NULL DEFAULT 0,
                    source_files_json TEXT NOT NULL DEFAULT '[]',
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
                    bank_version TEXT,
                    bank_item_snapshot_json TEXT,
                    bank_item_content_hash TEXT,
                    snapshot_origin TEXT,
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

                CREATE TABLE IF NOT EXISTS judge_assessments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    attempt_run_id TEXT NOT NULL,
                    judge_connection_id TEXT,
                    judge_model_alias TEXT,
                    status TEXT NOT NULL,
                    score REAL,
                    verdict TEXT,
                    criteria_json TEXT NOT NULL DEFAULT '[]',
                    rationale TEXT,
                    confidence REAL,
                    raw_response_json TEXT,
                    error TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_judge_assessments_item
                    ON judge_assessments(run_id, question_id, attempt_run_id, id);

                CREATE TABLE IF NOT EXISTS manual_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    attempt_run_id TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    score REAL NOT NULL,
                    verdict TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    confirmed INTEGER NOT NULL DEFAULT 1,
                    needs_review INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_manual_reviews_item
                    ON manual_reviews(run_id, question_id, attempt_run_id, id);

                CREATE TABLE IF NOT EXISTS review_threads (
                    thread_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    attempt_run_id TEXT NOT NULL,
                    connection_id TEXT,
                    title TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_review_threads_item
                    ON review_threads(run_id, question_id, attempt_run_id);

                CREATE TABLE IF NOT EXISTS review_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    raw_response_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (thread_id) REFERENCES review_threads(thread_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_review_messages_thread ON review_messages(thread_id, id);

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

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
            self._migrate_bank_items_composite_identity(conn)
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
            self._ensure_column(conn, "run_items", "bank_version", "TEXT")
            self._ensure_column(conn, "run_items", "bank_item_snapshot_json", "TEXT")
            self._ensure_column(conn, "run_items", "bank_item_content_hash", "TEXT")
            self._ensure_column(conn, "run_items", "snapshot_origin", "TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_items_module ON bank_items(module)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_items_subtype ON bank_items(subtype)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_items_item_format ON bank_items(item_format)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_items_version ON bank_items(version)")
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

    def _migrate_bank_items_composite_identity(self, conn: sqlite3.Connection) -> None:
        columns = conn.execute("PRAGMA table_info(bank_items)").fetchall()
        primary_key = [row["name"] for row in sorted(columns, key=lambda row: row["pk"]) if row["pk"]]
        if primary_key == ["version", "question_id"]:
            return
        legacy_items = [json_loads(row["full_item_json"], {}) for row in conn.execute(
            "SELECT full_item_json FROM bank_items"
        ).fetchall()]
        conn.execute("ALTER TABLE bank_items RENAME TO bank_items_legacy_identity")
        conn.execute(
            """
            CREATE TABLE bank_items (
                question_id TEXT NOT NULL,
                version TEXT NOT NULL,
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
                qa_status TEXT NOT NULL DEFAULT 'ready',
                difficulty TEXT,
                drift_role TEXT,
                module_quota_tag TEXT,
                notes TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (version, question_id)
            )
            """
        )
        for item in legacy_items:
            if item:
                item["version"] = item.get("version") or CURRENT_BANK_VERSION
                self._insert_bank_item(conn, item)
        conn.execute("DROP TABLE bank_items_legacy_identity")

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
        generated_dir = self.bank_items_path.parent
        sources = [generated_dir / name for name in SNAPSHOT_FILENAMES]
        sources.append(self.bank_items_path)
        combined: dict[tuple[str, str], dict[str, Any]] = {}
        source_files: dict[str, list[str]] = {}
        for path in sources:
            if not path.exists():
                continue
            for row in load_jsonl(path):
                version = str(row.get("version") or CURRENT_BANK_VERSION)
                row["version"] = version
                combined[(version, row["question_id"])] = row
                source_files.setdefault(version, []).append(path.name)
        on_disk = list(combined.values())
        existing = {
            (row.get("version") or CURRENT_BANK_VERSION, row["question_id"]): row
            for row in self.get_all_bank_items()
        }
        if existing != combined:
            self.replace_bank_items(on_disk)
        self._refresh_bank_versions(source_files)

    def _refresh_bank_versions(self, source_files: dict[str, list[str]]) -> None:
        with self._connect() as conn:
            counts = conn.execute(
                "SELECT version, COUNT(*) AS item_count FROM bank_items GROUP BY version"
            ).fetchall()
            present = {row["version"] for row in counts}
            conn.execute("DELETE FROM bank_versions")
            for row in counts:
                version = row["version"]
                if version == CURRENT_BANK_VERSION:
                    status = "current"
                elif version.endswith("-pilot"):
                    status = "pilot"
                else:
                    status = "legacy"
                conn.execute(
                    """
                    INSERT INTO bank_versions (
                        version, display_name, item_count, status, is_runnable, is_editable,
                        source_files_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        version,
                        version,
                        int(row["item_count"]),
                        status,
                        1,
                        1 if version in EDITABLE_BANK_VERSIONS else 0,
                        json_dumps(sorted(set(source_files.get(version, [])))),
                    ),
                )
            # Keep metadata deterministic even when a configured snapshot is empty.
            for version in ("QB-v1.0", "QB-v1.1", "QB-v1.2", CURRENT_BANK_VERSION):
                if version not in present:
                    conn.execute(
                        "INSERT INTO bank_versions (version, display_name, item_count, status, is_runnable, is_editable) VALUES (?, ?, 0, ?, 1, ?)",
                        (version, version, "current" if version == CURRENT_BANK_VERSION else "legacy", 1 if version in EDITABLE_BANK_VERSIONS else 0),
                    )

    def list_bank_versions(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM bank_versions ORDER BY version"
            ).fetchall()
        return [
            {
                "version": row["version"],
                "display_name": row["display_name"],
                "item_count": int(row["item_count"]),
                "status": row["status"],
                "is_runnable": bool(row["is_runnable"]),
                "is_editable": bool(row["is_editable"]),
                "source_files": json_loads(row["source_files_json"], []),
            }
            for row in rows
        ]

    def _assert_version_editable(self, version: str) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT is_editable FROM bank_versions WHERE version = ?", (version,)
            ).fetchone()
        editable = version in EDITABLE_BANK_VERSIONS if row is None else bool(row["is_editable"])
        if not editable:
            raise ValueError(f"bank version is read-only: {version}")

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

    def get_bank_item(self, question_id: str, version: str | None = None) -> dict[str, Any] | None:
        version = version or CURRENT_BANK_VERSION
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM bank_items WHERE version = ? AND question_id = ?",
                (version, question_id),
            ).fetchone()
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
        version = str(row.get("version") or CURRENT_BANK_VERSION)
        row["version"] = version
        self._assert_version_editable(version)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT question_id FROM bank_items WHERE version = ? AND question_id = ?",
                (version, row["question_id"]),
            ).fetchone()
            if existing:
                raise ValueError(f"question_id already exists: {row['question_id']}")
            self._insert_bank_item(conn, row)
        return row

    def update_bank_item(self, question_id: str, row: dict[str, Any], version: str | None = None) -> dict[str, Any]:
        version = version or str(row.get("version") or CURRENT_BANK_VERSION)
        self._assert_version_editable(version)
        row["question_id"] = question_id
        row["version"] = version
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT question_id FROM bank_items WHERE version = ? AND question_id = ?",
                (version, question_id),
            ).fetchone()
            if not existing:
                raise KeyError(question_id)
            self._insert_bank_item(conn, row)
        return row

    def delete_bank_item(self, question_id: str, version: str | None = None) -> bool:
        version = version or CURRENT_BANK_VERSION
        self._assert_version_editable(version)
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM bank_items WHERE version = ? AND question_id = ?",
                (version, question_id),
            )
        return cursor.rowcount > 0

    def archive_bank_item(self, question_id: str, version: str | None = None) -> dict[str, Any] | None:
        version = version or CURRENT_BANK_VERSION
        self._assert_version_editable(version)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT full_item_json FROM bank_items WHERE version = ? AND question_id = ?",
                (version, question_id),
            ).fetchone()
            if not row:
                return None
            item = json_loads(row["full_item_json"], {})
            item["qa_status"] = "retired"
            self._insert_bank_item(conn, item)
        return item

    def restore_bank_item(
        self, question_id: str, qa_status: str = "ready", version: str | None = None
    ) -> dict[str, Any] | None:
        version = version or CURRENT_BANK_VERSION
        self._assert_version_editable(version)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT full_item_json FROM bank_items WHERE version = ? AND question_id = ?",
                (version, question_id),
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
                "SELECT full_item_json FROM bank_items ORDER BY version, question_id"
            ).fetchall()
        return [json_loads(row["full_item_json"], {}) for row in rows]

    def get_bank_facets(
        self,
        *,
        version: str | None = None,
        module: str | None = None,
    ) -> dict[str, Any]:
        version_clauses: list[str] = []
        version_params: list[Any] = []
        if version:
            version_clauses.append("version = ?")
            version_params.append(version)
        scoped_clauses = list(version_clauses)
        scoped_params = list(version_params)
        if module:
            scoped_clauses.append("module = ?")
            scoped_params.append(module)
        version_where = f"WHERE {' AND '.join(version_clauses)}" if version_clauses else ""
        scoped_where = f"WHERE {' AND '.join(scoped_clauses)}" if scoped_clauses else ""
        subtype_clauses = [*scoped_clauses, "subtype IS NOT NULL", "subtype != ''"]
        subtype_where = f"WHERE {' AND '.join(subtype_clauses)}"
        with self._connect() as conn:
            total_row = conn.execute(
                f"SELECT COUNT(*) AS n FROM bank_items {scoped_where}", scoped_params
            ).fetchone()
            versions = conn.execute(
                "SELECT version AS value, COUNT(*) AS count FROM bank_items GROUP BY version ORDER BY version"
            ).fetchall()
            modules = conn.execute(
                f"SELECT module AS value, COUNT(*) AS count FROM bank_items {version_where} GROUP BY module ORDER BY module",
                version_params,
            ).fetchall()
            item_formats = conn.execute(
                f"SELECT item_format AS value, COUNT(*) AS count FROM bank_items {scoped_where} GROUP BY item_format ORDER BY item_format",
                scoped_params,
            ).fetchall()
            qa_statuses = conn.execute(
                f"SELECT qa_status AS value, COUNT(*) AS count FROM bank_items {scoped_where} GROUP BY qa_status ORDER BY qa_status",
                scoped_params,
            ).fetchall()
            subtypes = conn.execute(
                f"""
                SELECT subtype AS value, module, COUNT(*) AS count
                FROM bank_items
                {subtype_where}
                GROUP BY subtype, module
                ORDER BY module, subtype
                """,
                scoped_params,
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
                latency_ms, provider_id, model_alias, attempt_run_id, source_run_id, is_retry_attempt, canonical_selected,
                bank_version, bank_item_snapshot_json, bank_item_content_hash, snapshot_origin
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                canonical_selected=excluded.canonical_selected,
                bank_version=excluded.bank_version,
                bank_item_snapshot_json=excluded.bank_item_snapshot_json,
                bank_item_content_hash=excluded.bank_item_content_hash,
                snapshot_origin=excluded.snapshot_origin
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
                row.get("bank_version"),
                json_dumps(row.get("bank_item_snapshot")) if row.get("bank_item_snapshot") is not None else None,
                row.get("bank_item_content_hash"),
                row.get("snapshot_origin"),
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
            ON CONFLICT(version, question_id) DO UPDATE SET
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
            "bank_version": row["bank_version"],
            "bank_item_snapshot": json_loads(row["bank_item_snapshot_json"], None),
            "bank_item_content_hash": row["bank_item_content_hash"],
            "snapshot_origin": row["snapshot_origin"],
        }

    # ------------------------------------------------------------------
    # Judge / manual review / follow-up conversation persistence
    # ------------------------------------------------------------------
    def add_judge_assessment(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO judge_assessments (
                    run_id, question_id, attempt_run_id, judge_connection_id, judge_model_alias,
                    status, score, verdict, criteria_json, rationale, confidence,
                    raw_response_json, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["run_id"], payload["question_id"], payload.get("attempt_run_id") or payload["run_id"],
                    payload.get("judge_connection_id"), payload.get("judge_model_alias"), payload.get("status", "ok"),
                    payload.get("score"), payload.get("verdict"), json_dumps(payload.get("criteria", [])),
                    payload.get("rationale"), payload.get("confidence"),
                    json_dumps(payload.get("raw_response")) if payload.get("raw_response") is not None else None,
                    payload.get("error"),
                ),
            )
            assessment_id = cursor.lastrowid
        return self.get_judge_assessment(int(assessment_id))

    def get_judge_assessment(self, assessment_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM judge_assessments WHERE id = ?", (assessment_id,)).fetchone()
        if row is None:
            raise KeyError(assessment_id)
        return self._decode_judge_row(row)

    def list_judge_assessments(self, run_id: str, question_id: str, attempt_run_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM judge_assessments WHERE run_id = ? AND question_id = ?"
        params: list[Any] = [run_id, question_id]
        if attempt_run_id:
            sql += " AND attempt_run_id = ?"
            params.append(attempt_run_id)
        sql += " ORDER BY id"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._decode_judge_row(row) for row in rows]

    @staticmethod
    def _decode_judge_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "run_id": row["run_id"], "question_id": row["question_id"],
            "attempt_run_id": row["attempt_run_id"], "judge_connection_id": row["judge_connection_id"],
            "judge_model_alias": row["judge_model_alias"], "status": row["status"], "score": row["score"],
            "verdict": row["verdict"], "criteria": json_loads(row["criteria_json"], []),
            "rationale": row["rationale"], "confidence": row["confidence"],
            "raw_response": json_loads(row["raw_response_json"], None), "error": row["error"],
            "created_at": row["created_at"],
        }

    def add_manual_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO manual_reviews (
                    run_id, question_id, attempt_run_id, reviewer, score, verdict, note, confirmed, needs_review
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["run_id"], payload["question_id"], payload.get("attempt_run_id") or payload["run_id"],
                    payload["reviewer"], payload["score"], payload["verdict"], payload.get("note", ""),
                    1 if payload.get("confirmed", True) else 0, 1 if payload.get("needs_review", False) else 0,
                ),
            )
            review_id = cursor.lastrowid
            row = conn.execute("SELECT * FROM manual_reviews WHERE id = ?", (review_id,)).fetchone()
        return self._decode_manual_row(row)

    def list_manual_reviews(self, run_id: str, question_id: str, attempt_run_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM manual_reviews WHERE run_id = ? AND question_id = ?"
        params: list[Any] = [run_id, question_id]
        if attempt_run_id:
            sql += " AND attempt_run_id = ?"
            params.append(attempt_run_id)
        sql += " ORDER BY id"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._decode_manual_row(row) for row in rows]

    @staticmethod
    def _decode_manual_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "run_id": row["run_id"], "question_id": row["question_id"],
            "attempt_run_id": row["attempt_run_id"], "reviewer": row["reviewer"], "score": row["score"],
            "verdict": row["verdict"], "note": row["note"], "confirmed": bool(row["confirmed"]),
            "needs_review": bool(row["needs_review"]), "created_at": row["created_at"],
        }

    def create_review_thread(self, payload: dict[str, Any]) -> dict[str, Any]:
        thread_id = payload.get("thread_id") or f"review-{uuid.uuid4().hex[:12]}"
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO review_threads (thread_id, run_id, question_id, attempt_run_id, connection_id, title) VALUES (?, ?, ?, ?, ?, ?)",
                (thread_id, payload["run_id"], payload["question_id"], payload.get("attempt_run_id") or payload["run_id"], payload.get("connection_id"), payload.get("title") or payload["question_id"]),
            )
        return self.get_review_thread(thread_id)

    def add_review_message(self, thread_id: str, role: str, content: str, raw_response: Any = None) -> dict[str, Any]:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO review_messages (thread_id, role, content, raw_response_json) VALUES (?, ?, ?, ?)",
                (thread_id, role, content, json_dumps(raw_response) if raw_response is not None else None),
            )
            conn.execute("UPDATE review_threads SET updated_at = CURRENT_TIMESTAMP WHERE thread_id = ?", (thread_id,))
            row = conn.execute("SELECT * FROM review_messages WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._decode_message_row(row)

    def get_review_thread(self, thread_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            thread = conn.execute("SELECT * FROM review_threads WHERE thread_id = ?", (thread_id,)).fetchone()
            messages = conn.execute("SELECT * FROM review_messages WHERE thread_id = ? ORDER BY id", (thread_id,)).fetchall()
        if thread is None:
            raise KeyError(thread_id)
        return {**dict(thread), "messages": [self._decode_message_row(row) for row in messages]}

    def list_review_threads(self, run_id: str | None = None) -> list[dict[str, Any]]:
        sql, params = "SELECT * FROM review_threads", []
        if run_id:
            sql, params = sql + " WHERE run_id = ?", [run_id]
        sql += " ORDER BY updated_at DESC"
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    @staticmethod
    def _decode_message_row(row: sqlite3.Row) -> dict[str, Any]:
        return {"id": row["id"], "thread_id": row["thread_id"], "role": row["role"], "content": row["content"], "raw_response": json_loads(row["raw_response_json"], None), "created_at": row["created_at"]}

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._connect() as conn:
            row = conn.execute("SELECT value_json FROM app_settings WHERE key = ?", (key,)).fetchone()
        return json_loads(row["value_json"], default) if row else default

    def set_setting(self, key: str, value: Any) -> Any:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO app_settings (key, value_json) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=CURRENT_TIMESTAMP",
                (key, json_dumps(value)),
            )
        return value

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
