"""Strong deterministic verifier using business records, never evaluation labels."""
import time

from .validation import differences, reference_artifacts


class VerificationError(RuntimeError):
    pass


def verify_artifact(dataset, initial_state, task_id, artifact, logger):
    started = time.perf_counter()
    event = logger.log('verification_started', stage=artifact.stage,
                       parent_ids=[artifact.artifact_id])
    errors = differences(artifact.value, reference_artifacts(dataset, initial_state, task_id)[artifact.stage])
    logger.log('verification_completed', stage=artifact.stage, data={
        'verification_call_id': event, 'passed': not errors, 'errors': errors,
        'latency_ms': (time.perf_counter() - started) * 1000,
    }, parent_ids=[event, artifact.artifact_id])
    return not errors
