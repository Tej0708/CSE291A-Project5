import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

# Change this filename if you renamed your dataset.
DATASET_PATH = Path(__file__).parent / "support_cases_unique40.jsonl"


def main():
    with DATASET_PATH.open(encoding="utf-8") as file:
        rows = [json.loads(line) for line in file if line.strip()]

    clean_cases = [row for row in rows if row["fault_type"] == "none"]

    if len(rows) != 200 or len(clean_cases) != 40:
        raise ValueError(
            f"Expected 200 total cases and 40 clean cases; "
            f"found {len(rows)} and {len(clean_cases)}."
        )

    if len({row["case_id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate case IDs found.")

    updated_rows = [
        {
            **row,
            "scenario_group": (
                "multi_issue"
                if row["scenario_group"] == "ambiguous"
                else row["scenario_group"]
            ),
        }
        for row in rows
    ]

    changed_count = sum(
        old["scenario_group"] != new["scenario_group"]
        for old, new in zip(rows, updated_rows)
    )

    clean_counts = Counter(
        row["scenario_group"]
        for row in updated_rows
        if row["fault_type"] == "none"
    )

    expected_counts = {
        "tech_only": 10,
        "billing_only": 10,
        "multi_issue": 20,
    }

    if dict(clean_counts) != expected_counts:
        raise ValueError(f"Unexpected clean-case groups: {dict(clean_counts)}")

    if changed_count:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = DATASET_PATH.with_name(
            f"{DATASET_PATH.stem}_backup_{timestamp}.jsonl"
        )
        shutil.copy2(DATASET_PATH, backup_path)

        temporary_path = DATASET_PATH.with_name(
            f"{DATASET_PATH.name}.{timestamp}.tmp"
        )

        with temporary_path.open("w", encoding="utf-8") as file:
            for row in updated_rows:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")

        temporary_path.replace(DATASET_PATH)

        with DATASET_PATH.open(encoding="utf-8") as file:
            saved_rows = [json.loads(line) for line in file if line.strip()]

        if saved_rows != updated_rows:
            raise RuntimeError(f"Verification failed. Backup: {backup_path}")

        print(f"Updated dataset: {DATASET_PATH.name}")
        print(f"Backup created: {backup_path.name}")
    else:
        print("No ambiguous labels found. No changes needed.")

    print(f"Rows changed: {changed_count}")
    print("Clean-case groups:")
    for group, count in sorted(clean_counts.items()):
        print(f"  {group}: {count}")


if __name__ == "__main__":
    main()