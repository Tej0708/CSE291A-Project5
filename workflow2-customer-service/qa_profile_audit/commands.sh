# Run from /Users/yanghede/Downloads/CSE291A-Project5.
# Output files must not already exist; use a fresh directory for reproduction.
mkdir -p qa_profile_audit/reproduce
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s human_review_tool -v
PYTHONDONTWRITEBYTECODE=1 python3 run_fault_audit.py --fault qa_corruption --profile qa_first_missing_once_v1 --backend rule --output qa_profile_audit/reproduce/profile_rule.json
PYTHONDONTWRITEBYTECODE=1 python3 run_fault_audit.py --fault qa_corruption --profile qa_first_missing_once_v1 --backend scripted --output qa_profile_audit/reproduce/profile_scripted.json
PYTHONDONTWRITEBYTECODE=1 python3 run_fault_audit.py --fault qa_corruption --backend rule --output qa_profile_audit/reproduce/original_rule.json
PYTHONDONTWRITEBYTECODE=1 python3 run_fault_audit.py --fault qa_corruption --backend scripted --output qa_profile_audit/reproduce/original_scripted.json
