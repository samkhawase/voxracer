"""Interval operations used by the timing analysis."""

from __future__ import annotations

from collections.abc import Iterable

Interval = tuple[int, int]


def merge_intervals(intervals: Iterable[Interval]) -> list[Interval]:
    ordered = sorted((start, end) for start, end in intervals if end > start)
    merged: list[Interval] = []
    for start, end in ordered:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def union_duration_ns(intervals: Iterable[Interval]) -> int:
    return sum(end - start for start, end in merge_intervals(intervals))


def clip(interval: Interval, window: Interval) -> Interval | None:
    start = max(interval[0], window[0])
    end = min(interval[1], window[1])
    return (start, end) if end > start else None
