from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import time

from core.artifact import artifact_source, tool_event_source
from core.budget import BudgetExceeded, RunBudget
from core.trace import TraceLogger
from core.workflow import CheckResult, Workflow, WorkflowResult
from data.loader import DEFAULT_DATASET_PATH
from .agents import build_agents
from .checker import assess_run
from .dataset import FulfillmentDataset
from .faults import FaultConfigurationError, FaultInjector, FaultSpec
from .models import ExecutionDecision
from .state import FulfillmentState
from .tools import FulfillmentTools
from .validation import authoritative_inputs, differences, reference_artifacts


class VerificationError(RuntimeError):
    pass


class FulfillmentWorkflow(Workflow):
    name = "fulfillment"

    def __init__(self, *, model_client, dataset_path=DEFAULT_DATASET_PATH, log_dir="logs"):
        self.dataset = FulfillmentDataset(dataset_path)
        self.agents = build_agents(model_client)
        self.log_dir = log_dir

    def list_task_ids(self):
        return self.dataset.list_order_ids()

    def run(self, task_id: str, *, fault: FaultSpec | None = None,
            mode: str = 'unprotected', budget: RunBudget | None = None) -> WorkflowResult:
        if mode not in ('unprotected', 'always_verify'):
            raise ValueError(f'Unknown execution mode: {mode}')
        if fault is not None and fault.case_id != task_id:
            raise ValueError('Fault schedule does not match the selected case')
        state = FulfillmentState.from_dataset(self.dataset, task_id)
        initial = deepcopy(state)
        logger = TraceLogger(workflow=self.name, task_id=task_id, log_dir=self.log_dir)
        budget = budget or RunBudget()
        injector = FaultInjector(fault)
        tools = FulfillmentTools(dataset=self.dataset, state=state, logger=logger,
                                 injector=injector, budget=budget)
        logger.log('workflow_started', data={'initial_state': state.snapshot(), 'mode': mode,
                                             'fault': asdict(fault) if fault else None,
                                             'budget': asdict(budget)})
        artifacts = []
        error = error_type = failed_stage = None
        run_status = 'completed'

        def verify(stage, actual, expected_factory, sources):
            budget.tool()
            started = time.perf_counter()
            logger.log('verification_started', stage=stage, parent_ids=sources)
            errors = differences(actual, expected_factory())
            logger.log('verification_completed', stage=stage,
                       data={'passed': not errors, 'errors': errors,
                             'latency_ms': (time.perf_counter() - started) * 1000,
                             'inference_calls': 0}, parent_ids=sources)
            if errors:
                raise VerificationError('; '.join(errors))

        def stage(agent, factory, input_tool=None):
            repair_started = None
            for attempt in range(2 if mode == 'always_verify' else 1):
                logger.log('stage_started', stage=agent.name, data={'attempt': attempt + 1})
                try:
                    payload, sources = factory()
                    if mode == 'always_verify' and input_tool:
                        verify(agent.name, payload,
                               lambda: authoritative_inputs(self.dataset, initial, task_id)[input_tool],
                               [source.source_id for source in sources])
                    budget.model()
                    artifact = agent.run(payload=payload, logger=logger, sources=sources)
                    artifact = injector.artifact(artifact, logger)
                    previous = next((i for i, value in enumerate(artifacts) if value.stage == agent.name), None)
                    if previous is None:
                        artifacts.append(artifact)
                    else:
                        artifacts[previous] = artifact
                    if mode == 'always_verify':
                        verify(agent.name, artifact.value,
                               lambda: reference_artifacts(self.dataset, initial, task_id)[agent.name],
                               [artifact.artifact_id])
                    if repair_started is not None:
                        logger.log('stage_repaired', stage=agent.name,
                                   data={'latency_ms': (time.perf_counter() - repair_started) * 1000})
                    return artifact
                except Exception as exc:
                    if (mode != 'always_verify' or attempt == 1 or isinstance(exc, (BudgetExceeded, FaultConfigurationError))
                            or getattr(exc, 'error_type', '') in ('AuthenticationError', 'PermissionDeniedError', 'RateLimitError')):
                        raise
                    logger.log('stage_retry', stage=agent.name,
                               data={'reason': str(exc), 'next_attempt': attempt + 2})
                    repair_started = time.perf_counter()
            raise AssertionError('unreachable')

        def read_factory(tool):
            payload, event_id = getattr(tools, tool)(task_id)
            return payload, [tool_event_source(event_id)]

        try:
            order_context, order_event_id = tools.get_order_context(task_id)
            if mode == 'always_verify':
                verify('order_context', order_context,
                       lambda: authoritative_inputs(self.dataset, initial, task_id)['get_order_context'],
                       [order_event_id])
            inventory = stage(self.agents.inventory, lambda: read_factory('get_inventory_inputs'), 'get_inventory_inputs')
            pricing = stage(self.agents.pricing, lambda: read_factory('get_pricing_inputs'), 'get_pricing_inputs')
            shipping = stage(self.agents.shipping, lambda: read_factory('get_shipping_inputs'), 'get_shipping_inputs')
            plan = stage(self.agents.planner, lambda: (
                {'order': order_context['order'], 'inventory': inventory.value,
                 'pricing': pricing.value, 'shipping': shipping.value},
                [tool_event_source(order_event_id), artifact_source(inventory),
                 artifact_source(pricing), artifact_source(shipping)]))
            executor = stage(self.agents.executor, lambda: (
                {'order': order_context, 'plan': plan.value},
                [tool_event_source(order_event_id), artifact_source(plan)]))
            execution = ExecutionDecision.model_validate(executor.value)
            expected_actions = reference_artifacts(self.dataset, initial, task_id)['executor_agent']['actions']
            for index, action in enumerate(execution.actions):
                policy_errors = (differences(action.model_dump(mode='json'), expected_actions[index])
                                 if index < len(expected_actions) else ['Unexpected extra action'])
                repair_started = None
                for attempt in range(2 if mode == 'always_verify' else 1):
                    logger.log('action_audited', stage=action.tool,
                               data={'authorized': not policy_errors, 'errors': policy_errors,
                                     'action': action.model_dump(mode='json'), 'attempt': attempt + 1},
                               parent_ids=[executor.artifact_id])
                    try:
                        tools.execute_action(action, triggered_by_artifact_id=executor.artifact_id)
                        if repair_started is not None:
                            logger.log('tool_repaired', stage=action.tool,
                                       data={'latency_ms': (time.perf_counter() - repair_started) * 1000})
                        break
                    except TimeoutError:
                        if mode != 'always_verify' or attempt == 1:
                            raise
                        logger.log('tool_retry', stage=action.tool, data={'next_attempt': attempt + 2})
                        repair_started = time.perf_counter()
        except Exception as exc:
            run_status = 'error'
            error, error_type = str(exc), getattr(exc, 'error_type', type(exc).__name__)
            failed_stage = logger.last_stage

        check, task_check, stage_checks = assess_run(
            order_id=task_id, dataset=self.dataset, initial_state=initial,
            final_state=state, artifacts=artifacts)
        if error:
            check = CheckResult(False, check.errors + (f'{failed_stage}: {error}',))
        logger.log('workflow_completed', data={
            'outcome': state.order_status, 'run_status': run_status,
            'check_passed': check.passed, 'check_errors': list(check.errors),
            'task_passed': task_check.passed, 'task_errors': list(task_check.errors),
            'stage_checks': {name: asdict(value) for name, value in stage_checks.items()},
            'failed_stage': failed_stage, 'error_type': error_type, 'error': error,
            'fault_applied': injector.applied, 'final_state': state.snapshot(),
        }, parent_ids=[artifact.artifact_id for artifact in artifacts])
        return WorkflowResult(
            workflow=self.name, task_id=task_id, run_id=logger.run_id,
            outcome=state.order_status, artifacts=tuple(artifacts), check=check,
            log_path=str(logger.path), run_status=run_status, failed_stage=failed_stage,
            error_type=error_type, error=error, initial_state=initial.snapshot(),
            final_state=state.snapshot(), task_check=task_check,
            stage_checks=stage_checks, fault_applied=injector.applied,
        )
