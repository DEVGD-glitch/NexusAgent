"""
L5 Identity Memory — User profile, preferences, and persona model.

Stores deep knowledge about the user: preferences, communication style,
domain expertise, goals, and interaction history. This enables NEXUS
to personalize its behavior and build a long-term relationship.

Inspired by APEX's Honcho-style dialectic user modeling and
GenericAgent's meta-rules layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from nexus.memory.chroma_service import NexusMemoryService

logger = logging.getLogger(__name__)


@dataclass
class UserProfile:
    """A user's identity profile."""
    user_id: str
    display_name: str = ""
    language_preference: Optional[str] = None
    communication_style: str = "professional"  # professional, casual, technical, concise
    domain_expertise: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)
    preferences: dict[str, Any] = field(default_factory=dict)
    interaction_count: int = 0
    last_interaction: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_text(self) -> str:
        """Convert profile to searchable text."""
        parts = [
            f"User: {self.display_name or self.user_id}",
            f"Language: {self.language_preference}",
            f"Style: {self.communication_style}",
        ]
        if self.domain_expertise:
            parts.append(f"Expertise: {', '.join(self.domain_expertise)}")
        if self.goals:
            parts.append(f"Goals: {'; '.join(self.goals)}")
        if self.preferences:
            pref_items = [f"{k}={v}" for k, v in self.preferences.items()]
            parts.append(f"Preferences: {', '.join(pref_items)}")
        return "\n".join(parts)

    def to_metadata(self) -> dict[str, Any]:
        """Convert profile to ChromaDB-compatible metadata."""
        return {
            "user_id": self.user_id,
            "display_name": self.display_name,
            "language_preference": self.language_preference,
            "communication_style": self.communication_style,
            "domain_expertise": ",".join(self.domain_expertise),
            "goals_count": str(len(self.goals)),
            "interaction_count": str(self.interaction_count),
            "last_interaction": self.last_interaction,
            "source": "identity",
        }


class IdentityMemory:
    """
    L5 Identity Memory — manages user profiles and preferences.

    Stores one profile per user (identified by user_id) in the
    'identity' ChromaDB namespace. Updates incrementally as
    interactions reveal new preferences or information.

    Usage:
        identity = IdentityMemory(memory_service)
        await identity.update_profile(UserProfile(
            user_id="user_001",
            display_name="Alice",
            language_preference="fr",
            domain_expertise=["machine learning", "python"],
        ))
        profile = await identity.get_profile("user_001")
    """

    def __init__(self, memory_service: NexusMemoryService):
        self.memory = memory_service

    async def create_or_update_profile(self, profile: UserProfile) -> str:
        """
        Create or update a user profile.

        If a profile already exists for this user_id, it is merged
        with the new data (new values override existing ones).

        Args:
            profile: The UserProfile to store.

        Returns:
            Document ID.
        """
        existing = await self.get_profile(profile.user_id)
        if existing:
            # Merge: update existing profile with new values
            existing_meta = existing.get("metadata", {})
            merged = UserProfile(
                user_id=profile.user_id,
                display_name=profile.display_name or existing_meta.get("display_name", ""),
                language_preference=profile.language_preference if profile.language_preference is not None else existing_meta.get("language_preference", "en"),
                communication_style=profile.communication_style if profile.communication_style != "professional" else existing_meta.get("communication_style", "professional"),
                domain_expertise=list(set(
                    profile.domain_expertise + [x for x in existing_meta.get("domain_expertise", "").split(",") if x]
                )) if profile.domain_expertise or existing_meta.get("domain_expertise") else [],
                goals=list(set(
                    profile.goals + (existing_meta.get("goals", []) or [])
                )),
                preferences={**existing_meta.get("preferences", {}), **profile.preferences},
                interaction_count=int(existing_meta.get("interaction_count", "0")) + 1,
            )
            doc_id = existing["id"]
            await self.memory.update(
                doc_id=doc_id,
                text=merged.to_text(),
                metadata=merged.to_metadata(),
                namespace="identity",
            )
            logger.info("Updated identity profile for user '%s'", profile.user_id)
            return doc_id

        doc_id = await self.memory.store(
            text=profile.to_text(),
            metadata=profile.to_metadata(),
            namespace="identity",
            doc_id=f"identity_{profile.user_id}",
        )
        logger.info("Created identity profile for user '%s'", profile.user_id)
        return doc_id

    async def get_profile(self, user_id: str) -> Optional[dict[str, Any]]:
        """
        Get a user's profile.

        Args:
            user_id: The user identifier.

        Returns:
            Profile dict or None if not found.
        """
        results = await self.memory.search(
            query=f"User profile for {user_id}",
            namespace="identity",
            top_k=5,
            where={"user_id": user_id},
        )
        ids = results.get("ids", [[]])[0]
        if not ids:
            return None

        return {
            "id": ids[0],
            "text": results["documents"][0][0] if results.get("documents") else "",
            "metadata": results["metadatas"][0][0] if results.get("metadatas") else {},
        }

    async def record_preference(
        self,
        user_id: str,
        key: str,
        value: str,
    ) -> bool:
        """
        Record a single preference for a user.

        Args:
            user_id: User identifier.
            key: Preference key (e.g., "theme", "default_model").
            value: Preference value.

        Returns:
            True if the preference was recorded.
        """
        profile_data = await self.get_profile(user_id)
        if profile_data:
            prefs_str = profile_data.get("metadata", {}).get("preferences", "{}")
            try:
                prefs = json.loads(prefs_str) if isinstance(prefs_str, str) else prefs_str
            except (json.JSONDecodeError, TypeError):
                prefs = {}
            prefs[key] = value
            await self.memory.update(
                doc_id=profile_data["id"],
                metadata={"preferences": json.dumps(prefs)},
                namespace="identity",
            )
            return True
        else:
            profile = UserProfile(
                user_id=user_id,
                preferences={key: value},
            )
            await self.create_or_update_profile(profile)
            return True

    async def get_stats(self) -> dict[str, Any]:
        """Get identity memory statistics."""
        total = await self.memory.count(namespace="identity")
        return {
            "total_profiles": total,
            "namespace": "identity",
        }


# JSON import at module level
import json
