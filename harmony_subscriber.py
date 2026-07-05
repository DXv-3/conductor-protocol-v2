"""
harmony_subscriber.py
---------------------
Harmony bus subscriber for conductor-protocol-v2.

Listens for three event types emitted by the stack:
  - skill_event    (from self-improving-system-builder via skill_brain_sync)
  - model_call     (from ConductorModelGateway and zai-wrap ModelRouter)
  - kg_patch       (from MATRIX harmony_publisher_base)

Each event type has a dedicated handler that writes structured data into
conductor's SQLite state store (or brain_integration if available) and
updates in-memory routing state so BrainSkillRouter gets fresh scores
without waiting for the TTL cache to expire.

Usage:
    # As a long-running subscriber (blocking)
    python harmony_subscriber.py

    # As an imported module (non-blocking, spawns background thread)
    from harmony_subscriber import start_subscriber
    start_subscriber()  # returns immediately; handles events in background
"""

import json
import logging
import os
import sqlite3
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("CONDUCTOR_DB", "conductor_state.db"))


# ---------------------------------------------------------------------------
# SQLite state store setup
# ---------------------------------------------------------------------------

def _init_db(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS harmony_events (
            event_id    TEXT PRIMARY KEY,
            event_type  TEXT NOT NULL,
            received_at TEXT NOT NULL,
            payload     TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS skill_scores (
            skill_name  TEXT PRIMARY KEY,
            avg_score   REAL NOT NULL DEFAULT 0.0,
            event_count INTEGER NOT NULL DEFAULT 0,
            last_updated TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS model_call_log (
            call_id     TEXT PRIMARY KEY,
            model       TEXT NOT NULL,
            provider    TEXT NOT NULL,
            task_type   TEXT NOT NULL,
            operator_id TEXT,
            latency_ms  REAL,
            success     INTEGER,
            timestamp   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS kg_patches (
            patch_id    TEXT PRIMARY KEY,
            node_type   TEXT,
            node_id     TEXT,
            received_at TEXT NOT NULL,
            payload     TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_harmony_events_type
            ON harmony_events(event_type);
        CREATE INDEX IF NOT EXISTS idx_model_call_log_model
            ON model_call_log(model);
        CREATE INDEX IF NOT EXISTS idx_skill_scores_score
            ON skill_scores(avg_score DESC);
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

def handle_skill_event(payload: Dict, conn: sqlite3.Connection):
    """
    Processes skill_event envelopes from self-improving-system-builder.
    Updates the skill_scores table with a rolling avg outcome_score so
    BrainSkillRouter always has fresh data without hitting the-brain KG.
    """
    event_id = payload.get("event_id", str(uuid.uuid4()))
    skill_name = payload.get("skill_name", "")
    outcome_score = float(payload.get("outcome_score", 0.0))
    received_at = datetime.now(timezone.utc).isoformat()

    try:
        # Upsert into harmony_events
        conn.execute(
            "INSERT OR REPLACE INTO harmony_events (event_id, event_type, received_at, payload) "
            "VALUES (?, ?, ?, ?)",
            (event_id, "skill_event", received_at, json.dumps(payload)),
        )

        # Update rolling skill score
        existing = conn.execute(
            "SELECT avg_score, event_count FROM skill_scores WHERE skill_name = ?",
            (skill_name,)
        ).fetchone()

        if existing:
            old_avg, count = existing
            new_count = count + 1
            # Exponential moving average (alpha=0.3) — recent events weighted more
            new_avg = 0.7 * old_avg + 0.3 * outcome_score
            conn.execute(
                "UPDATE skill_scores SET avg_score=?, event_count=?, last_updated=? "
                "WHERE skill_name=?",
                (new_avg, new_count, received_at, skill_name),
            )
        else:
            conn.execute(
                "INSERT INTO skill_scores (skill_name, avg_score, event_count, last_updated) "
                "VALUES (?, ?, 1, ?)",
                (skill_name, outcome_score, received_at),
            )

        conn.commit()
        logger.debug("handle_skill_event: updated skill '%s' score=%.3f", skill_name, outcome_score)

        # Invalidate BrainSkillRouter cache so next call gets fresh scores
        _invalidate_router_cache()

    except Exception as exc:
        logger.warning("handle_skill_event: DB write failed: %s", exc)


def handle_model_call(payload: Dict, conn: sqlite3.Connection):
    """
    Records model_call events from ConductorModelGateway and zai-wrap.
    Populates model_call_log for the dashboard and provenance queries.
    """
    call_id = payload.get("call_id", str(uuid.uuid4()))
    received_at = datetime.now(timezone.utc).isoformat()

    try:
        conn.execute(
            "INSERT OR REPLACE INTO harmony_events (event_id, event_type, received_at, payload) "
            "VALUES (?, ?, ?, ?)",
            (call_id + "_evt", "model_call", received_at, json.dumps(payload)),
        )
        conn.execute(
            "INSERT OR REPLACE INTO model_call_log "
            "(call_id, model, provider, task_type, operator_id, latency_ms, success, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                call_id,
                payload.get("model", ""),
                payload.get("provider", ""),
                payload.get("task_type", ""),
                payload.get("operator_id", ""),
                payload.get("latency_ms", 0.0),
                1 if payload.get("success", True) else 0,
                payload.get("timestamp", received_at),
            ),
        )
        conn.commit()
        logger.debug(
            "handle_model_call: logged call %s model=%s latency=%.0fms",
            call_id, payload.get("model", "?"), payload.get("latency_ms", 0)
        )
    except Exception as exc:
        logger.warning("handle_model_call: DB write failed: %s", exc)


def handle_kg_patch(payload: Dict, conn: sqlite3.Connection):
    """
    Records kg_patch events from MATRIX/PSF harmony_publisher_base.
    Stores the patch for replay and auditing; could trigger conductor
    re-routing if a KG node update affects an active operator.
    """
    patch_id = payload.get("patch_id", str(uuid.uuid4()))
    received_at = datetime.now(timezone.utc).isoformat()

    try:
        conn.execute(
            "INSERT OR REPLACE INTO harmony_events (event_id, event_type, received_at, payload) "
            "VALUES (?, ?, ?, ?)",
            (patch_id + "_evt", "kg_patch", received_at, json.dumps(payload)),
        )
        conn.execute(
            "INSERT OR REPLACE INTO kg_patches "
            "(patch_id, node_type, node_id, received_at, payload) VALUES (?, ?, ?, ?, ?)",
            (
                patch_id,
                payload.get("node_type", ""),
                payload.get("node_id", ""),
                received_at,
                json.dumps(payload),
            ),
        )
        conn.commit()
        logger.debug("handle_kg_patch: stored patch %s node=%s", patch_id, payload.get("node_id", "?"))
    except Exception as exc:
        logger.warning("handle_kg_patch: DB write failed: %s", exc)


# ---------------------------------------------------------------------------
# Router cache invalidation
# ---------------------------------------------------------------------------

def _invalidate_router_cache():
    """Force BrainSkillRouter to refresh its score cache on next call."""
    try:
        from operator_router.brain_skill_router import BrainSkillRouter
        # Access the module-level singleton if it exists
        import operator_router.brain_skill_router as bsr_mod
        if hasattr(bsr_mod, "_singleton") and bsr_mod._singleton is not None:
            bsr_mod._singleton._cache_ts = 0.0
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main dispatch loop
# ---------------------------------------------------------------------------

HANDLERS: Dict[str, Callable] = {
    "skill_event": handle_skill_event,
    "model_call":  handle_model_call,
    "kg_patch":    handle_kg_patch,
}


def _process_message(raw_message: str, conn: sqlite3.Connection):
    """Parse and dispatch a single harmony bus message."""
    try:
        msg = json.loads(raw_message)
    except json.JSONDecodeError as exc:
        logger.warning("harmony_subscriber: malformed message: %s", exc)
        return

    event_type = msg.get("event_type", msg.get("type", ""))
    payload = msg.get("payload", msg)  # some publishers wrap; some don't

    handler = HANDLERS.get(event_type)
    if handler:
        try:
            handler(payload, conn)
        except Exception as exc:
            logger.error("harmony_subscriber: handler %s raised: %s", event_type, exc)
    else:
        # Store unknown events anyway for observability
        try:
            conn.execute(
                "INSERT OR IGNORE INTO harmony_events (event_id, event_type, received_at, payload) "
                "VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), event_type, datetime.now(timezone.utc).isoformat(), json.dumps(payload)),
            )
            conn.commit()
        except Exception:
            pass
        logger.debug("harmony_subscriber: no handler for event_type='%s' — stored only", event_type)


def _subscriber_loop(stop_event: threading.Event):
    """Main loop: connects to harmony bus and dispatches messages."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    _init_db(conn)

    # Try to connect to the harmony bus (harmony-engine-protocol)
    harmony_host = os.getenv("HARMONY_HOST", "localhost")
    harmony_port = int(os.getenv("HARMONY_PORT", "7700"))

    bus = None
    try:
        matrix_path = os.getenv("MATRIX_PATH", "../MATRIX")
        sys.path.insert(0, matrix_path)
        from harmony_publisher_base import HarmonySubscriber  # type: ignore
        bus = HarmonySubscriber(host=harmony_host, port=harmony_port)
        logger.info("harmony_subscriber: connected to bus at %s:%d", harmony_host, harmony_port)
    except Exception as exc:
        logger.warning(
            "harmony_subscriber: could not connect to harmony bus (%s) — "
            "running in poll-file mode", exc
        )

    poll_file = Path(os.getenv("HARMONY_POLL_FILE", "/tmp/harmony_events.jsonl"))
    last_pos = 0

    while not stop_event.is_set():
        if bus:
            try:
                msg = bus.poll(timeout=1.0)
                if msg:
                    _process_message(msg, conn)
            except Exception as exc:
                logger.warning("harmony_subscriber: bus poll error: %s", exc)
                time.sleep(2.0)
        else:
            # Poll-file fallback: read new lines from a shared JSONL file
            try:
                if poll_file.exists():
                    with poll_file.open("r") as f:
                        f.seek(last_pos)
                        for line in f:
                            line = line.strip()
                            if line:
                                _process_message(line, conn)
                        last_pos = f.tell()
            except Exception as exc:
                logger.debug("harmony_subscriber: poll file error: %s", exc)
            time.sleep(0.5)

    conn.close()
    logger.info("harmony_subscriber: stopped")


_subscriber_thread: Optional[threading.Thread] = None
_stop_event: Optional[threading.Event] = None


def start_subscriber() -> threading.Thread:
    """Start the subscriber in a daemon background thread. Idempotent."""
    global _subscriber_thread, _stop_event
    if _subscriber_thread and _subscriber_thread.is_alive():
        return _subscriber_thread
    _stop_event = threading.Event()
    _subscriber_thread = threading.Thread(
        target=_subscriber_loop,
        args=(_stop_event,),
        name="harmony-subscriber",
        daemon=True,
    )
    _subscriber_thread.start()
    logger.info("harmony_subscriber: background thread started")
    return _subscriber_thread


def stop_subscriber():
    global _stop_event
    if _stop_event:
        _stop_event.set()


def get_local_skill_scores() -> Dict[str, float]:
    """
    Query conductor's local SQLite cache for skill scores.
    Used by BrainSkillRouter as a fast local alternative to hitting the-brain KG.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        rows = conn.execute(
            "SELECT skill_name, avg_score FROM skill_scores ORDER BY avg_score DESC"
        ).fetchall()
        conn.close()
        return {row[0]: row[1] for row in rows}
    except Exception as exc:
        logger.warning("get_local_skill_scores: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("harmony_subscriber: starting in blocking mode")
    logger.info("  DB:           %s", DB_PATH)
    logger.info("  Harmony host: %s:%s", os.getenv('HARMONY_HOST','localhost'), os.getenv('HARMONY_PORT','7700'))
    logger.info("  Poll file:    %s", os.getenv('HARMONY_POLL_FILE','/tmp/harmony_events.jsonl'))

    stop = threading.Event()
    try:
        _subscriber_loop(stop)
    except KeyboardInterrupt:
        logger.info("harmony_subscriber: interrupted by user")
