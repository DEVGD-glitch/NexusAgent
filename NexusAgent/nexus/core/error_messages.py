"""
NEXUS Error Messages — Human-friendly error message mapping.

Transforms technical exceptions into clear, actionable messages
that non-developers can understand.
"""

from __future__ import annotations

from typing import Optional


class HumanError:
    """A human-friendly error with a clear message and suggested action."""

    def __init__(self, message: str, action: str = "", technical: str = ""):
        self.message = message
        self.action = action
        self.technical = technical

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "action": self.action,
            "technical": self.technical,
        }


# ── Error Mapping ──────────────────────────────────────────────────

ERROR_MAP: dict[str, HumanError] = {
    # LLM Errors
    "LLMAllProvidersFailedError": HumanError(
        message="Aucun fournisseur LLM n'est disponible.",
        action="Configure au moins une clé API dans Settings, ou lance Ollama localement.",
    ),
    "LLMProviderError": HumanError(
        message="Le fournisseur LLM a rencontré une erreur.",
        action="Vérifie ta clé API dans Settings, ou essaie un autre fournisseur.",
    ),
    "LLMRateLimitError": HumanError(
        message="Limite de requêtes atteinte pour ce fournisseur.",
        action="Attends quelques secondes, ou bascule vers un autre fournisseur.",
    ),
    "LLMError": HumanError(
        message="Erreur LLM.",
        action="Vérifie ta configuration dans Settings.",
    ),

    # Memory Errors
    "MemoryNamespaceError": HumanError(
        message="Namespace mémoire invalide.",
        action="Utilise un namespace existant : conversations, episodes, knowledge, skills, identity, code.",
    ),
    "MemorySearchError": HumanError(
        message="Impossible de rechercher en mémoire.",
        action="ChromaDB est peut-être indisponible. Redémarre NEXUS.",
    ),
    "MemoryStoreError": HumanError(
        message="Impossible de stocker en mémoire.",
        action="Vérifie que le répertoire de données est accessible.",
    ),

    # Sandbox Errors
    "SandboxError": HumanError(
        message="L'exécution du code a échoué.",
        action="Vérifie ton code et essaie à nouveau.",
    ),

    # MCP Errors
    "MCPToolError": HumanError(
        message="L'outil MCP a échoué.",
        action="Vérifie les paramètres et réessaie.",
    ),

    # Orchestrator Errors
    "MaxIterationsError": HumanError(
        message="L'agent a atteint la limite d'itérations.",
        action="La tâche est peut-être trop complexe. Essaie de la décomposer.",
    ),
    "OrchestratorError": HumanError(
        message="L'orchestrateur a rencontré une erreur.",
        action="Essaie de reformuler ta tâche.",
    ),
}


def get_human_error(exc: Exception) -> HumanError:
    """
    Transform a technical exception into a human-friendly error.

    Args:
        exc: The original exception.

    Returns:
        HumanError with clear message and suggested action.
    """
    # Try exact match first, then MRO-based match
    exc_type = type(exc).__name__
    if exc_type not in ERROR_MAP:
        # Walk the MRO to find a parent class match
        for cls in type(exc).__mro__[1:]:
            if cls.__name__ in ERROR_MAP:
                exc_type = cls.__name__
                break

    # Direct mapping
    if exc_type in ERROR_MAP:
        import copy
        human = copy.deepcopy(ERROR_MAP[exc_type])
        human.technical = str(exc)
        return human

    # Pattern-based matching
    exc_str = str(exc).lower()

    if "connection" in exc_str or "refused" in exc_str:
        return HumanError(
            message="Impossible de se connecter au serveur.",
            action="Vérifie que NEXUS est en cours d'exécution et que le port est correct.",
            technical=str(exc),
        )

    if "timeout" in exc_str or "timed out" in exc_str:
        return HumanError(
            message="L'opération a pris trop de temps.",
            action="Essaie une tâche plus simple, ou augmente le timeout dans Settings.",
            technical=str(exc),
        )

    if "api key" in exc_str or "unauthorized" in exc_str or "401" in exc_str:
        return HumanError(
            message="Clé API invalide ou manquante.",
            action="Vérifie ta clé API dans Settings.",
            technical=str(exc),
        )

    if "rate" in exc_str or "429" in exc_str:
        return HumanError(
            message="Trop de requêtes. Limite atteinte.",
            action="Attends quelques secondes avant de réessayer.",
            technical=str(exc),
        )

    if "import" in exc_str or "module" in exc_str or "no module named" in exc_str:
        return HumanError(
            message="Un composant NEXUS est manquant.",
            action="Réinstalle les dépendances via Settings > Re-run Setup.",
            technical=str(exc),
        )

    if "permission" in exc_str or "access denied" in exc_str:
        return HumanError(
            message="Permission refusée.",
            action="NEXUS n'a pas les droits nécessaires pour cette action.",
            technical=str(exc),
        )

    # Default fallback
    return HumanError(
        message="Une erreur inattendue s'est produite.",
        action="Essaie à nouveau. Si le problème persiste, redémarre NEXUS.",
        technical=str(exc),
    )
