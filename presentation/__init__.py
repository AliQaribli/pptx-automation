"""Offline, deterministic PPTX fallback engine.

Public API::

    from presentation import Contract, render
    contract = Contract.from_json("brief.json")
    deck = render(contract, "output/demo")
"""
from __future__ import annotations

from pathlib import Path

from .contract import Contract, ContractError
from .render_pptx import render
from . import qa

__all__ = ["Contract", "ContractError", "render", "qa"]
