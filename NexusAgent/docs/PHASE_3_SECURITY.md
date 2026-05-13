# Phase 3 — Sécurité et Permissions

## Résumé
Mise en place du système de permissions souverain : l'utilisateur contrôle tout, l'agent demande confirmation pour les actions dangereuses, et les actions importantes sont tracées.

## Ce qui a été fait

### 3.1 Mode de Permissions Dual

| Mode | Comportement |
|------|-------------|
| **🔓 Auto-approuve** | Flux libre. Confirmation UNIQUEMENT pour les actions dangereuses (suppression, exécution code, accès système) |
| **🔒 Confirmation** | Toute action importante demande confirmation via toast |

### 3.2 Actions Toujours Confirmées (même en auto-approuve)

Actions dangereuses identifiées :
- `delete_file` — Suppression de fichier (définitif)
- `delete_memory` — Suppression en mémoire
- `execute_code` / `execute_sandboxed` — Exécution de code arbitraire
- `write_file` — Écriture dans un fichier
- `move_file` — Déplacement de fichier
- `install_package` — Installation de package Python

Chemins système protégés :
- `C:\Windows\*`
- `C:\Program Files\*`
- `C:\Program Files (x86)\*`
- Tout chemin contenant "System" ou "Windows"

### 3.3 Implémentation Frontend

```typescript
// nexus-api.ts
const DANGEROUS_ACTIONS = [
  'delete_file', 'delete_memory', 'execute_code', 'execute_sandboxed',
  'move_file', 'write_file', 'install_package',
]

async function gatedAction(action, params, description) {
  const isDangerous = DANGEROUS_ACTIONS.includes(action) || 
    params.path?.includes('System') || 
    params.path?.includes('Windows')

  if (isDangerous || store.settings.permissionMode === 'confirm') {
    const approved = await store.requestPermission(
      isDangerous ? '⚠️ Action nécessite confirmation' : 'Confirmer l\'action',
      description
    )
    if (!approved) throw new Error('Action annulée par l\'utilisateur')
  }
  // ... execute action
}
```

### 3.4 Audit Log Léger

- Chaque action est loguée (chat, run_task, tool:xxx)
- Détails : latence, statut, paramètres tronqués
- Les échecs sont aussi logués
- L'audit ne bloque JAMAIS l'API (try/except silencieux)
- Consultable via `GET /security/audit`

### 3.5 Pas de Garde-fous Output

Conformément au choix de l'utilisateur :
- Pas de filtrage de contenu en sortie
- Les modèles IA ont déjà leurs propres garde-fous
- L'utilisateur est souverain

## Fichiers Concernés
- `src/lib/nexus-api.ts` — Permission gating côté frontend
- `src/lib/nexus-store.ts` — Store des permissions et toasts
- `src/components/nexus/toast-container.tsx` — UI de confirmation
- `src/components/nexus/security-panel.tsx` — Panneau sécurité
- `nexus/api/gateway.py` — Audit logging côté backend
- `nexus/security/audit.py` — Module d'audit
