# 🔒 Sécurité NEXUS

## Principes

1. **Souveraineté** : Aucune donnée ne quitte ton PC sans ton consentement explicite.
2. **Permissions** : Mode auto-approuve ou confirmation manuelle pour chaque action.
3. **Isolation** : Le code exécuté par l'agent tourne dans un sandbox (local ou Docker).
4. **Chiffrement** : Les clés API et secrets sont chiffrés via le vault intégré.
5. **Audit** : Toutes les actions sont journalisées dans l'audit trail.

## Sandbox

| Type | Description |
|------|-------------|
| **Local** | Sous-processus isolé, timeout, pas de réseau |
| **Docker** | Conteneur éphémère, read-only, network none, ressources limitées |

## Vault

Les clés API sont stockées dans un fichier chiffré avec Fernet (cryptography).
Le pepper est généré aléatoirement au premier lancement.

## Rapport de vulnérabilité

Si tu découvres une vulnérabilité, ouvre une issue **privée** sur GitHub
ou contacte les maintainers directement.

Ne publie pas de vulnérabilité avant qu'elle soit corrigée.
