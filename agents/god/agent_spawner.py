"""
AgentSpawner - Spawn des agents spécialisés via tmux à la demande.

Ce module permet de lancer des agents spécialisés (CoderAgent, ReviewerAgent, etc.)
dans des sessions tmux dédiées, pour une isolation et une gestion dynamique.
"""

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING
import logging

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from agents.god.agent import GodAgent
    from core.aci.interface import ACIInterface


class AgentSpawner:
    """
    Spawn des agents spécialisés dans des sessions tmux dédiées.
    
    Chaque agent spécialisé (CoderAgent, ReviewerAgent, etc.) est lancé
    dans sa propre session tmux, ce qui permet de :
    - Isoler les agents dans des processus séparés
    - Les démarrer à la demande
    - Les conserver vivants entre les tâches
    - Les surveiller et les terminer proprement
    
    Attributes:
        god: Référence vers le GodAgent parent
        aci: Référence vers l'ACIInterface pour la communication
        _spawned_sessions: Dict mapping agent_name -> tmux_session_name
    """
    
    def __init__(self):
        self.god: Optional["GodAgent"] = None
        self.aci: Optional["ACIInterface"] = None
        self._spawned_sessions: Dict[str, str] = {}
        self._project_root = self._get_project_root()
    
    def _get_project_root(self) -> Path:
        """Trouve la racine du projet Harness."""
        # Remonter depuis ce fichier : agents/god/agent_spawner.py
        return Path(__file__).parent.parent.parent
    
    def set_god_reference(self, god: "GodAgent") -> None:
        """Définit la référence vers GodAgent."""
        self.god = god
        self.aci = god.aci if hasattr(god, 'aci') else None
    
    async def spawn_agent(self, agent_name: str) -> bool:
        """
        Spawn un agent spécialisé dans une nouvelle session tmux.
        
        Args:
            agent_name: Nom de l'agent à spawner (ex: "CoderAgent")
            
        Returns:
            True si l'agent a été spawné avec succès, False sinon
        """
        # Vérifier si l'agent est déjà spawné
        if agent_name in self._spawned_sessions:
            logger.info(f"Agent {agent_name} déjà spawné dans session {self._spawned_sessions[agent_name]}")
            return True
        
        # Mapper le nom de l'agent au module Python
        agent_module_map = {
            "CoderAgent": "agents.specialists.coder.agent:CoderAgent",
            "ReviewerAgent": "agents.specialists.reviewer.agent:ReviewerAgent",
            "PlannerAgent": "agents.specialists.planner.agent:PlannerAgent",
            "TesterAgent": "agents.specialists.tester.agent:TesterAgent",
            "DebuggerAgent": "agents.specialists.debugger.agent:DebuggerAgent",
            "ResearcherAgent": "agents.specialists.researcher.agent:ResearcherAgent",
            "DocumenterAgent": "agents.specialists.documenter.agent:DocumenterAgent",
        }
        
        if agent_name not in agent_module_map:
            logger.warning(f"Agent {agent_name} non reconnu, impossible de spawner")
            # Essayer quand même avec une convention de nommage
            module_path = f"agents.specialists.{agent_name.lower()}.agent:{agent_name}"
            if module_path not in agent_module_map.values():
                agent_module_map[agent_name] = module_path
            else:
                return False
        
        module_path = agent_module_map[agent_name]
        
        # Générer un nom de session tmux unique
        session_name = self._generate_session_name(agent_name)
        
        # Construire la commande tmux
        cmd = self._build_tmux_command(session_name, module_path, agent_name)
        
        try:
            # Lancer la session tmux
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                cwd=self._project_root
            )
            
            if result.returncode != 0:
                logger.error(f"Échec du spawn de {agent_name}: {result.stderr}")
                return False
            
            # Enregistrer la session
            self._spawned_sessions[agent_name] = session_name
            logger.info(f"Agent {agent_name} spawné dans session tmux: {session_name}")
            
            # Attendre un peu pour laisser le temps à l'agent de s'initialiser
            await asyncio.sleep(0.5)
            
            return True
            
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout lors du spawn de {agent_name}")
            return False
        except Exception as e:
            logger.error(f"Erreur lors du spawn de {agent_name}: {e}")
            return False
    
    def _generate_session_name(self, agent_name: str) -> str:
        """Génère un nom de session tmux unique."""
        import time
        timestamp = int(time.time())
        return f"harness-{agent_name.lower()}-{os.getpid()}-{timestamp}"
    
    def _build_tmux_command(
        self, 
        session_name: str, 
        module_path: str, 
        agent_name: str
    ) -> list:
        """Construire la commande tmux pour lancer un agent."""
        # Trouver le chemin vers Python
        python_path = self._find_python_path()
        
        # Commande pour lancer l'agent dans tmux
        cmd = [
            "tmux", "new-session", "-d", "-s", session_name,
            python_path, "-m", "agents.specialists.runner",
            "--agent", module_path,
            "--agent-name", agent_name,
            "--project-root", str(self._project_root),
        ]
        
        # Ajouter le chemin vers le venv si nécessaire
        venv_python = str(self._project_root / ".venv" / "bin" / "python")
        if os.path.exists(venv_python):
            # Utiliser le venv
            cmd[4] = venv_python
        
        return cmd
    
    def _find_python_path(self) -> str:
        """Trouve le chemin vers l'exécutable Python."""
        # Essayer le venv d'abord
        venv_python = str(self._project_root / ".venv" / "bin" / "python")
        if os.path.exists(venv_python):
            return venv_python
        
        # Sinon, utiliser python du système
        return "python"
    
    async def kill_agent(self, agent_name: str) -> bool:
        """
        Terminer un agent et sa session tmux.
        
        Args:
            agent_name: Nom de l'agent à terminer
            
        Returns:
            True si l'agent a été tué avec succès, False sinon
        """
        if agent_name not in self._spawned_sessions:
            logger.warning(f"Agent {agent_name} n'est pas spawné")
            return False
        
        session_name = self._spawned_sessions.pop(agent_name)
        
        try:
            # Tuer la session tmux
            result = subprocess.run(
                ["tmux", "kill-session", "-t", session_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                logger.error(f"Échec de la termination de {session_name}: {result.stderr}")
                # Remettre dans le dict car la session existe toujours
                self._spawned_sessions[agent_name] = session_name
                return False
            
            logger.info(f"Agent {agent_name} (session {session_name}) terminé")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la termination de {agent_name}: {e}")
            # Remettre dans le dict
            self._spawned_sessions[agent_name] = session_name
            return False
    
    async def kill_all(self) -> int:
        """
        Terminer tous les agents spawnés.
        
        Returns:
            Nombre d'agents tués avec succès
        """
        count = 0
        for agent_name in list(self._spawned_sessions.keys()):
            if await self.kill_agent(agent_name):
                count += 1
        return count
    
    def list_spawned(self) -> Dict[str, str]:
        """
        Liste des agents spawnés et leurs sessions tmux.
        
        Returns:
            Dictionnaire {agent_name: tmux_session_name}
        """
        return self._spawned_sessions.copy()
    
    def is_agent_spawned(self, agent_name: str) -> bool:
        """Vérifie si un agent est spawné."""
        return agent_name in self._spawned_sessions
    
    def get_session_name(self, agent_name: str) -> Optional[str]:
        """Obtient le nom de la session tmux pour un agent."""
        return self._spawned_sessions.get(agent_name)
    
    def clear(self) -> None:
        """Efface la liste des sessions (sans tuer les sessions tmux)."""
        self._spawned_sessions.clear()
    
    def __repr__(self) -> str:
        return f"AgentSpawner(spawned={len(self._spawned_sessions)})"
