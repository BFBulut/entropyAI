"""
Ajan katmanı: kasadaki ajan tanımları, sağlayıcı derlemesi ve görev kartları.

Üç modül:
  registry.py  — `<kasa>/Entropy/Agents/<ad>/AGENT.md` dosyalarını okur/yazar.
  compile.py   — kaynak tanımı agy (.agents/agents/<ad>/agent.md) ve Claude
                 (.claude/agents/<ad>.md) biçimlerine derler.
  tasks.py     — `<kasa>/Entropy/Tasks/<id>.md` görev kartları ve yürütme.

Kaynak tek: kullanıcı Obsidian'da düzenler, derleme türetilmiş çıktıdır.
"""

from entropy.agents.registry import AgentSpec, AgentRegistry  # noqa: F401
from entropy.agents.tasks import TaskCard, TaskBoard  # noqa: F401

__all__ = ["AgentSpec", "AgentRegistry", "TaskCard", "TaskBoard"]
