"""Centralized logging configuration. Call ``setup_logging()`` once at process startup."""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())

    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level.upper())
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
