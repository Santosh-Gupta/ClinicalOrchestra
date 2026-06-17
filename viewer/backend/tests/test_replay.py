"""Smoke tests for run discovery and the replay adapter.

These run against whatever lives in the configured runs dir, so they assert on
invariants rather than specific cases. Run with: ``pytest`` from viewer/backend.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from clinical_viewer import runs as runs_mod
from clinical_viewer import config as config_mod
from clinical_viewer.adapters.replay import build_case_timeline
from clinical_viewer.config import runs_dir
from clinical_viewer.events import EventType


def _first_run_with_cases():
    for run in runs_mod.list_runs():
        cases = runs_mod.list_cases(run.run_id)
        if cases:
            return run.run_id, cases
    return None, None


@pytest.mark.skipif(not runs_dir().is_dir(), reason="no runs dir configured")
def test_runs_discoverable():
    assert isinstance(runs_mod.list_runs(), list)


@pytest.mark.skipif(not runs_dir().is_dir(), reason="no runs dir configured")
def test_timeline_is_ordered_and_bookended():
    run_id, cases = _first_run_with_cases()
    if not run_id:
        pytest.skip("no cases found in any run")
    run_dir = runs_mod.resolve_case_dir(run_id)
    tl = build_case_timeline(run_dir, run_id, cases[0].case_id)

    assert tl.events, "expected at least one event"
    # seq is monotonic and dense
    assert [e.seq for e in tl.events] == list(range(len(tl.events)))
    # every timeline starts with case_started and ends with case_completed
    assert tl.events[0].type == EventType.CASE_STARTED
    assert tl.events[-1].type == EventType.CASE_COMPLETED
    assert tl.trace_source in {"native", "replay"}
    assert tl.trace_notice


@pytest.mark.skipif(not runs_dir().is_dir(), reason="no runs dir configured")
def test_rich_artifacts_surface_prompt_and_model_response():
    for run in runs_mod.list_runs():
        run_dir = runs_mod.resolve_case_dir(run.run_id)
        for case in runs_mod.list_cases(run.run_id):
            if (run_dir / f"{case.case_id}.retrieval_prompt.txt").exists() and (
                run_dir / f"{case.case_id}.retrieval_response.json"
            ).exists():
                tl = build_case_timeline(run_dir, run.run_id, case.case_id)
                types = [event.type for event in tl.events]
                assert tl.trace_source in {"native", "replay"}
                assert EventType.PROMPT_BUILT in types
                assert EventType.MODEL_RESPONSE in types
                return
    pytest.skip("no rich prompt/response artifacts found")


def test_replay_reconstructs_pubmed_tool_calls(tmp_path):
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    case_id = "case-1"
    (run_dir / f"{case_id}.queries.json").write_text(
        json.dumps(
            [
                {
                    "query_id": "r1q1",
                    "query": "microascus sinusitis",
                    "source": "pubmed",
                    "intent": "find discriminator",
                    "round_index": 1,
                    "generated_by": "preset_template",
                }
            ]
        ),
        encoding="utf-8",
    )
    (run_dir / f"{case_id}.evidence.json").write_text(
        json.dumps(
            [
                {
                    "evidence_id": "pubmed:123",
                    "query_id": "r1q1",
                    "rank": 1,
                    "pmid": "123",
                    "pmcid": "PMC999",
                    "title": "Microascus sinusitis",
                    "journal": "Medical Mycology",
                    "publication_year": "2024",
                    "source_scope": "full_text",
                    "full_text_snippet": "Full text diagnostic details.",
                    "excluded": False,
                }
            ]
        ),
        encoding="utf-8",
    )

    tl = build_case_timeline(run_dir, "run-1", case_id)
    tool_events = [event for event in tl.events if event.type == EventType.TOOL_CALL]
    tool = tool_events[0]
    pmc_tool = next(event for event in tool_events if event.payload["tool"] == "pmc_fetch")
    evidence_event = next(event for event in tl.events if event.type == EventType.EVIDENCE_RETRIEVED)

    assert tool.title == "PubMed search · r1q1"
    assert tool.payload["tool"] == "pubmed_search"
    assert tool.payload["pmids"] == ["123"]
    assert tool.payload["output_evidence_ids"] == ["pubmed:123"]
    assert pmc_tool.payload["pmcids"] == ["PMC999"]
    assert pmc_tool.payload["output_evidence_ids"] == ["pubmed:123"]
    assert evidence_event.payload["query_id"] == "r1q1"
    assert evidence_event.payload["rank"] == 1
    assert evidence_event.payload["source_scope"] == "full_text"
    assert evidence_event.payload["full_text_snippet"] == "Full text diagnostic details."
    assert {artifact.name for artifact in tl.artifacts} == {"queries", "evidence"}


def test_path_traversal_rejected():
    with pytest.raises((ValueError, FileNotFoundError)):
        runs_mod.list_cases("../etc")


def test_case_summaries_include_native_event_metadata(tmp_path, monkeypatch):
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    event_path = run_dir / "case-1.events.jsonl"
    event_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "e0000",
                        "seq": 0,
                        "run_id": "run-1",
                        "case_id": "case-1",
                        "type": "case_started",
                        "actor": "runner",
                        "title": "Case case-1",
                    }
                ),
                json.dumps(
                    {
                        "id": "e0001",
                        "seq": 1,
                        "run_id": "run-1",
                        "case_id": "case-1",
                        "type": "case_completed",
                        "actor": "runner",
                        "title": "Case complete",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLINICAL_HARNESS_RUNS", str(tmp_path))
    config_mod.runs_dir.cache_clear()
    try:
        run = runs_mod.list_runs()[0]
        case = runs_mod.list_cases("run-1")[0]
    finally:
        config_mod.runs_dir.cache_clear()

    assert run.native_event_case_count == 1
    assert run.incomplete_case_count == 0
    assert case.has_native_events
    assert case.event_count == 2
    assert case.last_event_type == "case_completed"
    assert case.is_complete is True


def test_native_event_ledger_artifact_is_served(tmp_path, monkeypatch):
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from clinical_viewer.app import app

    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    event_path = run_dir / "case-1.events.jsonl"
    event_path.write_text(
        json.dumps(
            {
                "id": "e0000",
                "seq": 0,
                "run_id": "run-1",
                "case_id": "case-1",
                "type": "case_started",
                "actor": "runner",
                "title": "Case case-1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLINICAL_HARNESS_RUNS", str(tmp_path))
    config_mod.runs_dir.cache_clear()
    try:
        response = fastapi_testclient.TestClient(app).get("/api/runs/run-1/cases/case-1/artifacts/events")
    finally:
        config_mod.runs_dir.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "events"
    assert body["filename"] == "case-1.events.jsonl"
    assert '"case_started"' in body["content"]


def test_save_trace_writes_user_generated_bundle(tmp_path, monkeypatch):
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from clinical_viewer.app import app

    run_dir = tmp_path / "runs" / "run-1"
    export_dir = tmp_path / "exports"
    run_dir.mkdir(parents=True)
    case_id = "case-1"
    (run_dir / "retrieval_guided_results.jsonl").write_text(
        json.dumps(
            {
                "case_id": case_id,
                "expected_diagnosis": "Anti-NMDA receptor encephalitis",
                "model_final_diagnosis": "Autoimmune encephalitis",
                "score": "pass",
                "score_method": "judge",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / f"{case_id}.events.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "e0000",
                        "seq": 0,
                        "run_id": "run-1",
                        "case_id": case_id,
                        "type": "case_started",
                        "actor": "runner",
                        "title": "Case case-1",
                    }
                ),
                json.dumps(
                    {
                        "id": "e0001",
                        "seq": 1,
                        "run_id": "run-1",
                        "case_id": case_id,
                        "type": "answer",
                        "actor": "diagnostician",
                        "title": "Final diagnosis",
                        "payload": {"final_diagnosis": "Autoimmune encephalitis"},
                    }
                ),
                json.dumps(
                    {
                        "id": "e0002",
                        "seq": 2,
                        "run_id": "run-1",
                        "case_id": case_id,
                        "type": "case_completed",
                        "actor": "runner",
                        "title": "Case complete",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLINICAL_HARNESS_RUNS", str(tmp_path / "runs"))
    monkeypatch.setenv("CLINICAL_VIEWER_USER_GENERATED", str(export_dir))
    config_mod.runs_dir.cache_clear()
    config_mod.user_generated_dir.cache_clear()
    try:
        response = fastapi_testclient.TestClient(app).post("/api/runs/run-1/cases/case-1/save")
    finally:
        config_mod.runs_dir.cache_clear()
        config_mod.user_generated_dir.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body["correct_answer"] == "Anti-NMDA receptor encephalitis"
    assert body["event_count"] == 3
    json_path = export_dir / "traces" / Path(body["directory"]).name / "trace.json"
    md_path = export_dir / "traces" / Path(body["directory"]).name / "trace.md"
    assert json_path.exists()
    assert md_path.exists()
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["correct_answer"] == "Anti-NMDA receptor encephalitis"
    assert saved["events"][1]["payload"]["final_diagnosis"] == "Autoimmune encephalitis"
    assert "Correct answer: Anti-NMDA receptor encephalitis" in md_path.read_text(encoding="utf-8")


def test_new_case_endpoint_writes_user_generated_run(tmp_path, monkeypatch):
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from clinical_viewer.app import app

    generated_dir = tmp_path / "viewer-generated"
    monkeypatch.setenv("CLINICAL_HARNESS_RUNS", str(tmp_path / "runs"))
    monkeypatch.setenv("CLINICAL_VIEWER_USER_GENERATED", str(generated_dir))
    config_mod.runs_dir.cache_clear()
    config_mod.user_generated_dir.cache_clear()
    config_mod.user_generated_runs_dir.cache_clear()
    try:
        response = fastapi_testclient.TestClient(app).post(
            "/api/new-case",
            json={
                "title": "Synthetic encephalitis case",
                "prompt": (
                    "A 19-year-old woman develops subacute psychosis, seizures, orofacial dyskinesias, "
                    "and lymphocytic CSF pleocytosis over three weeks."
                ),
                "correct_answer": "anti-NMDA receptor encephalitis",
                "aliases": ["NMDAR encephalitis"],
                "dry_run": True,
                "retrieve": False,
                "judge": False,
                "max_queries": 2,
                "articles_per_query": 3,
                "max_rounds": 1,
            },
        )
        assert response.status_code == 200
        body = response.json()
        event_path = Path(body["run_dir"]) / f"{body['case_id']}.events.jsonl"
        for _ in range(50):
            if event_path.exists() and "case_completed" in event_path.read_text(encoding="utf-8"):
                break
            time.sleep(0.05)
        else:
            pytest.fail("new case background run did not finish")

        run = next(run for run in runs_mod.list_runs() if run.run_id == body["run_id"])
        cases = runs_mod.list_cases(body["run_id"])
    finally:
        config_mod.runs_dir.cache_clear()
        config_mod.user_generated_dir.cache_clear()
        config_mod.user_generated_runs_dir.cache_clear()

    assert run.path == body["run_dir"]
    assert cases[0].case_id == body["case_id"]
    assert cases[0].expected_diagnosis == "anti-NMDA receptor encephalitis"


def test_runledger_case_is_discovered_and_replayed(tmp_path, monkeypatch):
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    case_id = "case-1"
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "case_id": case_id,
                "mode": "pubmed_only",
                "status": "completed",
                "answer_path": str(run_dir / "answer.json"),
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "answer.json").write_text(
        json.dumps(
            {
                "final_diagnosis": "Anti-NMDA receptor encephalitis",
                "confidence": "medium",
                "recommended_next_step": "CSF antibody testing",
            }
        ),
        encoding="utf-8",
    )
    rows = [
        {
            "event_id": "event:1",
            "timestamp": "2026-01-01T00:00:00Z",
            "actor": "runner",
            "action": "run_created",
            "input_ids": [],
            "output_ids": ["run-1"],
            "details": {"mode": "pubmed_only"},
            "error": None,
        },
        {
            "event_id": "event:2",
            "timestamp": "2026-01-01T00:00:01Z",
            "actor": "template_runner",
            "action": "problem_represented",
            "input_ids": [case_id],
            "output_ids": [f"problem:{case_id}"],
            "details": {"one_liner": "Young adult with psychosis and seizures."},
            "error": None,
        },
        {
            "event_id": "event:3",
            "timestamp": "2026-01-01T00:00:02Z",
            "actor": "template_runner",
            "action": "query_generated",
            "input_ids": [case_id],
            "output_ids": ["query:1"],
            "details": {
                "query_id": "query:1",
                "query": "psychosis seizures autoimmune encephalitis",
                "intent": "find syndrome",
            },
            "error": None,
        },
        {
            "event_id": "event:4",
            "timestamp": "2026-01-01T00:00:03Z",
            "actor": "pubmed",
            "action": "query_executed",
            "input_ids": ["query:1"],
            "output_ids": ["query:1"],
            "details": {
                "query": "psychosis seizures autoimmune encephalitis",
                "result_count": 42,
                "returned_articles": 5,
            },
            "error": None,
        },
        {
            "event_id": "event:5",
            "timestamp": "2026-01-01T00:00:04Z",
            "actor": "pubmed",
            "action": "evidence_recorded",
            "input_ids": ["query:1"],
            "output_ids": ["evidence:123"],
            "details": {"pmid": "123", "pmcid": "PMC123", "doi": "10.1/example"},
            "error": None,
        },
        {
            "event_id": "event:6",
            "timestamp": "2026-01-01T00:00:05Z",
            "actor": "template_runner",
            "action": "answer_written",
            "input_ids": [case_id, "evidence:123"],
            "output_ids": ["answer"],
            "details": {"answer_path": str(run_dir / "answer.json"), "confidence": "medium"},
            "error": None,
        },
    ]
    (run_dir / "events.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    (run_dir / "queries.jsonl").write_text("{}\n", encoding="utf-8")
    (run_dir / "evidence.jsonl").write_text("{}\n", encoding="utf-8")

    monkeypatch.setenv("CLINICAL_HARNESS_RUNS", str(tmp_path))
    config_mod.runs_dir.cache_clear()
    try:
        cases = runs_mod.list_cases("run-1")
    finally:
        config_mod.runs_dir.cache_clear()

    tl = build_case_timeline(run_dir, "run-1", case_id)
    types = [event.type for event in tl.events]

    assert [case.case_id for case in cases] == [case_id]
    assert cases[0].has_native_events
    assert cases[0].event_count == len(rows)
    assert cases[0].last_event_type == "answer_written"
    assert cases[0].is_complete is True
    assert tl.trace_source == "replay"
    assert EventType.PROBLEM_REPRESENTATION in types
    assert EventType.QUERY_GENERATED in types
    assert EventType.TOOL_CALL in types
    assert EventType.EVIDENCE_RETRIEVED in types
    assert EventType.ANSWER in types
    assert tl.events[-1].type == EventType.CASE_COMPLETED
    assert tl.model_diagnosis == "Anti-NMDA receptor encephalitis"
    assert {artifact.name for artifact in tl.artifacts} == {
        "ledger_answer",
        "ledger_events",
        "ledger_evidence",
        "ledger_manifest",
        "ledger_queries",
    }


def test_runledger_artifact_is_served(tmp_path, monkeypatch):
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from clinical_viewer.app import app

    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps({"run_id": "run-1", "case_id": "case-1", "status": "completed"}),
        encoding="utf-8",
    )
    (run_dir / "events.jsonl").write_text(
        json.dumps({"event_id": "event:1", "action": "run_created", "details": {}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLINICAL_HARNESS_RUNS", str(tmp_path))
    config_mod.runs_dir.cache_clear()
    try:
        response = fastapi_testclient.TestClient(app).get(
            "/api/runs/run-1/cases/case-1/artifacts/ledger_events"
        )
    finally:
        config_mod.runs_dir.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "ledger_events"
    assert body["filename"] == "events.jsonl"
    assert '"run_created"' in body["content"]
