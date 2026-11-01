from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_DATASET_PATH = Path(__file__).with_name("dataset.json")


@lru_cache(maxsize=4)
def load_dataset(path: str | Path = DEFAULT_DATASET_PATH) -> dict[str, Any]:
    dataset_path = Path(path).resolve()
    with dataset_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError("Dataset root must be a JSON object.")
    return data
