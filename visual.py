import json
from collections import defaultdict
from pathlib import Path

path = Path(__file__).parent / "support_cases_unique40.jsonl"

with path.open(encoding="utf-8") as f:
    rows = [json.loads(line) for line in f if line.strip()]

cases = [row for row in rows if row["fault_type"] == "none"]

# 查找完全相同的用户请求
duplicates = defaultdict(list)
for case in cases:
    duplicates[case["user_query"]].append(case)

print(f"正常案例：{len(cases)} 条")
print(f"不重复请求文本：{len(duplicates)} 条")
print("按 Enter 查看下一条；输入 q 退出。\n")

for index, case in enumerate(cases, start=1):
    print("=" * 70)
    print(f"[{index}/{len(cases)}] {case['case_id']}")
    print(f"场景：{case['scenario_group']} | Split：{case['split']}")

    print("\n用户原话：")
    print(case["user_query"])

    print("\n预期问题：", case["expected_issues"])
    print("预期客服：", case["expected_routing"])
    print("预期状态：", case["expected_final_status"])
    print("最大轮数：", case["max_iterations"])

    others = [
        f"{other['case_id']} ({other['split']})"
        for other in duplicates[case["user_query"]]
        if other["case_id"] != case["case_id"]
    ]
    if others:
        print("\n重复请求：", ", ".join(others))

    print("\n检查：有没有漏标、多标？客服是否正确？分组是否合理？")

    if input("\nEnter 下一条 / q 退出：").strip().lower() == "q":
        break