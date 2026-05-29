#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from evaluation_engine import EvaluationRunService


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
    provider_id: str
    model_alias: str
    modules: list[str] | None = None
    module_filters: list[str] | None = None
    smoke: bool = False
    timeout: int | None = None
    max_items: int | None = None
    limit_per_module: int = 1
    concurrency_limit: int = Field(default=1, ge=1, le=4)
    question_ids: list[str] | None = None


class RetryRequest(BaseModel):
    timeout: int | None = None
    concurrency_limit: int = Field(default=1, ge=1, le=4)


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


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/system/paths")
def system_paths() -> dict[str, Any]:
    return service.get_system_paths()


@app.get("/api/providers")
def list_providers() -> dict[str, Any]:
    return {
        "providers": service.registry.list_providers(),
        "models": service.registry.list_models(),
    }


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
            modules=payload.modules or payload.module_filters,
            smoke=payload.smoke,
            timeout=payload.timeout,
            max_items=payload.max_items,
            limit_per_module=payload.limit_per_module,
            concurrency_limit=payload.concurrency_limit,
            question_ids=payload.question_ids,
        )
        return run
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/runs")
def list_runs() -> dict[str, Any]:
    return {"runs": service.list_runs()}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    try:
        return service.get_run(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc


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


@app.get("/api/bank/items")
def list_bank_items(
    module: str | None = Query(default=None),
    subtype: str | None = Query(default=None),
    item_format: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    return service.list_bank_items(
        module=module,
        subtype=subtype,
        item_format=item_format,
        keyword=keyword,
        offset=offset,
        limit=limit,
    )


@app.get("/api/bank/facets")
def bank_facets() -> dict[str, Any]:
    return service.get_bank_facets()


@app.get("/api/bank/items/{question_id}")
def get_bank_item(question_id: str) -> dict[str, Any]:
    item = service.get_bank_item(question_id)
    if not item:
        raise HTTPException(status_code=404, detail="question not found")
    return item


@app.post("/api/runs/{run_id}/report")
def generate_report(run_id: str) -> dict[str, Any]:
    try:
        return service.generate_report(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc


@app.get("/api/reports/{run_id}")
def get_report(run_id: str) -> dict[str, Any]:
    try:
        report = service.generate_report(run_id)
        path = Path(report["report_path"])
        return {"run_id": run_id, "report_path": str(path), "content": path.read_text(encoding="utf-8")}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
