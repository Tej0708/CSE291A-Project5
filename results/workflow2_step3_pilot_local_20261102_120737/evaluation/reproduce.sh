# Execution command, for documentation only. Do not rerun without authorization.
cd /Users/yanghede/Downloads/CSE291A-Project5
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python run_live_pilot.py --execute --output results/workflow2_step3_pilot_local_20261102_120737_reproduction

# Offline report regeneration only (no paid calls):
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python results/workflow2_step3_pilot_local_20261102_120737/evaluation/evaluate.py
