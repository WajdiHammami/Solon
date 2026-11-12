"""Small, dependency-free statistics for the evaluation."""

import math
import random
from collections.abc import Callable, Sequence


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else math.nan


def rankdata(values: Sequence[float]) -> list[float]:
    """1-based ranks; ties get the average of the ranks they span."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def pearson(x: Sequence[float], y: Sequence[float]) -> float:
    if len(x) != len(y) or len(x) < 2:
        return math.nan
    mx, my = mean(x), mean(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx == 0 or syy == 0:
        return math.nan  # a constant series has no correlation
    return sxy / math.sqrt(sxx * syy)


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    return pearson(rankdata(x), rankdata(y))


def bootstrap_ci(
    statistic: Callable[[list], float],
    items: Sequence,
    samples: int,
    seed: int,
    level: float = 0.95,
) -> tuple[float, float]:
    """Percentile bootstrap CI of ``statistic`` over resamples of ``items``."""
    if len(items) < 2:
        return (math.nan, math.nan)
    rng = random.Random(seed)
    values = []
    for _ in range(samples):
        resample = [items[rng.randrange(len(items))] for _ in items]
        value = statistic(resample)
        if not math.isnan(value):
            values.append(value)
    if not values:
        return (math.nan, math.nan)
    values.sort()
    lo = values[int((1 - level) / 2 * (len(values) - 1))]
    hi = values[int((1 + level) / 2 * (len(values) - 1))]
    return (lo, hi)


def to_class(value: float) -> int:
    """Round a mean lean to the nearest of the five classes (-2..2)."""
    return max(-2, min(2, int(math.floor(value + 0.5))))


def agreement(predicted: Sequence[int], actual: Sequence[int]) -> dict[str, float]:
    if not actual:
        return {"exact": math.nan, "within_one": math.nan, "n": 0}
    exact = sum(p == a for p, a in zip(predicted, actual)) / len(actual)
    within = sum(abs(p - a) <= 1 for p, a in zip(predicted, actual)) / len(actual)
    return {"exact": exact, "within_one": within, "n": len(actual)}


def random_baseline(actual: Sequence[int]) -> dict[str, float]:
    """Expected agreement of a uniformly random 5-class guess."""
    if not actual:
        return {"exact": math.nan, "within_one": math.nan, "n": 0}
    within = mean([sum(abs(c - a) <= 1 for c in range(-2, 3)) / 5 for a in actual])
    return {"exact": 0.2, "within_one": within, "n": len(actual)}


def confusion(predicted: Sequence[int], actual: Sequence[int]) -> list[list[int]]:
    """5x5 counts; rows = actual (-2..2), columns = predicted (-2..2)."""
    matrix = [[0] * 5 for _ in range(5)]
    for p, a in zip(predicted, actual):
        matrix[a + 2][p + 2] += 1
    return matrix
