# Harness — Guide pour Claude Code

Framework d'agents Python avec un orchestrateur central (`GodAgent`) qui spawn des agents spécialisés dans des sessions tmux. Interface TUI (Textual) et API (FastAPI, à venir). LLM via Ollama par défaut.

## Stack

- Python 3.12+, **async partout** (`asyncio`)
- Textual (TUI), FastAPI (API)
- Ollama via `OpenAICompatibleProvider` sur `http://localhost:11434/v1`
- `tmux` pour l'isolation des agents spawnés
- pytest, ruff, black

## Commandes

```bash
make run-tui          # Démarrer la TUI
make test             # Tests
make test-coverage    # Tests + couverture
make lint             # ruff
make format           # black + ruff --fix
make install          # Dépendances
```

## Pré-requis runtime

- `ollama serve` doit tourner — sinon `LLMAgent` échoue à l'init
- `tmux` installé — sinon `AgentSpawner` échoue
- `.env` configuré : `DEFAULT_LLM_PROVIDER=ollama`, `OLLAMA_MODEL`, `OLLAMA_BASE_URL=http://localhost:11434/v1`

## Architecture

```
TUI ─┐
     ├─→ GodAgent ─┬─→ LLMAgent (Ollama)
API ─┘             ├─→ AgentRegistry
                   ├─→ TaskRouter / TaskDecomposer / ResultAggregator
                   └─→ AgentSpawner ──tmux──→ CoderAgent / ReviewerAgent / …
```

- **`GodAgent`** (`agents/god/agent.py`) : orchestrateur. Route les tâches, gère la conversation, *aucune logique métier*.
- **`LLMAgent`** (`agents/specialists/llm_agent.py`) : wrapper LLM, gère l'historique de conversation.
- **`AgentSpawner`** (`agents/god/agent_spawner.py`) : spawn dans tmux. Sessions nommées `harness-{agent_name}-{pid}-{index}`.
- **`Runner`** (`agents/specialists/runner.py`) : entry point des agents spawnés, s'enregistre via ACI.
- **ACI** (`core/aci/`) : messagerie inter-agents. Impl. en mémoire pour l'instant — TCP/Redis prévu pour les processus séparés.

## Layout

```
agents/
├── base.py                       # BaseAgent, HybridAgent, TaskContext, TaskResult
├── god/{agent,agent_spawner}.py
└── specialists/
    ├── llm_agent.py
    ├── runner.py
    └── {coder,reviewer,planner}/

core/{aci,sandbox,monitoring,tools}/
providers/                        # LLMProvider, Registry, OpenAI-compatible
configs/                          # llm_config.py, schemas, agent_configs/*.yaml
tui/                              # app.py, controller.py, screens/, widgets/
tests/
```

## Conventions

- **Async/await partout.** Pas de blocant sync dans les chemins async. `asyncio.gather()` pour le parallélisme.
- **Type hints obligatoires.** `Optional[T]` plutôt que `Union[T, None]`. `TYPE_CHECKING` pour les imports circulaires.
- **Streaming = `AsyncIterator[str]`.** Toujours `yield` des chunks ; jamais de `return` unique dans une méthode `*_stream()`. Prévoir un fallback pour les providers sans streaming.
- **Séparation des responsabilités** :
  - `GodAgent` → orchestration uniquement
  - `LLMAgent` → interface LLM uniquement
  - `TUIController` → adaptateur, pas de logique métier
  - Agents spécialisés → logique métier
- **Erreurs** : logger systématiquement, exceptions définies dans `agents/base.py`, messages utilisateur lisibles.
- **Modèle LLM** : jamais hardcodé, toujours via `get_llm_config()` qui lit `.env`.
- **Cleanup tmux** : kill les sessions à la sortie de l'app, vérifier `tmux list-sessions` après crash.

## À ne pas faire

- Bypass de `TaskRouter` pour exécuter directement sur un agent (sauf tests).
- Mettre de la logique LLM dans `GodAgent` — toujours passer par `LLMAgent`.
- Code sync dans un chemin async.
- Laisser des sessions tmux orphelines.
- Modifier les modèles d'affichage TUI (`tui/models/`) sans passer par les converters.

## Graphe de connaissances

`graphify-out/graph.html` — visualisation interactive de la codebase (classes, fonctions, dépendances, clusters par module). Utile pour cartographier un flux ou trouver les usages d'une fonction.

```bash
xdg-open graphify-out/graph.html
# ou
python -m http.server 8000 --directory graphify-out
```

## Roadmap & état d'avancement

Voir `plan.md` (ou `ROADMAP.md`) — pas dans ce fichier, qui doit refléter l'état *courant* du code.
