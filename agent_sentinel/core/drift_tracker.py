"""
Drift Tracker — watches an agent's stated sub-goals across a session and
flags gradual goal drift.
"""

from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from agent_sentinel.core.types import Action, Verdict, VerdictType


class DriftTracker:
    def __init__(
        self, embedding_model: str = "all-MiniLM-L6-v2", drift_threshold: float = 0.5
    ):
        self.drift_threshold = drift_threshold
        self._embedder = SentenceTransformer(embedding_model)
        # session_id -> {"original": np.ndarray, "recent": list[np.ndarray]}
        self._session_history: dict[str, dict] = {}

    def check(self, action: Action) -> Verdict:
        session_id = action.session_id
        original_task = action.context.get("original_task", "")
        current_subgoal = action.context.get("current_subgoal", original_task)

        if not original_task:
            # Nothing to compare against — allow, nothing to check.
            return Verdict(
                action_id=action.action_id,
                verdict=VerdictType.ALLOW,
                reason="No original_task in context; drift check skipped.",
                layer="drift_tracker",
            )

        if session_id not in self._session_history:
            self._session_history[session_id] = {
                "original": self._embed(original_task),
                "recent": [],
            }

        current_embedding = self._embed(current_subgoal)
        original_embedding = self._session_history[session_id]["original"]

        similarity = self._cosine_similarity(current_embedding, original_embedding)
        self._session_history[session_id]["recent"].append(current_embedding)

        if similarity < self.drift_threshold:
            return Verdict(
                action_id=action.action_id,
                verdict=VerdictType.FLAG,
                reason=(
                    f"Stated sub-goal has drifted from original task "
                    f"(similarity={similarity:.2f}, threshold={self.drift_threshold})."
                ),
                layer="drift_tracker",
            )

        return Verdict(
            action_id=action.action_id,
            verdict=VerdictType.ALLOW,
            reason=f"Sub-goal consistent with original task (similarity={similarity:.2f}).",
            layer="drift_tracker",
        )

    def _embed(self, text: str) -> np.ndarray:
        return self._embedder.encode(text)

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def reset_session(self, session_id: str) -> None:
        self._session_history.pop(session_id, None)
