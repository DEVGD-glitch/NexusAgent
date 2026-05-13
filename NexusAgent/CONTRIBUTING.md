# 🤝 Contribuer à NEXUS

## Comment contribuer

1. **Fork** le projet
2. Crée une branche : `git checkout -b feat/ma-feature`
3. Commit : `git commit -m "feat: ajoute ma feature"`
4. Push : `git push origin feat/ma-feature`
5. Ouvre une **Pull Request**

## Conventions

### Messages de commit

```
feat: ajoute le provider gratuit Pollinations
fix: corrige le timeout du routeur LLM
refactor: simplifie le convertisseur de messages
test: ajoute les tests pour le memory compactor
docs: met à jour le README
```

### Code

- **Tout en français** : UI, messages, docs, CLI. Identifiants et logs en anglais.
- **Async-first** : FastAPI + async everywhere
- **MCP = protocole universel** : chaque capacité exposée comme outil MCP
- **Tests avant merge** : `pytest tests/ -v` doit passer
- **Type hints** : mypy strict

### Branches

| Préfixe | Usage |
|---------|-------|
| `feat/` | Nouvelle fonctionnalité |
| `fix/` | Correction de bug |
| `refactor/` | Refactoring |
| `docs/` | Documentation |
| `test/` | Tests |

---

## Structure du Projet

```
nexus/           → Backend Python
nexus-web/       → Frontend Next.js
nexus-desktop/   → App Tauri (bientôt)
docs/            → Documentation
tests/           → 22k+ lignes de tests
```

---

## Setup Développement

```bash
git clone https://github.com/YOUR_USERNAME/nexus.git
cd nexus
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
pip install -r requirements.txt
cd nexus-web && npm install && cd ..

# Tests
pytest tests/ -v

# Lint + types
ruff check nexus/ tests/
mypy nexus/
```
