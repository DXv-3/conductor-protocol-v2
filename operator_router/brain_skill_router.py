"""
operator_router/brain_skill_router.py
--------------------------------------
Enriches the conductor's operator_router with real-time skill scores
from the-brain KG, so task routing decisions are weighted by empirical
performance history rather than static config.

This module sits BETWEEN the incoming task and the operator_router.router:

    task arrives
        ↓
    BrainSkillRouter.enrich_route_context(task)   ←─ reads the-brain
        ↓
    operator_router.router.route(task, context)    ←─ normal routing
        ↓
    ConductorModelGateway.call(prompt, task_type)  ←─ GATEWAY-01
        ↓
    result → back to caller

Usage:
    from operator_router.brain_skill_router import BrainSkillRouter
    bsr = BrainSkillRouter()
    context = bsr.enrich_route_context(task_dict)
    # context now has: best_skill, skill_score, skill_history_summary,
    #                  recommended_task_type, recommended_model
"""

import logging
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class BrainSkillRouter:
    """
    Reads skill performance data from the-brain (via skill_brain_sync)
    and surfaces routing recommendations to the conductor.
    """

    # Map conductor task categories → ModelRouter task_type
    CATEGORY_TO_TASK_TYPE: Dict[str, str] = {
        "code_generation":   "code",
        "code_review":       "code",
        "reasoning":         "reasoning",
        "analysis":          "reasoning",
        "summarization":     "fast",
        "classification":    "fast",
        "creative_writing":  "creative",
        "image_description": "vision",
        "audit":             "audit",
        "forensics":         "forensics",
        "routing":           "routing",
    }

    def __init__(self):
        self._sync = None
        self._sync_available = False
        self._score_cache: Dict[str, float] = {}
        self._cache_ts: float = 0.0
        self._cache_ttl: float = float(os.getenv("BRAIN_SKILL_CACHE_TTL", "60"))  # seconds
        self._init_sync()

    def _init_sync(self):
        sis_path = os.getenv("SIS_PATH", "../self-improving-system-builder")
        sys.path.insert(0, sis_path)
        try:
            import skill_brain_sync as sbs  # noqa
            self._sync = sbs
            self._sync_available = True
            logger.info("BrainSkillRouter: skill_brain_sync connected from %s", sis_path)
        except ImportError:
            logger.warning(
                "BrainSkillRouter: skill_brain_sync not found at %s — "
                "routing will use static config only", sis_path
            )
        except Exception as exc:
            logger.warning("BrainSkillRouter: init failed: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enrich_route_context(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Given a conductor task dict, return an enriched context dict with:
          - best_skill: str           — highest-scoring skill for this task category
          - skill_score: float        — its avg outcome score from the-brain
          - skill_history_summary: str — last 3 events as a one-liner for prompt injection
          - recommended_task_type: str — ModelRouter task_type string
          - recommended_model: str    — suggested primary model
          - all_skill_scores: dict    — full {skill: score} map for dashboard
        """
        context: Dict[str, Any] = {
            "best_skill": "",
            "skill_score": 0.0,
            "skill_history_summary": "",
            "recommended_task_type": "reasoning",
            "recommended_model": "claude/claude-sonnet-4-5",
            "all_skill_scores": {},
        }

        category = task.get("category", task.get("task_type", "reasoning"))
        context["recommended_task_type"] = self.CATEGORY_TO_TASK_TYPE.get(category, "reasoning")

        if not self._sync_available:
            return context

        try:
            # Skill scores (cached)
            scores = self._get_cached_scores()
            context["all_skill_scores"] = scores

            # Find best skill for this category
            candidate_skills = task.get("candidate_skills", [])
            if not candidate_skills:
                # Derive candidates from scores that match category keywords
                candidate_skills = [
                    s for s in scores
                    if category.split("_")[0] in s.lower() or s.lower() in category
                ]

            if candidate_skills:
                best = max(candidate_skills, key=lambda s: scores.get(s, 0.0))
                context["best_skill"] = best
                context["skill_score"] = scores.get(best, 0.0)

                # Pull history for prompt context
                history = self._sync.get_skill_history(best, limit=3)
                if history:
                    lines = [
                        f"{h.get('event_type','?')} v{h.get('skill_version',1)} "
                        f"score={h.get('outcome_score',0):.2f}: {h.get('delta_summary','')[:80]}"
                        for h in history
                    ]
                    context["skill_history_summary"] = " | ".join(lines)

            # Recommend model based on top-scoring task type
            context["recommended_model"] = self._recommend_model(
                context["recommended_task_type"], context["skill_score"]
            )

        except Exception as exc:
            logger.warning("BrainSkillRouter.enrich_route_context failed: %s", exc)

        return context

    def get_skill_scores(self) -> Dict[str, float]:
        """Return the current skill score map (cached)."""
        return self._get_cached_scores()

    def recommend_task_type(self, category: str) -> str:
        return self.CATEGORY_TO_TASK_TYPE.get(category, "reasoning")

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _get_cached_scores(self) -> Dict[str, float]:
        import time
        now = time.time()
        if now - self._cache_ts > self._cache_ttl:
            try:
                self._score_cache = self._sync.get_all_skill_scores()
                self._cache_ts = now
                logger.debug(
                    "BrainSkillRouter: refreshed skill score cache (%d skills)",
                    len(self._score_cache)
                )
            except Exception as exc:
                logger.warning("BrainSkillRouter: score cache refresh failed: %s", exc)
        return self._score_cache

    def _recommend_model(self, task_type: str, skill_score: float) -> str:
        """
        High-scoring skills get the more capable (and expensive) primary model.
        Low-scoring skills get a cheaper fast model to conserve budget during
        improvement cycles.
        """
        from operator_router.model_gateway_adapter import ConductorModelGateway
        defaults = ConductorModelGateway.TASK_DEFAULTS
        primary, fallback = defaults.get(task_type, ("claude/claude-sonnet-4-5", "deepseek/deepseek-chat"))
        # Below 0.5 score → use fallback (cheaper) model; above → use primary
        return primary if skill_score >= 0.5 else fallback
