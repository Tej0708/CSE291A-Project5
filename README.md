# Failure Propagation and Recovery in Multi-Agent Systems

**CSE 291A — Systems for Large Language Models and Agents**

## Project Overview

This project investigates how failures propagate through multi-agent AI systems and evaluates different strategies for detecting and recovering from these failures.

Multi-agent systems rely on communication and dependencies between specialized agents to complete complex tasks. When an agent produces incorrect, stale, or malicious outputs, these failures can propagate to downstream agents, potentially compromising task completion and overall system reliability.

To study these behaviors, we implement two practical multi-agent workflows:

1. **Workflow 1: Order Processing** — A multi-agent order fulfillment system involving inventory, pricing, shipping, and policy-related decisions.
2. **Workflow 2: Billing** — A multi-agent billing workflow involving coordinated agents responsible for processing and validating billing-related operations.

Both workflows serve as test environments for controlled fault injection, failure propagation analysis, and recovery evaluation.

## Project Structure

```text
CSE291A-Project5/
├── workflow1/
│   ├── README.md
│   └── ...
├── workflow2/
│   ├── README.md
│   └── ...
└── README.md
```

Each workflow contains its own implementation, configuration, experiments, and documentation.

## Methodology

We evaluate system behavior under both fault-free and fault-injected conditions.

**Fault Injection**

Controlled faults are introduced at intermediate stages of each workflow, including:

- Incorrect intermediate results
- Malicious or adversarial instructions
- Agent timeouts
- Stale outputs

**Recovery Strategies**

We compare the following execution strategies:

- **Clean Baseline:** Normal workflow execution without injected faults.
- **No Recovery:** Fault-injected execution without corrective intervention.
- **Full Restart:** Restarting the workflow after a fault is introduced.
- **Always Verify:** Validating intermediate outputs before downstream execution.

**Evaluation Metrics**

We measure:

- Clean task success rate
- Failure propagation rate
- Unauthorized actions
- Number of affected stages
- Wasted computational work
- End-to-end latency
- Recovery effectiveness and verification overhead

## Workflows

### Workflow 1: Order Processing

Simulates an order fulfillment process in which specialized agents coordinate to validate and process customer orders. Fault injection is used to investigate how unreliable intermediate outputs affect downstream decisions and final execution.

See [Workflow 1 README](./workflow1-order-fulfillment/README.md) for implementation details and experiment instructions.

### Workflow 2: Billing

Simulates a multi-agent billing process to study how faults introduced during billing operations affect downstream agents and overall workflow correctness.

See [Workflow 2 README](./workflow2-customer-service/README.md) for implementation details and experiment instructions.

## Project Goal

The goal is to characterize how failures spread across agent dependencies and compare the effectiveness and cost of different recovery strategies. By evaluating two distinct workflows, we aim to identify common failure patterns and understand the trade-offs between reliability, computational overhead, and execution latency.

---

**Course:** CSE 291A — Systems for Large Language Models and Agents
**Institution:** University of California, San Diego
