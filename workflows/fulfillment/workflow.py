from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace

from core.artifact import artifact_source, tool_event_source
from core.budget import RunBudget
from core.model_client import INFRASTRUCTURE_ERRORS
from core.trace import TraceLogger
from core.workflow import CheckResult, Workflow, WorkflowResult
from data.loader import DEFAULT_DATASET_PATH
from .agents import build_agents
from .checker import assess_run
from .dataset import FulfillmentDataset
from .faults import FaultInjector, FaultSpec
from .models import ExecutionDecision
from .state import FulfillmentState
from .tools import FulfillmentTools
from .validation import differences, reference_artifacts
from .verifier import VerificationError, verify_artifact


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
        if mode not in ('unprotected', 'full_restart', 'always_verify'):
            raise ValueError(f'Unknown execution mode: {mode}')
        budget = budget or RunBudget()
        first = self._run_attempt(task_id, fault=fault, mode=mode, budget=budget)
        attempts = [first]
        if mode == 'full_restart' and first.fault_applied and self._retryable(first.error_type):
            second = self._run_attempt(task_id, fault=None, mode=mode, budget=budget)
            attempts.append(second)
        return replace(attempts[-1], attempts=tuple(attempts),
                       fault_applied=any(item.fault_applied for item in attempts))

    @staticmethod
    def _retryable(error_type):
        return error_type not in INFRASTRUCTURE_ERRORS | {
            'BudgetExceeded', 'InferenceBudgetExceeded', 'FaultConfigurationError',
            'BadRequestError', 'NotFoundError', 'UnprocessableEntityError',
            # Programming defects must remain visible rather than consume retries.
            'TypeError', 'AttributeError', 'KeyError', 'IndexError',
            'NameError', 'AssertionError', 'NotImplementedError',
        }

    def _run_attempt(self, task_id, *, fault, mode, budget):
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

        def stage(agent, factory):
            for attempt in range(1, 3 if mode == 'always_verify' else 2):
                logger.log('stage_started', stage=agent.name, data={'attempt': attempt})
                try:
                    payload, sources = factory()
                    budget.model()
                    artifact = agent.run(payload=payload, logger=logger, sources=sources)
                    artifact = injector.artifact(artifact, logger)
                    if mode == 'always_verify':
                        budget.tool()
                        verdict = verify_artifact(self.dataset, initial, task_id, artifact, logger)
                        if not verdict:
                            raise VerificationError('Artifact differs from authoritative records')
                    if attempt > 1:
                        logger.log('stage_repaired', stage=agent.name,
                                   parent_ids=[artifact.artifact_id])
                    artifacts.append(artifact)
                    return artifact
                except Exception as exc:
                    if (mode != 'always_verify' or attempt == 2
                            or not self._retryable(getattr(exc, 'error_type', type(exc).__name__))):
                        raise
                    logger.log('stage_retry', stage=agent.name,
                               data={'attempt': attempt + 1, 'error': str(exc)})

        def read_factory(tool):
            payload, event_id = getattr(tools, tool)(task_id)
            return payload, [tool_event_source(event_id)]

        try:
            for context_attempt in range(2 if mode == 'always_verify' else 1):
                try:
                    order_context, order_event_id = tools.get_order_context(task_id)
                    if context_attempt:
                        logger.log('tool_repaired', stage='get_order_context')
                    break
                except Exception as exc:
                    if context_attempt or mode != 'always_verify' or not self._retryable(
                            getattr(exc, 'error_type', type(exc).__name__)):
                        raise
                    logger.log('tool_retry', stage='get_order_context', data={'error': str(exc)})
            inventory = stage(self.agents.inventory, lambda: read_factory('get_inventory_inputs'))
            pricing = stage(self.agents.pricing, lambda: read_factory('get_pricing_inputs'))
            shipping = stage(self.agents.shipping, lambda: read_factory('get_shipping_inputs'))
            plan_reads = 0

            def plan_factory():
                nonlocal order_context, order_event_id, plan_reads
                if plan_reads:
                    order_context, order_event_id = tools.get_order_context(task_id)
                plan_reads += 1
                context, context_sources = order_context, [tool_event_source(order_event_id)]
                return (
                    {'order': context['order'], 'inventory': inventory.value,
                     'pricing': pricing.value, 'shipping': shipping.value},
                    context_sources + [artifact_source(inventory),
                                       artifact_source(pricing), artifact_source(shipping)])
            plan = stage(self.agents.planner, plan_factory)
            executor_reads = 0

            def executor_factory():
                nonlocal order_context, order_event_id, executor_reads
                if executor_reads:
                    order_context, order_event_id = tools.get_order_context(task_id)
                executor_reads += 1
                return ({'order': order_context, 'plan': plan.value},
                        [tool_event_source(order_event_id), artifact_source(plan)])

            executor = stage(self.agents.executor, executor_factory)
            execution = ExecutionDecision.model_validate(executor.value)
            expected_actions = reference_artifacts(self.dataset, initial, task_id)['executor_agent']['actions']
            for index, action in enumerate(execution.actions):
                policy_errors = (differences(action.model_dump(mode='json'), expected_actions[index])
                                 if index < len(expected_actions) else ['Unexpected extra action'])
                audit_id = logger.log('action_audited', stage=action.tool,
                           data={'authorized': not policy_errors, 'errors': policy_errors,
                                 'action': action.model_dump(mode='json'), 'attempt': 1},
                           parent_ids=[executor.artifact_id])
                tools.execute_action(action, triggered_by_artifact_id=executor.artifact_id,
                                     audit_event_id=audit_id)
        except Exception as exc:
            run_status = 'error'
            error, error_type = str(exc), getattr(exc, 'error_type', type(exc).__name__)
            failed_stage = logger.last_stage

        # Full restart is an oracle baseline: injection evidence is the trigger,
        # regardless of whether the fault affected correctness or was consumed.
        recovery_detected = injector.applied if mode == 'full_restart' else bool(error)
        if mode == 'full_restart':
            logger.log('failure_detection_completed', data={
                'detected': injector.applied, 'errors': [], 'latency_ms': 0,
                'error_type': error_type, 'policy': 'oracle_fault_applied'})

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
            recovery_detected=recovery_detected,
        )
