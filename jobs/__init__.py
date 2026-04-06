"""Lazy exports for job entry points."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["start_job", "start_fix_article"]


def _load_mps() -> Any:
    return import_module("jobs.mps")


def start_job(*args, **kwargs):
    return _load_mps().start_job(*args, **kwargs)


def start_fix_article(*args, **kwargs):
    return _load_mps().start_fix_article(*args, **kwargs)
