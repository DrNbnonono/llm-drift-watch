#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from evaluation_engine import EvaluationRunService
from provider_runtime import ProviderError, is_master_key_configured, set_master_key


service = EvaluationRunService()
app = FastAPI(title="Question Bank Evaluation API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunCreateRequest(BaseModel):
    provider_id: str | None = None
    model_alias: str | None = None
    model_connection_id: str | None = None
    modules: list[str] | None = None
    module_filters: list[str] | None = None
    smoke: bool = False
    timeout: int | None = None
    max_items: int | None = None
    limit_per_module: int = 1
    concurrency_limit: int = Field(default=1, ge=1, le=4)
    question_ids: list[str] | None = None
    bank_version: str | None = None
    judge_connection_id: str | None = None


class RetryRequest(BaseModel):
    timeout: int | None = None
    concurrency_limit: int = Field(default=1, ge=1, le=4)


class BulkDeleteRunsRequest(BaseModel):
    run_ids: list[str] = Field(default_factory=list)


class JudgeRetryRequest(BaseModel):
    attempt_run_id: str | None = None
    judge_connection_id: str | None = None


class ManualReviewRequest(BaseModel):
    attempt_run_id: str | None = None
    reviewer: str
    score: float = Field(ge=0, le=1)
    verdict: str | None = None
    note: str = Field(min_length=1)
    confirmed: bool = True
    needs_review: bool = False


class ReviewThreadCreateRequest(BaseModel):
    attempt_run_id: str | None = None
    connection_id: str | None = None
    title: str | None = None


class ReviewMessageRequest(BaseModel):
    content: str
    connection_id: str | None = None


class ReviewSettingsRequest(BaseModel):
    default_judge_connection_id: str | None = None
    reviewer_name: str | None = None


class BankBulkActionRequest(BaseModel):
    question_ids: list[str] = Field(default_factory=list)
    action: str
    qa_status: str = "ready"
    version: str | None = None


class ProviderUpsertRequest(BaseModel):
    provider_id: str | None = None
    display_name: str
    protocol: str
    base_url: str
    auth_scheme: str
    auth_env: str = ""
    headers_template: dict[str, str] = Field(default_factory=dict)
    model_lookup_mode: str = "skip"
    enabled: bool = True


class ModelUpsertRequest(BaseModel):
    model_alias: str | None = None
    provider_id: str
    display_name: str
    model_name: str
    default_timeout: int = 45
    default_max_tokens: int = 512
    supports_multi_turn: bool = True
    enabled: bool = True


class PricingRequest(BaseModel):
    currency: str = "USD"
    input_per_million: float | None = Field(default=None, ge=0)
    cached_input_per_million: float | None = Field(default=None, ge=0)
    cache_creation_per_million: float | None = Field(default=None, ge=0)
    output_per_million: float | None = Field(default=None, ge=0)
    reasoning_per_million: float | None = Field(default=None, ge=0)


class ModelConnectionUpsertRequest(BaseModel):
    connection_id: str | None = None
    vendor_name: str
    note: str | None = None
    homepage_url: str | None = None
    display_name: str
    protocol: str
    base_url: str
    auth_scheme: str
    auth_env: str = ""
    api_key: str | None = None
    model_name: str
    default_timeout: int = 45
    default_max_tokens: int = 512
    supports_multi_turn: bool = True
    enabled: bool = True
    headers_template: dict[str, str] = Field(default_factory=dict)
    model_lookup_mode: str = "skip"
    advanced: dict[str, Any] = Field(default_factory=dict)
    pricing: PricingRequest | None = None
    keep_existing_secret: bool = True


class EvaluationBatchCreateRequest(BaseModel):
    model_connection_ids: list[str] = Field(min_length=2)
    modules: list[str] | None = None
    smoke: bool = False
    timeout: int | None = None
    max_items: int | None = None
    limit_per_module: int = 1
    concurrency_limit: int = Field(default=2, ge=1, le=4)
    max_active_models: int = Field(default=2, ge=1, le=8)
    question_ids: list[str] | None = None
    bank_version: str | None = None
    judge_connection_id: str | None = None


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/system/paths")
def system_paths() -> dict[str, Any]:
    return service.get_system_paths()


class MasterKeyUpdateRequest(BaseModel):
    key: str = Field(..., min_length=8, description="New QUESTION_BANK_SECRET_KEY")
    persist: bool = True


class MasterKeyRotateRequest(BaseModel):
    persist: bool = True


def _provider_error_to_http(exc: ProviderError) -> HTTPException:
    code = 503 if exc.failure_type in {"master_key_required", "master_key_invalid"} else 400
    return HTTPException(status_code=code, detail={
        "code": exc.failure_type,
        "message": str(exc),
    })


@app.post("/api/system/master-key/rotate")
def rotate_master_key(payload: MasterKeyRotateRequest = MasterKeyRotateRequest()) -> dict[str, Any]:
    import secrets
    new_key = secrets.token_urlsafe(32)
    try:
        status = set_master_key(new_key, persist=payload.persist)
    except ProviderError as exc:
        raise _provider_error_to_http(exc) from exc
    return {
        "configured": status["configured"],
        "persisted": status["persisted"],
        "path": status["path"],
        "key": new_key,
    }


@app.put("/api/system/master-key")
def update_master_key(payload: MasterKeyUpdateRequest) -> dict[str, Any]:
    try:
        status = set_master_key(payload.key, persist=payload.persist)
    except ProviderError as exc:
        raise _provider_error_to_http(exc) from exc
    service.registry.reload()
    return {
        "configured": status["configured"],
        "persisted": status["persisted"],
        "path": status["path"],
        "key": payload.key if status["persisted"] else None,
    }


@app.get("/api/providers")
def list_providers() -> dict[str, Any]:
    return {
        "providers": service.registry.list_providers(),
        "models": service.registry.list_models(),
        "model_connections": service.registry.list_model_connections(),
    }


@app.get("/api/model-connections")
def list_model_connections() -> dict[str, Any]:
    return {"connections": service.registry.list_model_connections()}


@app.post("/api/model-connections")
def create_model_connection(payload: ModelConnectionUpsertRequest) -> dict[str, Any]:
    try:
        data = payload.model_dump(exclude_none=True)
        pricing = data.pop("pricing", None)
        if pricing is not None:
            data.setdefault("advanced", {})["pricing"] = pricing
        return service.registry.create_model_connection(data)
    except ProviderError as exc:  # noqa: BLE001
        raise _provider_error_to_http(exc) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/model-connections/{connection_id}")
def update_model_connection(connection_id: str, payload: ModelConnectionUpsertRequest) -> dict[str, Any]:
    try:
        data = payload.model_dump(exclude_none=True)
        data.pop("connection_id", None)
        pricing = data.pop("pricing", None)
        if pricing is not None:
            data.setdefault("advanced", {})["pricing"] = pricing
        return service.registry.update_model_connection(connection_id, data)
    except ProviderError as exc:  # noqa: BLE001
        raise _provider_error_to_http(exc) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/model-connections/{connection_id}")
def delete_model_connection(connection_id: str) -> dict[str, Any]:
    try:
        service.registry.delete_model_connection(connection_id)
        return {"ok": True, "connection_id": connection_id}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/model-connections/{connection_id}/test")
def test_model_connection(connection_id: str) -> dict[str, Any]:
    try:
        return service.registry.test_model_connection(connection_id)
    except ProviderError as exc:  # noqa: BLE001
        raise _provider_error_to_http(exc) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/providers")
def create_provider(payload: ProviderUpsertRequest) -> dict[str, Any]:
    try:
        return service.registry.create_provider(payload.model_dump(exclude_none=True))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/providers/{provider_id}")
def update_provider(provider_id: str, payload: ProviderUpsertRequest) -> dict[str, Any]:
    try:
        data = payload.model_dump(exclude_none=True)
        data.pop("provider_id", None)
        return service.registry.update_provider(provider_id, data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/providers/{provider_id}")
def delete_provider(provider_id: str) -> dict[str, Any]:
    try:
        service.registry.delete_provider(provider_id)
        return {"ok": True, "provider_id": provider_id}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/providers/{provider_id}/models")
def list_provider_models(provider_id: str) -> dict[str, Any]:
    return {"models": service.registry.list_models(provider_id=provider_id)}


@app.post("/api/models")
def create_model(payload: ModelUpsertRequest) -> dict[str, Any]:
    try:
        return service.registry.create_model(payload.model_dump(exclude_none=True))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/models/{model_alias}")
def update_model(model_alias: str, payload: ModelUpsertRequest) -> dict[str, Any]:
    try:
        data = payload.model_dump(exclude_none=True)
        data.pop("model_alias", None)
        return service.registry.update_model(model_alias, data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/models/{model_alias}")
def delete_model(model_alias: str) -> dict[str, Any]:
    try:
        service.registry.delete_model(model_alias)
        return {"ok": True, "model_alias": model_alias}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/runs")
def create_run(payload: RunCreateRequest) -> dict[str, Any]:
    try:
        run = service.create_run(
            provider_id=payload.provider_id,
            model_alias=payload.model_alias,
            model_connection_id=payload.model_connection_id,
            modules=payload.modules or payload.module_filters,
            smoke=payload.smoke,
            timeout=payload.timeout,
            max_items=payload.max_items,
            limit_per_module=payload.limit_per_module,
            concurrency_limit=payload.concurrency_limit,
            question_ids=payload.question_ids,
            bank_version=payload.bank_version,
            judge_connection_id=payload.judge_connection_id,
        )
        return run
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/runs")
def list_runs() -> dict[str, Any]:
    return {"runs": service.list_runs()}


@app.get("/api/runs/{run_id}/progress-grid")
def run_progress_grid(run_id: str) -> dict[str, Any]:
    try:
        return service.get_run_progress_grid(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc


@app.post("/api/evaluation-batches")
def create_evaluation_batch(payload: EvaluationBatchCreateRequest) -> dict[str, Any]:
    try:
        return service.create_evaluation_batch(**payload.model_dump())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/evaluation-batches")
def list_evaluation_batches() -> dict[str, Any]:
    batches = service.list_evaluation_batches()
    return {"batches": batches, "total": len(batches)}


@app.get("/api/evaluation-batches/{batch_id}")
def get_evaluation_batch(batch_id: str) -> dict[str, Any]:
    try:
        return service.get_evaluation_batch(batch_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="batch not found") from exc


@app.get("/api/evaluation-batches/{batch_id}/progress-grid")
def batch_progress_grid(batch_id: str) -> dict[str, Any]:
    try:
        return service.get_batch_progress_grid(batch_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="batch not found") from exc


@app.post("/api/evaluation-batches/{batch_id}/report")
def create_batch_report(batch_id: str) -> dict[str, Any]:
    try:
        return service.generate_batch_report(batch_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="batch not found") from exc


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    try:
        return service.get_run(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: str) -> dict[str, Any]:
    try:
        return service.delete_run(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/runs/bulk-delete")
def bulk_delete_runs(payload: BulkDeleteRunsRequest) -> dict[str, Any]:
    try:
        return service.delete_runs(payload.run_ids)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/items")
def get_run_items(
    run_id: str,
    module: str | None = Query(default=None),
    status: str | None = Query(default=None),
    failure_type: str | None = Query(default=None),
    question_id: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    canonical_only: bool = Query(default=False),
    include_bank: bool = Query(default=True),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=200),
) -> dict[str, Any]:
    try:
        if canonical_only:
            rows = service.get_canonical_items(run_id, include_bank=include_bank)
            if module:
                rows = [row for row in rows if row["module"] == module]
            if status:
                rows = [row for row in rows if row["status"] == status]
            if failure_type:
                rows = [row for row in rows if row.get("failure_type") == failure_type]
            if question_id:
                rows = [row for row in rows if row["question_id"] == question_id]
            if keyword:
                needle = keyword.lower()
                rows = [
                    row for row in rows
                    if needle in str(row).lower()
                ]
            total = len(rows)
            return {"items": rows[offset:offset + limit], "total": total, "offset": offset, "limit": limit}
        return service.get_items(
            run_id,
            module=module,
            status=status,
            failure_type=failure_type,
            question_id=question_id,
            keyword=keyword,
            include_bank=include_bank,
            offset=offset,
            limit=limit,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc


@app.post("/api/runs/{run_id}/retry-failures")
def retry_failures(run_id: str, payload: RetryRequest) -> dict[str, Any]:
    try:
        return service.retry_failed_items(
            run_id,
            concurrency_limit=payload.concurrency_limit,
            timeout=payload.timeout,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/canonical-summary")
def canonical_summary(run_id: str) -> dict[str, Any]:
    try:
        return service.get_canonical_summary(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc


@app.get("/api/runs/{run_id}/canonical-items")
def canonical_items(run_id: str) -> dict[str, Any]:
    try:
        return {"items": service.get_canonical_items(run_id, include_bank=True)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc


@app.get("/api/runs/{run_id}/timeline/{question_id}")
def get_item_timeline(run_id: str, question_id: str, canonical_only: bool = Query(default=False)) -> dict[str, Any]:
    try:
        return service.get_item_timeline(run_id, question_id, canonical_only=canonical_only)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="question or run not found") from exc


@app.post("/api/runs/{run_id}/items/{question_id}/judge")
def retry_judge(run_id: str, question_id: str, payload: JudgeRetryRequest) -> dict[str, Any]:
    try:
        return service.judge_run_item(run_id, question_id, attempt_run_id=payload.attempt_run_id, judge_connection_id=payload.judge_connection_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="question or run not found") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/runs/{run_id}/items/{question_id}/manual-review")
def submit_manual_review(run_id: str, question_id: str, payload: ManualReviewRequest) -> dict[str, Any]:
    try:
        return service.submit_manual_review(run_id, question_id, payload.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="question or run not found") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/items/{question_id}/reviews")
def review_history(run_id: str, question_id: str, attempt_run_id: str | None = Query(default=None)) -> dict[str, Any]:
    return service.get_review_history(run_id, question_id, attempt_run_id)


@app.get("/api/reviews/queue")
def review_queue(run_id: str | None = Query(default=None)) -> dict[str, Any]:
    rows = service.get_review_queue(run_id)
    return {"items": rows, "total": len(rows)}


@app.get("/api/review-settings")
def review_settings() -> dict[str, Any]:
    return service.get_review_settings()


@app.put("/api/review-settings")
def update_review_settings(payload: ReviewSettingsRequest) -> dict[str, Any]:
    try:
        return service.update_review_settings(payload.model_dump(exclude_unset=True))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/runs/{run_id}/items/{question_id}/review-threads")
def create_review_thread(run_id: str, question_id: str, payload: ReviewThreadCreateRequest) -> dict[str, Any]:
    try:
        return service.create_review_thread(run_id, question_id, payload.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="question or run not found") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/review-threads/{thread_id}")
def get_review_thread(thread_id: str) -> dict[str, Any]:
    try:
        return service.get_review_thread(thread_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="review thread not found") from exc


@app.post("/api/review-threads/{thread_id}/messages")
def send_review_message(thread_id: str, payload: ReviewMessageRequest) -> dict[str, Any]:
    try:
        return service.send_review_message(thread_id, payload.content, payload.connection_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="review thread not found") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/bank/items")
def list_bank_items(
    version: str | None = Query(default=None),
    module: str | None = Query(default=None),
    subtype: str | None = Query(default=None),
    item_format: str | None = Query(default=None),
    difficulty_tier: str | None = Query(default=None),
    qa_status: str | None = Query(default=None),
    include_archived: bool = Query(default=True),
    keyword: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    return service.list_bank_items(
        version=version,
        module=module,
        subtype=subtype,
        item_format=item_format,
        difficulty_tier=difficulty_tier,
        qa_status=qa_status,
        include_archived=include_archived,
        keyword=keyword,
        offset=offset,
        limit=limit,
    )


@app.get("/api/bank/versions")
def list_bank_versions() -> dict[str, Any]:
    return {"versions": service.list_bank_versions()}


@app.get("/api/bank/facets")
def bank_facets(
    version: str | None = Query(default=None),
    module: str | None = Query(default=None),
) -> dict[str, Any]:
    return service.get_bank_facets(version=version, module=module)


@app.get("/api/bank/items/{question_id}")
def get_bank_item(question_id: str, version: str | None = Query(default=None)) -> dict[str, Any]:
    item = service.get_bank_item(question_id, version=version)
    if not item:
        raise HTTPException(status_code=404, detail="question not found")
    return item


@app.post("/api/bank/items")
def create_bank_item(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return service.create_bank_item(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/bank/items/{question_id}")
def update_bank_item(question_id: str, payload: dict[str, Any], version: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        return service.update_bank_item(question_id, payload, version=version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="question not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/bank/items/{question_id}")
def delete_bank_item(question_id: str, version: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        deleted = service.delete_bank_item(question_id, version=version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="question not found")
    return {"deleted": True, "question_id": question_id}


@app.post("/api/bank/items/{question_id}/archive")
def archive_bank_item(question_id: str, version: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        item = service.archive_bank_item(question_id, version=version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not item:
        raise HTTPException(status_code=404, detail="question not found")
    return item


@app.post("/api/bank/items/{question_id}/restore")
def restore_bank_item(
    question_id: str, qa_status: str = Query(default="ready"), version: str | None = Query(default=None)
) -> dict[str, Any]:
    try:
        item = service.restore_bank_item(question_id, qa_status=qa_status, version=version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not item:
        raise HTTPException(status_code=404, detail="question not found")
    return item


@app.post("/api/bank/items/bulk-action")
def bulk_bank_action(payload: BankBulkActionRequest) -> dict[str, Any]:
    try:
        return service.bulk_bank_action(
            payload.question_ids,
            action=payload.action,
            qa_status=payload.qa_status,
            version=payload.version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/runs/{run_id}/report")
def generate_report(run_id: str) -> dict[str, Any]:
    try:
        return service.generate_report(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc


@app.get("/api/reports/{run_id}")
def get_report(run_id: str) -> dict[str, Any]:
    try:
        return service.get_report_payload(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc


# --------------------------------------------------------------------
# Dictionary CRUD (Phase 3): /api/dict/{modules,subtypes,quota_tags}
# --------------------------------------------------------------------
_DICT_KIND_SEGMENT = {"module": "module", "modules": "module", "subtype": "subtype", "subtypes": "subtype", "quota_tag": "quota_tag", "quota_tags": "quota_tag"}


def _resolve_dict_kind(segment: str) -> str:
    kind = _DICT_KIND_SEGMENT.get(segment.lower())
    if not kind:
        raise HTTPException(status_code=404, detail=f"unknown dict kind: {segment}")
    return kind


@app.get("/api/dict/{kind}")
def list_dict_entries(kind: str, include_inactive: bool = Query(default=True)) -> dict[str, Any]:
    real_kind = _resolve_dict_kind(kind)
    return {"items": service.list_dict(real_kind, include_inactive=include_inactive)}


@app.get("/api/dict/{kind}/{code}")
def get_dict_entry(kind: str, code: str) -> dict[str, Any]:
    real_kind = _resolve_dict_kind(kind)
    row = service.get_dict(real_kind, code)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return row


@app.post("/api/dict/{kind}")
async def upsert_dict_entry(kind: str, request: Request) -> dict[str, Any]:
    real_kind = _resolve_dict_kind(kind)
    payload = await request.json()
    if not payload.get("code"):
        raise HTTPException(status_code=400, detail="code is required")
    try:
        return service.upsert_dict(real_kind, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"validation: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc


@app.put("/api/dict/{kind}/{code}")
async def update_dict_entry(kind: str, code: str, request: Request) -> dict[str, Any]:
    real_kind = _resolve_dict_kind(kind)
    payload = await request.json()
    payload = dict(payload)
    payload["code"] = code
    return service.upsert_dict(real_kind, payload)


@app.delete("/api/dict/{kind}/{code}")
def delete_dict_entry(kind: str, code: str, hard: bool = Query(default=False)) -> dict[str, Any]:
    real_kind = _resolve_dict_kind(kind)
    deleted = service.delete_dict(real_kind, code, hard=hard)
    if not deleted:
        raise HTTPException(status_code=404, detail="not found")
    return {"deleted": True, "code": code, "hard": hard}


@app.post("/api/dict/{kind}/bulk")
async def bulk_upsert_dict(kind: str, request: Request) -> dict[str, Any]:
    real_kind = _resolve_dict_kind(kind)
    payload = await request.json()
    rows = payload.get("items") or []
    if not isinstance(rows, list):
        raise HTTPException(status_code=400, detail="items must be a list")
    return service.bulk_upsert_dict(real_kind, rows)
