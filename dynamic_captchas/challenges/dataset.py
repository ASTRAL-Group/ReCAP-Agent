import random
from pathlib import Path
from typing import Any, Dict

from datasets import load_from_disk

from .common import count_for_scope

TEXT_CAPTCHA_DATASET_DIR = Path(__file__).resolve().parents[1] / "data" / "text_captcha"


def load_text_captcha_dataset():
    """Load CAPTCHA dataset from Hugging Face."""
    dataset = load_from_disk(str(TEXT_CAPTCHA_DATASET_DIR))
    return dataset


def get_random_text_captcha_entry(dataset, dataset_scope: str = "dynamic") -> Dict[str, Any]:
    """Get a random CAPTCHA entry from the Hugging Face dataset."""
    dataset_length = len(dataset)
    scoped_count = count_for_scope(dataset_length, dataset_scope)
    if scoped_count <= 0:
        return {}

    if dataset_scope == "static":
        start_index = 0
    else:
        start_index = dataset_length - scoped_count

    random_index = random.randint(start_index, start_index + scoped_count - 1)
    entry = dataset[random_index]

    answer = None
    for field in ("label", "text", "answer", "target"):
        if field in entry and entry[field] is not None:
            answer = str(entry[field])
            break
    if answer is None:
        return {}

    return {
        "index": random_index,
        "image": entry["image"],
        "answer": answer,
        "image_index": random_index,
    }
