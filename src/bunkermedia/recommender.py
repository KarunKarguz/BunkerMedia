from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from bunkermedia.database import Database
from bunkermedia.intelligence import cosine_similarity, parse_embedding
from bunkermedia.models import Recommendation


class RecommendationEngine:
    KIDS_BLOCK_KEYWORDS = {
        "kill",
        "killing",
        "murder",
        "violent",
        "violence",
        "gore",
        "blood",
        "horror",
        "terror",
        "nsfw",
        "adult",
        "explicit",
        "weapon",
        "war",
        "crime",
        "drugs",
    }

    def __init__(self, db: Database, logger: Any) -> None:
        self.db = db
        self.logger = logger

    async def refresh_scores(self, profile_id: str = Database.DEFAULT_PROFILE_ID) -> None:
        self._refresh_scores_sync(profile_id=profile_id)

    async def recommend(
        self,
        limit: int = 20,
        explain: bool = False,
        profile_id: str = Database.DEFAULT_PROFILE_ID,
        is_kids: bool = False,
        can_access_private: bool = True,
    ) -> list[Recommendation]:
        return self._recommend_sync(
            limit,
            explain,
            profile_id=profile_id,
            is_kids=is_kids,
            can_access_private=can_access_private,
        )

    def _refresh_scores_sync(self, profile_id: str = Database.DEFAULT_PROFILE_ID) -> None:
        prefs = self.db.get_preferences("channel", profile_id=profile_id)
        watch_signal = self.db.fetch_history_signal(profile_id=profile_id)
        candidates = self.db.get_recommendation_candidates(profile_id=profile_id, limit=3000)

        for item in candidates:
            channel_key = str(item.get("channel") or "").lower()
            channel_pref = float(prefs.get(channel_key, 0.0))
            history_score = float(watch_signal.get(str(item["video_id"]), 0.0))
            self.db.update_video_signals(str(item["video_id"]), channel_pref, history_score)

        self.logger.info("Recommendation features refreshed count=%d", len(candidates))

    def _recommend_sync(
        self,
        limit: int,
        explain: bool,
        profile_id: str,
        is_kids: bool,
        can_access_private: bool,
    ) -> list[Recommendation]:
        limit = max(1, limit)
        prefs = self.db.get_preferences("channel", profile_id=profile_id)
        watch_signal = self.db.fetch_history_signal(profile_id=profile_id)
        profile_vector, profile_size = self._build_profile_vector(profile_id=profile_id)
        candidates = self.db.get_recommendation_candidates(profile_id=profile_id, limit=max(limit * 8, 4000))

        scored: list[dict[str, Any]] = []
        for item in candidates:
            privacy_level = str(item.get("privacy_level") or "standard").lower()
            if privacy_level in {"private", "explicit"} and not can_access_private:
                continue
            if is_kids and not self._is_kids_safe(item):
                continue
            video_id = str(item["video_id"])
            channel = str(item.get("channel") or "Unknown")
            channel_pref = float(prefs.get(channel.lower(), 0.0))
            history_score = float(watch_signal.get(video_id, 0.0))
            trending_score = float(item.get("trending_score") or 0.0)
            recency_score = self._compute_recency_score(item.get("upload_date"))
            feedback_score = self._feedback_score(item)
            quality_score = float(item.get("intelligence_quality") or 0.0)

            embedding = parse_embedding(str(item.get("embedding_json") or ""))
            semantic_score = 0.0
            if profile_vector and embedding and len(profile_vector) == len(embedding):
                semantic_score = cosine_similarity(profile_vector, embedding) * quality_score

            base_score = (
                (0.24 * self._clamp(trending_score, -2.0, 2.0))
                + (0.18 * self._clamp(channel_pref, -2.0, 2.0))
                + (0.16 * self._clamp(history_score, -2.0, 2.0))
                + (0.28 * self._clamp(semantic_score, -1.0, 1.0))
                + (0.08 * feedback_score)
                + (0.06 * recency_score)
            )

            watched = int(item.get("watched") or 0)
            if watched:
                base_score -= 0.2
            if item.get("rejected_reason"):
                base_score -= 5.0

            scored.append(
                {
                    "video_id": video_id,
                    "title": str(item.get("title") or "Untitled"),
                    "channel": channel,
                    "downloaded": bool(item.get("downloaded")),
                    "local_path": item.get("local_path"),
                    "embedding": embedding,
                    "base_score": base_score,
                    "components": {
                        "trending": round(trending_score, 4),
                        "channel_preference": round(channel_pref, 4),
                        "watch_history": round(history_score, 4),
                        "semantic_similarity": round(semantic_score, 4),
                        "feedback": round(feedback_score, 4),
                        "recency": round(recency_score, 4),
                        "already_watched_penalty": -0.2 if watched else 0.0,
                        "profile_seed_count": profile_size,
                        "transcript_source": str(item.get("transcript_source") or "none"),
                    },
                }
            )

        ranked = self._diversity_rerank(scored, limit)
        recommendations: list[Recommendation] = []
        for rec in ranked:
            explanation: dict[str, Any] | None = None
            if explain:
                explanation = {
                    "base_score": round(float(rec["base_score"]), 4),
                    "diversity_adjustment": round(float(rec.get("diversity_adjustment", 0.0)), 4),
                    "final_score": round(float(rec["final_score"]), 4),
                    "components": rec["components"],
                }

            recommendations.append(
                Recommendation(
                    video_id=rec["video_id"],
                    title=rec["title"],
                    channel=rec["channel"],
                    score=float(rec["final_score"]),
                    downloaded=bool(rec["downloaded"]),
                    local_path=rec.get("local_path"),
                    explanation=explanation,
                )
            )

        return recommendations

    def _build_profile_vector(self, profile_id: str = Database.DEFAULT_PROFILE_ID) -> tuple[list[float], int]:
        seeds = self.db.get_profile_embedding_seeds(profile_id=profile_id, limit=1200)
        accumulator: list[float] = []
        seed_count = 0

        for seed in seeds:
            embedding = parse_embedding(str(seed.get("embedding_json") or ""))
            if not embedding:
                continue
            if not accumulator:
                accumulator = [0.0] * len(embedding)
            if len(embedding) != len(accumulator):
                continue

            weight = 0.0
            if int(seed.get("liked") or 0) == 1:
                weight += 1.2
            if int(seed.get("disliked") or 0) == 1:
                weight -= 1.4
            if int(seed.get("watched") or 0) == 1:
                weight += 0.1
            if int(seed.get("completed") or 0) == 1:
                weight += 0.25

            rating = float(seed.get("rating") or 0.0)
            if rating > 0:
                weight += (rating - 2.5) / 2.5 * 0.4

            if abs(weight) < 1e-6:
                continue

            for idx, value in enumerate(embedding):
                accumulator[idx] += weight * value
            seed_count += 1

        if not accumulator:
            return [], 0

        norm = math.sqrt(sum(value * value for value in accumulator))
        if norm <= 1e-9:
            return [], seed_count

        vector = [value / norm for value in accumulator]
        return vector, seed_count

    def _diversity_rerank(self, scored: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        channel_counts: dict[str, int] = {}
        selected: list[dict[str, Any]] = []
        pool = sorted(scored, key=lambda item: float(item["base_score"]), reverse=True)

        diversity_penalty_weight = 0.18
        novelty_bonus_weight = 0.07

        while pool and len(selected) < limit:
            best_idx = 0
            best_adjusted = float("-inf")
            best_adjustment = 0.0

            for idx, item in enumerate(pool):
                channel_key = item["channel"].lower()
                channel_penalty = diversity_penalty_weight * channel_counts.get(channel_key, 0)

                novelty_bonus = 0.0
                current_embedding = item.get("embedding") or []
                if selected and current_embedding:
                    max_similarity = max(
                        cosine_similarity(current_embedding, selected_item.get("embedding") or [])
                        for selected_item in selected
                    )
                    novelty_bonus = novelty_bonus_weight * max(0.0, 1.0 - max_similarity)

                adjusted = float(item["base_score"]) - channel_penalty + novelty_bonus
                if adjusted > best_adjusted:
                    best_adjusted = adjusted
                    best_idx = idx
                    best_adjustment = -channel_penalty + novelty_bonus

            chosen = pool.pop(best_idx)
            chosen["diversity_adjustment"] = best_adjustment
            chosen["final_score"] = float(chosen["base_score"]) + best_adjustment
            selected.append(chosen)
            channel_key = chosen["channel"].lower()
            channel_counts[channel_key] = channel_counts.get(channel_key, 0) + 1

        return selected

    @staticmethod
    def _feedback_score(item: dict[str, Any]) -> float:
        if int(item.get("liked") or 0) == 1:
            return 1.0
        if int(item.get("disliked") or 0) == 1:
            return -1.5
        return float(item.get("rating") or 0.0) / 5.0

    @staticmethod
    def _compute_recency_score(upload_date: Any) -> float:
        raw = str(upload_date or "").strip()
        if len(raw) != 8 or not raw.isdigit():
            return 0.0
        try:
            dt = datetime.strptime(raw, "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return 0.0

        days_old = (datetime.now(timezone.utc) - dt).days
        if days_old <= 7:
            return 1.0
        if days_old <= 30:
            return 0.75
        if days_old <= 90:
            return 0.4
        if days_old <= 365:
            return 0.2
        return 0.05

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _is_kids_safe(self, item: dict[str, Any]) -> bool:
        text = " ".join(
            [
                str(item.get("title") or ""),
                str(item.get("channel") or ""),
                str(item.get("source_url") or ""),
                str(item.get("rejected_reason") or ""),
            ]
        ).lower()
        return not any(keyword in text for keyword in self.KIDS_BLOCK_KEYWORDS)
