from __future__ import annotations

from pathlib import Path
from typing import Iterable

import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from behavior_engine import choose_message_length_category


class _StubRandom:
    def __init__(self, values: Iterable[float]):
        self._values = iter(values)

    def random(self) -> float:
        return next(self._values)


def test_choose_message_length_category_respects_distribution():
    profile = {"short": 0.2, "medium": 0.3, "long": 0.5}
    rng = _StubRandom([0.1, 0.35, 0.95])

    assert choose_message_length_category(profile, rng=rng) == "short"
    assert choose_message_length_category(profile, rng=rng) == "medium"
    assert choose_message_length_category(profile, rng=rng) == "long"
