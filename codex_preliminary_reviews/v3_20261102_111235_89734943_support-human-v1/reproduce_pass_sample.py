"""Read-only reproduction of the saved stratified PASS-case sample."""
import json
import math
from pathlib import Path
import random

sample = json.loads(Path(__file__).with_name('pass_sample_manifest.json').read_text())
rng = random.Random(sample['seed'])
selected = []
for group in ('tech_only', 'billing_only', 'multi_issue'):
    population = sorted(sample['strata'][group]['population'])
    chosen = sorted(rng.sample(population, math.ceil(0.20 * len(population))))
    assert chosen == sample['strata'][group]['selected']
    selected.extend(chosen)
assert sorted(selected) == sample['selected_case_ids']
print('\n'.join(sorted(selected)))
