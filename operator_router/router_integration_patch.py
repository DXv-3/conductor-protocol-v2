#!/usr/bin/env python3
"""router_integration_patch.py — The final wire.

Two usage modes:

MODE A — wrap_router() decorator (zero changes to router.py):
    from router_integration_patch import wrap_router
    inspect_and_route = wrap_router(inspect_and_route)

MODE B — manual patch (paste into inspect_and_route top):
    from conductor_adapter import call_model
    from brain_query_before_route import query_before_route, apply_routing_adjustment
    adjustment = query_before_route(task_config)
    if adjustment.is_blocking:
        return {"blocked": True, "reason": adjustment.reason,
                "evidence": adjustment.evidence, "recommendation": adjustment.recommendation}
    task_config = apply_routing_adjustment(task_config, adjustment)
"""
from __future__ import annotations

import functools
import sys
from pathlib import Path
from typing import Callable

for _p in [
    Path(__file__).parent.parent.parent / "zai-wrap",
    Path(__file__).parent.parent,
]:
    if _p.exists():
        sys.path.insert(0, str(_p))

try:
    from conductor_adapter import call_model, ModelCallResult
    _CONDUCTOR_ADAPTER = True
except ImportError:
    _CONDUCTOR_ADAPTER = False

try:
    from brain_query_before_route import query_before_route, apply_routing_adjustment
    _BRAIN_QUERY = True
except ImportError:
    _BRAIN_QUERY = False


def wrap_router(inspect_and_route_fn: Callable) -> Callable:
    """Wrap inspect_and_route() with brain pre-route query.

    1. Queries brain for prior failure patterns BEFORE routing
    2. Returns blocked dict if hard_block threshold met
    3. Adjusts task_config model if adjust_model threshold met
    4. Calls original function with (possibly adjusted) task_config

    Brain failure never blocks routing — exception is caught and logged.
    """
    @functools.wraps(inspect_and_route_fn)
    def _wrapped(task_config: dict, *args, **kwargs) -> dict:
        if _BRAIN_QUERY:
            try:
                adjustment = query_before_route(task_config)
                if adjustment.is_blocking:
                    return {
                        "blocked": True,
                        "reason": adjustment.reason,
                        "evidence": adjustment.evidence,
                        "recommendation": adjustment.recommendation,
                        "task_config": task_config,
                    }
                task_config = apply_routing_adjustment(task_config, adjustment)
            except Exception as e:
                print(f"[router_patch] pre-route query failed (continuing): {e}")

        return inspect_and_route_fn(task_config, *args, **kwargs)

    return _wrapped


def patched_call_model(
    model: str,
    prompt: str,
    system: str = "",
    max_tokens: int = 1024,
    run_id: str = "",
) -> dict:
    """call_model() returning a plain dict for routers that expect dict results."""
    if not _CONDUCTOR_ADAPTER:
        raise ImportError("conductor_adapter not available — ensure zai-wrap is in path")
    result = call_model(model=model, prompt=prompt, system=system,
                        max_tokens=max_tokens, run_id=run_id)
    return {
        "success": result.success,
        "content": result.content,
        "error": result.error,
        "model_used": result.model_used,
        "backend": result.backend,
        "latency_ms": result.latency_ms,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
    }
