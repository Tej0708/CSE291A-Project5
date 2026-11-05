import json
from pathlib import Path

from experiments.scripted_model import ScriptedModelClient as FakeModelClient
from workflows.fulfillment.workflow import FulfillmentWorkflow


def test_all_fulfillment_cases_pass_with_deterministic_model(tmp_path) -> None:
    workflow = FulfillmentWorkflow(
        model_client=FakeModelClient(),
        log_dir=tmp_path,
    )

    task_ids = workflow.list_task_ids()
    assert len(task_ids) == 30

    for task_id in task_ids:
        result = workflow.run(task_id)
        assert result.check.passed, (task_id, result.check.errors)
        assert result.log_path.endswith(".jsonl")


def test_artifact_sources_are_recorded(tmp_path) -> None:
    workflow = FulfillmentWorkflow(
        model_client=FakeModelClient(),
        log_dir=tmp_path,
    )
    result = workflow.run("ORD-1001")

    inventory, pricing, shipping, plan, executor = result.artifacts

    assert len(inventory.sources) == 1
    assert inventory.sources[0].source_type == "tool_event"
    assert len(pricing.sources) == 1
    assert pricing.sources[0].source_type == "tool_event"
    assert len(shipping.sources) == 1
    assert shipping.sources[0].source_type == "tool_event"

    plan_artifact_sources = {
        source.source_id for source in plan.sources if source.source_type == "artifact"
    }
    assert plan_artifact_sources == {
        inventory.artifact_id,
        pricing.artifact_id,
        shipping.artifact_id,
    }
    assert any(source.source_type == "tool_event" for source in plan.sources)

    executor_artifact_sources = {
        source.source_id for source in executor.sources if source.source_type == "artifact"
    }
    assert executor_artifact_sources == {plan.artifact_id}
    assert any(source.source_type == "tool_event" for source in executor.sources)


def test_every_artifact_source_resolves_in_same_trace(tmp_path) -> None:
    workflow = FulfillmentWorkflow(
        model_client=FakeModelClient(),
        log_dir=tmp_path,
    )
    result = workflow.run("ORD-1001")

    records = [
        json.loads(line)
        for line in Path(result.log_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    event_ids = {record["event_id"] for record in records}
    artifact_ids = {
        record["data"]["artifact"]["artifact_id"]
        for record in records
        if record["event_type"] == "agent_completed"
    }

    for artifact in result.artifacts:
        for source in artifact.sources:
            if source.source_type == "tool_event":
                assert source.source_id in event_ids
            else:
                assert source.source_id in artifact_ids
