"""
Runner pour agents spécialisés spawnés via tmux.

Ce module permet de lancer un agent spécialisé en mode standalone,
qui s'enregistre auprès du GodAgent via ACI.

Usage:
    python -m agents.specialists.runner \
        --agent agents.specialists.coder.agent:CoderAgent \
        --agent-name CoderAgent \
        --project-root /path/to/harness
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Ajouter le project root au path pour les imports
_project_root: Optional[Path] = None


def setup_path(project_root: Optional[str] = None) -> Path:
    """Configure le Python path pour importer depuis la racine du projet."""
    global _project_root
    
    if project_root:
        _project_root = Path(project_root)
    else:
        # Trouver la racine depuis ce fichier
        _project_root = Path(__file__).parent.parent.parent
    
    # Ajouter au sys.path
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))
    
    return _project_root


async def run_agent(
    agent_module: str,
    agent_name: Optional[str] = None,
    god_aci_endpoint: Optional[str] = None,
    project_root: Optional[str] = None,
    log_level: str = "INFO",
) -> None:
    """
    Lance un agent spécialisé et le connecte au GodAgent.
    
    Args:
        agent_module: Chemin du module de l'agent (ex: "agents.specialists.coder.agent:CoderAgent")
        agent_name: Nom à donner à l'agent (optionnel)
        god_aci_endpoint: Endpoint ACI du GodAgent (optionnel)
        project_root: Racine du projet (optionnel)
        log_level: Niveau de logging
    """
    # Configurer le path
    setup_path(project_root)
    
    # Configurer le logging
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
    logger = logging.getLogger(__name__)
    
    # Parser le module
    if ":" not in agent_module:
        raise ValueError(
            f"Format de module invalide: {agent_module}. "
            f"Attendu: 'module.path:ClassName'"
        )
    
    module_path, class_name = agent_module.rsplit(":", 1)
    
    # Importer dynamiquement la classe de l'agent
    try:
        import importlib
        module = importlib.import_module(module_path)
        agent_class = getattr(module, class_name)
    except ImportError as e:
        logger.error(f"Impossible d'importer le module {module_path}: {e}")
        raise
    except AttributeError as e:
        logger.error(f"Classe {class_name} introuvable dans {module_path}: {e}")
        raise
    
    # Créer l'agent
    logger.info(f"Création de l'agent {class_name}...")
    agent = agent_class(name=agent_name or class_name)
    
    # Configurer ACI
    # Pour l'instant, on utilise InMemoryACI car les agents spawnés dans tmux
    # ne peuvent pas accéder directement à l'instance ACI du GodAgent
    # Solution temporaire: utiliser un fichier ou socket pour la communication
    from core.aci import InMemoryACI
    aci = InMemoryACI()
    agent.aci = aci
    
    # Initialiser l'agent
    try:
        logger.info(f"Initialisation de {agent.name}...")
        await agent.initialize()
        logger.info(f"✓ Agent {agent.name} initialisé et prêt")
    except Exception as e:
        logger.error(f"✗ Échec de l'initialisation de {agent.name}: {e}")
        raise
    
    # Afficher les informations de l'agent
    logger.info(f"Agent: {agent.name}")
    logger.info(f"Description: {agent.description}")
    logger.info(f"Capacités: {[cap.name for cap in agent.capabilities]}")
    logger.info(f"État: {agent.state.value}")
    
    # Message de ready
    logger.info(f"{agent.name} est prêt à recevoir des tâches. Appuyez sur Ctrl+C pour quitter.")
    
    # Garder l'agent vivant
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info(f"Arrêt de {agent.name}...")
        await agent.shutdown()
        logger.info(f"✓ {agent.name} arrêté proprement")


def main() -> None:
    """Point d'entrée pour lancer un agent via CLI."""
    parser = argparse.ArgumentParser(
        description="Runner pour agents spécialisés Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python -m agents.specialists.runner --agent agents.specialists.coder.agent:CoderAgent
  python -m agents.specialists.runner --agent agents.specialists.reviewer.agent:ReviewerAgent --log-level DEBUG
        """
    )
    
    parser.add_argument(
        "--agent",
        required=True,
        help="Module de l'agent (ex: agents.specialists.coder.agent:CoderAgent)"
    )
    
    parser.add_argument(
        "--agent-name",
        help="Nom à donner à l'agent (optionnel, sinon utilise la classe)"
    )
    
    parser.add_argument(
        "--god-aci-endpoint",
        help="Endpoint ACI du GodAgent (ex: tcp://localhost:65432)"
    )
    
    parser.add_argument(
        "--project-root",
        help="Racine du projet Harness"
    )
    
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Niveau de logging"
    )
    
    args = parser.parse_args()
    
    # Lancer l'agent
    try:
        asyncio.run(run_agent(
            agent_module=args.agent,
            agent_name=args.agent_name,
            god_aci_endpoint=args.god_aci_endpoint,
            project_root=args.project_root,
            log_level=args.log_level,
        ))
    except KeyboardInterrupt:
        print("\nInterrompu par l'utilisateur")
        sys.exit(0)
    except Exception as e:
        print(f"Erreur: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
