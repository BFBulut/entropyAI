"""
Ajan önyüklemesi: açılışta ve proje değiştiğinde koşan tek giriş noktası.

Daha önce bu mantık `entropy.main` içinde gömülüydü ve test edilemiyordu:
istisnalar `print` ile yutuluyor, pencereli derlemede stderr olmadığı için
derlemenin hiç koşmadığı ancak diske bakılarak anlaşılıyordu. Ayrıca
paketlenmiş sürümde `APP_ROOT` .exe'nin klasörü (`dist/EntropyAI`) olduğundan
üretilen tanımlar gerçek proje kökünde görünmüyordu.

Sözleşme:
- `ensure_defaults()` ÖNCE koşar (tohum ajanlar diske düşer), derleme SONRA;
  aksi hâlde ilk açılışta hiçbir şey derlenmezdi.
- Derleme yalnızca kayıt defterindeki adlar için dosya yazar; başka bir ajanı
  (kullanıcının elle yazdığı `.claude/agents/*.md` ya da `.agents/agents/distiller`)
  ne siler ne de değiştirir.
- Her adım loglanır; hata önyüklemeyi durdurmaz.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BootstrapResult:
    """Önyükleme özeti; çağıran (UI/terminal) bunu kullanıcıya basar."""

    created: List[str] = field(default_factory=list)
    offices_created: List[str] = field(default_factory=list)
    compiled: Dict[str, Dict[str, Path]] = field(default_factory=dict)
    roots: List[Path] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def summary(self) -> str:
        if self.error:
            return f"Ajan önyüklemesi başarısız: {self.error}"
        parts = []
        if self.created:
            parts.append(f"varsayılan ajanlar oluşturuldu: {', '.join(self.created)}")
        if self.offices_created:
            parts.append(f"varsayılan ofisler oluşturuldu: {', '.join(self.offices_created)}")
        if self.compiled:
            parts.append(
                f"{len(self.compiled)} ajan derlendi ({', '.join(sorted(self.compiled))}) "
                f"-> {', '.join(str(r) for r in self.roots)}"
            )
        return "; ".join(parts) or "derlenecek ajan yok"


def bootstrap_agents(
    project_dir: Optional[Path | str] = None,
    vault_path: Optional[Path | str] = None,
) -> BootstrapResult:
    """
    Tohum ajanları garanti eder ve tüm ajanları sağlayıcı biçimlerine derler.

    `project_dir` None/geçersizse derleme yine de uygulama köküne ve ayarlardaki
    etkin projeye yazar (bkz. `compile_roots`), yani hiçbir durumda sessizce
    atlanmaz.
    """
    from entropy.agents.compile import compile_roots
    from entropy.agents.offices import OfficeRegistry
    from entropy.agents.registry import AgentRegistry

    result = BootstrapResult()
    try:
        registry = AgentRegistry(vault_path=vault_path)
        result.created = registry.ensure_defaults()
        if result.created:
            logger.info("Varsayılan ajanlar oluşturuldu: %s", ", ".join(result.created))
        # Ofisler ajanlardan SONRA tohumlanır: tohum ofis, tohum ajanlara
        # (orkestrator/degerlendirici) atıfta bulunuyor; ters sırada ofis var
        # ama orkestratörü olmayan bir kurulum çıkardı.
        result.offices_created = OfficeRegistry(vault_path=vault_path).ensure_defaults()
        if result.offices_created:
            logger.info("Varsayılan ofisler oluşturuldu: %s", ", ".join(result.offices_created))
        result.roots = compile_roots(project_dir)
        result.compiled = registry.compile_all(project_dir)
        logger.info(
            "Ajan derlemesi: %d ajan, kökler=%s",
            len(result.compiled),
            [str(r) for r in result.roots],
        )
    except Exception as exc:  # önyükleme uygulamayı düşürmemeli
        result.error = str(exc)
        logger.exception("Ajan önyüklemesi başarısız")
    return result
