"""
Bütçeli bilişsel bağlam birleştirici.

Neyi değiştiriyor
-----------------
Önceki bağlam toplama sabit dilimlerle çalışıyordu: MEMORY.md'nin ilk 750 karakteri,
raporların ilk 2 tanesinin ilk satırının ilk 180 karakteri, 4 hafıza düğümü. Bu
seçim alakaya değil sıraya dayandığı için, kasadaki 7,8 milyon karakterin yaklaşık
%0,17'si ve çoğu konuyla ilgisiz kısmı enjekte ediliyordu.

Buradaki yaklaşım
-----------------
Sabit bir token bütçesi, öncelik sırasına göre doldurulur:

  1. Yetenek playbook'u   — "bu iş nasıl yapılır" (varsa, her zaman ilk sırada)
  2. Hibrit recall        — sorguya semantik + sözcüksel olarak en yakın anılar
  3. Rapor alıntıları     — sorguyla ilgili raporlardan gerçek gövde parçaları
  4. Kalıcı hafıza        — MEMORY.md'nin ilgili kısmı

Bütçe dolduğunda kesilir. Böylece maliyet deponun büyüklüğünden bağımsız kalır:
100 rapor da olsa 1000 rapor da olsa prompt aynı boyutta kalır, yalnızca içine
giren parçalar daha isabetli olur.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from entropy.memory.playbook import PlaybookStore, estimate_tokens

logger = logging.getLogger(__name__)

# Varsayılan toplam bütçe (token). Mevcut davranış ~3300 token üretiyordu; benzer
# maliyette kalıp sinyali artırmak hedefleniyor.
DEFAULT_TOKEN_BUDGET = 4000

# Öncelik sırasına göre bölüm tavanları (token).
BUDGET_PLAYBOOK = 1500
BUDGET_RECALL = 800
BUDGET_REPORTS = 900
BUDGET_PROJECT = 400
BUDGET_CODE = 400
BUDGET_GLOBAL_MEMORY = 300


@dataclass
class ContextSection:
    """Bağlamın tek bir bölümü; hangi kaynaktan geldiği izlenebilir olsun diye ayrı tutulur."""

    title: str
    body: str
    kind: str
    tokens: int = 0

    def render(self) -> str:
        return f"[{self.title}]:\n{self.body}"


@dataclass
class AssembledContext:
    sections: List[ContextSection] = field(default_factory=list)
    budget: int = DEFAULT_TOKEN_BUDGET

    @property
    def tokens(self) -> int:
        return sum(s.tokens for s in self.sections)

    def render(self) -> str:
        return "\n\n".join(s.render() for s in self.sections if s.body.strip())

    def summary(self) -> Dict[str, Any]:
        return {
            "total_tokens": self.tokens,
            "budget": self.budget,
            "sections": [{"kind": s.kind, "title": s.title, "tokens": s.tokens} for s in self.sections],
        }


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Metni token tavanına indirir; mümkünse satır sınırından keser."""
    if max_tokens <= 0 or not text:
        return ""
    if estimate_tokens(text) <= max_tokens:
        return text
    max_chars = max_tokens * 4
    cut = text[:max_chars]
    nl = cut.rfind("\n")
    if nl > max_chars * 0.6:
        cut = cut[:nl]
    return cut.rstrip() + " …"


def _strip_frontmatter(text: str) -> str:
    m = re.match(r"^---\s*\n.*?\n---\s*\n(.*)$", text, re.DOTALL)
    return (m.group(1) if m else text).strip()


def _best_excerpt(body: str, query: str, max_chars: int) -> str:
    """
    Rapor gövdesinden sorguya en yakın bölümü seçer.

    Belgenin başını almak yerine, sorgu terimlerinin en yoğun geçtiği paragraf
    penceresini döndürür; bir raporun ilk satırı çoğunlukla başlık tekrarıdır ve
    hiçbir bilgi taşımaz.
    """
    if not body:
        return ""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if not paragraphs:
        return body[:max_chars]

    terms = {t for t in re.findall(r"\w+", (query or "").lower()) if len(t) >= 4}
    if not terms:
        return "\n\n".join(paragraphs)[:max_chars]

    scored = []
    for idx, para in enumerate(paragraphs):
        low = para.lower()
        hits = sum(1 for t in terms if t in low)
        if hits:
            scored.append((hits, -idx, idx))

    if not scored:
        return "\n\n".join(paragraphs)[:max_chars]

    scored.sort(reverse=True)
    best_idx = scored[0][2]
    window: List[str] = []
    total = 0
    for para in paragraphs[best_idx : best_idx + 4]:
        if total + len(para) > max_chars:
            window.append(para[: max(0, max_chars - total)])
            break
        window.append(para)
        total += len(para)
    return "\n\n".join(window).strip()


class CognitiveContextBuilder:
    """Sorgu ve yeteneğe göre, token bütçesine uyan bilişsel bağlam üretir."""

    def __init__(
        self,
        memory_system: Any = None,
        vault_manager: Any = None,
        playbook_store: Optional[PlaybookStore] = None,
    ):
        self._memory = memory_system
        self._vault = vault_manager
        self.playbooks = playbook_store or PlaybookStore()

    # -- tembel bağımlılıklar (Qt dışı bağlamda da kurulabilsin diye) ----

    @property
    def memory(self):
        if self._memory is None:
            from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem

            self._memory = CognitiveMemorySystem()
        return self._memory

    @property
    def vault(self):
        if self._vault is None:
            from entropy.memory.obsidian.vault_manager import ObsidianVaultManager

            self._vault = ObsidianVaultManager()
        return self._vault

    # -- bölümler -------------------------------------------------------

    # Bütçe daralınca hangi bölümün önce kırpılacağı: uzun "Çalışma Adımları"
    # en sona bırakılır; kısa ve kararı belirleyen bölümler (ne zaman, ölçütler,
    # tuzaklar, çıktı biçimi) her zaman tam girer.
    _PLAYBOOK_TRIM_LAST = ("çalışma adımları", "calisma adimlari")

    # Sorguya göre bölüm seçiminde, alakasız bölümlerin özetine ayrılabilecek
    # azami pay. Kalan bütçe her zaman ilgili bölümlerin tam metnine gider;
    # yoksa 9000 karakterlik bir playbook'ta 1500 token yalnızca başlıklara giderdi.
    _DIGEST_BUDGET_RATIO = 0.4
    # Sorguya göre tam metin verilecek azami bölüm sayısı.
    _RELEVANT_SECTION_LIMIT = 2

    # Türkçe eklemeli bir dil: "tuzaklara" alt dizge olarak "Tuzaklar" başlığında
    # geçmez. Bu yüzden eşleşme sözcük gövdesi (ilk 5 harf) üzerinden yapılır.
    _STEM_LEN = 5
    # Her sorguda geçen, hiçbir bölümü ayırt etmeyen sözcükler.
    _QUERY_STOPWORDS = frozenset(
        {
            "hangi", "nasil", "nasıl", "neler", "nedir", "için", "icin", "olan", "daha",
            "sonra", "önce", "once", "gibi", "kadar", "bana", "bunu", "şunu", "sunu",
            "lazim", "lazım", "gerek", "yapmam", "etmem", "misin", "musun", "what",
            "which", "should", "there", "about",
        }
    )

    # Kullanıcı "adim" yazıyor, playbook "Adımları" diyor: Türkçe aksanları
    # katlanmazsa hiçbir bölüm eşleşmiyor (ölçüldü: hedef bölüm seçilemiyordu).
    _FOLD = str.maketrans("ıİşŞğĞüÜöÖçÇâÂîÎûÛ", "iisSgGuUoOcCaAiIuU")

    @classmethod
    def _fold(cls, text: str) -> str:
        return text.translate(cls._FOLD).lower()

    @classmethod
    def _query_stems(cls, query: str) -> List[str]:
        out: List[str] = []
        for w in re.findall(r"\w+", cls._fold(query or "")):
            if len(w) < 3 or w in cls._QUERY_STOPWORDS:
                continue
            stem = w[: cls._STEM_LEN]
            if stem not in out:
                out.append(stem)
        return out

    @classmethod
    def _section_score(cls, section: str, stems: List[str]) -> int:
        words = re.findall(r"\w+", cls._fold(section))
        if not words:
            return 0
        # Başlık iki kez sayılır: bölümün konusunu en iyi o anlatır.
        head_words = re.findall(r"\w+", cls._fold(section.splitlines()[0]))
        score = 0
        for stem in stems:
            score += sum(1 for w in words if w.startswith(stem))
            score += 2 * sum(1 for w in head_words if w.startswith(stem))
        return score

    @staticmethod
    def _section_digest(section: str) -> str:
        """Bölümün başlığı ve ilk maddesi; 'burada şu var' bilgisini token'sız taşır."""
        lines = [ln for ln in section.splitlines() if ln.strip()]
        if not lines:
            return ""
        head = lines[0].rstrip()
        for ln in lines[1:]:
            body = ln.strip()
            if body:
                return f"{head}\n{body}"
        return head

    @classmethod
    def _fit_playbook_by_query(cls, procedure: str, budget: int, query: str) -> Optional[str]:
        """
        Sorguyla ilgili bölümleri tam, diğerlerini başlık + ilk madde olarak verir.

        Playbook diskte 9000 karaktere kadar büyüyor, bütçe ise 1500 token
        (~6000 karakter). Sabit öncelikle kırpmak, sorusu tuzaklarla ilgili olan
        bir turda adımları tam, tuzakları yarım vermek anlamına geliyordu.
        Sorgu terimi taşımayan bölüm tamamen düşmez; başlığı kalır ki ajan
        neyin var olduğunu bilsin.

        Sorgu bir bölümle eşleşmiyorsa None döner ve sabit öncelikli yola dönülür.
        """
        stems = cls._query_stems(query)
        if not stems:
            return None

        # Alt başlıklar da ayrı seçilebilir: gerçek playbook'larda "Çalışma
        # Adımları" altında beş '###' bloğu var ve sorgu çoğu zaman yalnızca
        # birini ilgilendiriyor. Sabit öncelikli yol yalnızca '##' ile böler.
        sections = [s for s in re.split(r"(?m)^(?=#{2,3} )", procedure.strip()) if s.strip()]
        if len(sections) <= 1:
            return None

        scored = [(cls._section_score(sec, stems), idx) for idx, sec in enumerate(sections)]
        if not any(sc > 0 for sc, _ in scored):
            return None

        ranked = sorted(scored, key=lambda x: (-x[0], x[1]))
        relevant = {idx for sc, idx in ranked[: cls._RELEVANT_SECTION_LIMIT] if sc > 0}

        parts: Dict[int, str] = {}
        remaining = budget
        digest_cap = int(budget * cls._DIGEST_BUDGET_RATIO)
        digest_used = 0
        for idx, sec in enumerate(sections):
            if idx in relevant:
                continue
            digest = cls._section_digest(sec)
            cost = estimate_tokens(digest)
            if not digest.strip() or digest_used + cost > digest_cap or cost > remaining:
                continue
            parts[idx] = digest
            digest_used += cost
            remaining -= cost

        for _sc, idx in ranked:
            if idx not in relevant or remaining <= 0:
                continue
            text = _truncate_to_tokens(sections[idx].rstrip(), remaining)
            if not text.strip():
                continue
            parts[idx] = text.rstrip()
            remaining -= estimate_tokens(text)

        # Artan bütçe boşa gitmez: ilgili bölümler tam girdikten sonra kalan pay,
        # özete indirilmiş bölümlere puan sırasıyla geri verilir. Bu olmadan
        # kısa bir hedef bölüm bütçenin çoğunu kullanılmadan bırakıyordu
        # (financial-auditor: 1455 token yerine 120).
        for _sc, idx in ranked:
            if remaining <= 0:
                break
            if idx in relevant:
                continue
            current = parts.get(idx, "")
            gain = remaining + estimate_tokens(current)
            text = _truncate_to_tokens(sections[idx].rstrip(), gain)
            if estimate_tokens(text) <= estimate_tokens(current):
                continue
            remaining -= estimate_tokens(text) - estimate_tokens(current)
            parts[idx] = text.rstrip()

        body = "\n\n".join(parts[i] for i in sorted(parts) if parts[i].strip())
        # Bölüm bölüm sayılan token'lar birleştirme ayraçlarını saymaz; son kırpma
        # bütçenin gerçekten aşılmamasını garanti eder.
        return _truncate_to_tokens(body, budget) or None

    @classmethod
    def _fit_playbook(cls, procedure: str, budget: int, query: str = "") -> str:
        parts = re.split(r"(?m)^(?=## )", procedure.strip())
        sections = [p for p in parts if p.strip()]
        if len(sections) <= 1:
            return _truncate_to_tokens(procedure.strip(), budget)

        if query and query.strip():
            by_query = cls._fit_playbook_by_query(procedure, budget, query)
            if by_query:
                return by_query

        def is_steps(sec: str) -> bool:
            head = sec.splitlines()[0].lower().lstrip("# ").strip()
            return any(head.startswith(k) for k in cls._PLAYBOOK_TRIM_LAST)

        fixed_cost = sum(estimate_tokens(s) for s in sections if not is_steps(s))
        out: List[str] = []
        remaining = budget
        for sec in sections:
            if is_steps(sec):
                allowance = max(0, budget - fixed_cost)
                text = _truncate_to_tokens(sec, min(allowance, remaining))
            else:
                text = _truncate_to_tokens(sec, remaining)
            if not text.strip():
                continue
            out.append(text.rstrip())
            remaining -= estimate_tokens(text)
            if remaining <= 0:
                break
        return "\n\n".join(out)

    def _playbook_section(self, skill_name: str, budget: int, query: str = "") -> Optional[ContextSection]:
        pb = self.playbooks.load(skill_name)
        if not pb or not pb.procedure.strip():
            return None
        body = self._fit_playbook(pb.procedure, budget, query)
        coverage = f"{pb.processed_count}/{pb.source_count}" if pb.processed_count < pb.source_count else f"{pb.source_count}"
        return ContextSection(
            title=f"📘 {skill_name} — Öğrenilmiş Çalışma Yordamı ({coverage} rapordan damıtıldı)",
            body=body,
            kind="playbook",
            tokens=estimate_tokens(body),
        )

    def _recall_section(self, query: str, skill_name: Optional[str], budget: int) -> Optional[ContextSection]:
        try:
            hits = self.memory.hybrid_recall(query, top_k=12)
        except Exception as e:
            logger.warning("Hafıza geri çağırma başarısız: %s", e)
            return None
        if not hits:
            return None

        lines: List[str] = []
        used = 0
        for node, score in hits:
            content = (node.content or "").strip()
            if not content:
                continue
            entry = f"• ({score:.2f}) {content}"
            cost = estimate_tokens(entry)
            if used + cost > budget:
                break
            lines.append(entry)
            used += cost

        if not lines:
            return None
        return ContextSection(
            title="Hatırlanan İlgili Bilgiler",
            body="\n".join(lines),
            kind="recall",
            tokens=used,
        )

    # Anlamsal yedek sıralamada gömülecek azami rapor sayısı.
    SEMANTIC_CANDIDATE_LIMIT = 20
    SEMANTIC_MIN_SIMILARITY = 0.30

    def _semantic_rank(self, query: str, candidates: List[tuple]) -> List[tuple]:
        """
        Sözcüksel eşleşme bulunamadığında raporları anlamsal benzerliğe göre sıralar.

        Yalnızca ilk SEMANTIC_CANDIDATE_LIMIT aday gömülür; tüm arşivi her sorguda
        gömmek maliyeti deponun büyüklüğüne bağlar ve bu mimarinin amacına aykırıdır.
        """
        if not candidates:
            return []
        try:
            from entropy.memory.supabase.cognitive_memory import (
                LocalEmbeddingEngine,
                cosine_similarity,
            )

            engine = LocalEmbeddingEngine.get_instance()
            q_vec = engine.embed_text(query)
        except Exception as e:
            logger.warning("Anlamsal rapor sıralaması yapılamadı: %s", e)
            return []

        ranked: List[tuple] = []
        for _hits, path, raw in candidates[: self.SEMANTIC_CANDIDATE_LIMIT]:
            probe = f"{path.stem}\n{_strip_frontmatter(raw)[:1200]}"
            try:
                sim = cosine_similarity(q_vec, engine.embed_text(probe))
            except Exception:
                continue
            if sim >= self.SEMANTIC_MIN_SIMILARITY:
                # Sözcüksel yolla aynı biçimde döndürülür; skor sıralama içindir.
                ranked.append((sim, path, raw))

        ranked.sort(key=lambda x: x[0], reverse=True)
        return ranked

    def _reports_section(self, query: str, skill_name: Optional[str], budget: int) -> Optional[ContextSection]:
        """Yetenek raporlarından sorguya en yakın gövde parçalarını çıkarır."""
        if not skill_name:
            return None
        sources = self.playbooks.source_reports(skill_name)
        if not sources:
            return None

        # Eşik 3: kısaltmalar (CLO, SEO, RAG, KPI) finans ve teknik metinlerde
        # en ayırt edici terimlerdir; 4 harf eşiği bunları tamamen eliyordu.
        terms = {t for t in re.findall(r"\w+", (query or "").lower()) if len(t) >= 3}

        scored: List[tuple] = []
        for p in sources:
            try:
                raw = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            low = raw.lower()
            hits = sum(low.count(t) for t in terms) if terms else 0
            scored.append((hits, p, raw))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Sözcüksel eşleşme yoksa anlamsal benzerliğe düşülür: sorgu ile rapor
        # farklı kelimeler kullanıyor olabilir. Gömme maliyetli olduğu için
        # yalnızca sınırlı sayıda aday üzerinde çalışılır.
        if not scored or scored[0][0] == 0:
            scored = self._semantic_rank(query, scored)
            if not scored:
                return None

        blocks: List[str] = []
        used = 0
        per_report = max(400, (budget * 4) // 3)
        for score, path, raw in scored[:3]:
            # Skor sözcüksel yolda eşleşme sayısı, anlamsal yolda benzerliktir;
            # her iki durumda da sıfır/negatif bir aday alınmaz.
            if score <= 0:
                break
            excerpt = _best_excerpt(_strip_frontmatter(raw), query, per_report)
            if not excerpt:
                continue
            block = f"— [{path.stem}]\n{excerpt}"
            cost = estimate_tokens(block)
            if used + cost > budget:
                block = _truncate_to_tokens(block, budget - used)
                cost = estimate_tokens(block)
                if cost <= 0:
                    break
            blocks.append(block)
            used += cost
            if used >= budget:
                break

        if not blocks:
            return None
        return ContextSection(
            title=f"🎯 {skill_name} — İlgili Rapor Alıntıları",
            body="\n\n".join(blocks),
            kind="reports",
            tokens=used,
        )

    def _project_section(self, project_dir: Optional[Path], budget: int) -> Optional[ContextSection]:
        """Aktif projenin kendi hafıza dosyası ve en güncel proje raporu."""
        if not project_dir:
            return None
        project_dir = Path(project_dir)
        from entropy.core.config import config

        parts: List[str] = []
        used = 0

        candidates = [
            project_dir / "MEMORY.md",
            Path(config.obsidian_vault_path) / "Entropy" / "Projects" / project_dir.name / "MEMORY.md",
        ]
        for cand in candidates:
            if not cand.is_file():
                continue
            try:
                text = _strip_frontmatter(cand.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
            if text:
                chunk = _truncate_to_tokens(text, budget // 2)
                parts.append(chunk)
                used += estimate_tokens(chunk)
            break

        rep_dir = Path(config.obsidian_vault_path) / "Entropy" / "Projects" / project_dir.name / "Reports"
        if rep_dir.is_dir() and used < budget:
            try:
                newest = sorted(rep_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)[:1]
            except OSError:
                newest = []
            for rf in newest:
                try:
                    body = _strip_frontmatter(rf.read_text(encoding="utf-8", errors="ignore"))
                except OSError:
                    continue
                chunk = _truncate_to_tokens(f"— [{rf.stem}]\n{body}", budget - used)
                if chunk.strip():
                    parts.append(chunk)
                    used += estimate_tokens(chunk)

        if not parts:
            return None
        return ContextSection(
            title=f"📁 Proje Bağlamı ({project_dir.name})",
            body="\n\n".join(parts),
            kind="project",
            tokens=used,
        )

    def _code_section(self, query: str, project_dir: Optional[Path], budget: int) -> Optional[ContextSection]:
        """Teknik sorgular için proje kod tabanından ilgili parçalar."""
        if not project_dir:
            return None
        technical = any(
            w in (query or "").lower()
            for w in ("kod", "dosya", "hata", "fonksiyon", "class", "test", "build", "mcp",
                      "hafıza", "rag", "terminal", "mimari", "implement", "refactor", "python")
        )
        if not technical:
            return None
        try:
            from entropy.memory.rag.project_indexer import ProjectIndexer

            indexer = ProjectIndexer(Path(project_dir))
            indexer.scan_and_index(max_files=120)
            matches = indexer.search_codebase(query, top_k=3)
        except Exception as e:
            logger.warning("Kod tabanı araması başarısız: %s", e)
            return None
        if not matches:
            return None

        lines: List[str] = []
        used = 0
        for m in matches:
            entry = f"• [{m.get('path')}] {m.get('snippet', '')}"
            cost = estimate_tokens(entry)
            if used + cost > budget:
                break
            lines.append(entry)
            used += cost
        if not lines:
            return None
        return ContextSection(
            title="İlgili Proje Kodları",
            body="\n".join(lines),
            kind="code",
            tokens=used,
        )

    def _global_memory_section(self, budget: int) -> Optional[ContextSection]:
        try:
            text = (self.vault.read_global_memory() or "").strip()
        except Exception:
            return None
        if not text:
            return None
        body = _truncate_to_tokens(text, budget)
        return ContextSection(
            title="Kalıcı Bilişsel Hafıza (MEMORY.md)",
            body=body,
            kind="global_memory",
            tokens=estimate_tokens(body),
        )

    # -- birleştirme ----------------------------------------------------

    def build(
        self,
        query: str,
        skill_name: Optional[str] = None,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
        project_dir: Optional[Path] = None,
    ) -> AssembledContext:
        """
        Bağlamı öncelik sırasına göre kurar ve bütçeyi aşmadan döndürür.

        Bir bölüm bütçesinden az yer kullanırsa artan pay sonraki bölümlere geçer;
        böylece playbook'u olmayan bir yetenekte bütçe rapor alıntılarına kayar.
        """
        ctx = AssembledContext(budget=token_budget)
        remaining = token_budget

        # Sıra = öncelik. Yordam ve proje hafızası önce gelir: ikisi de küçük,
        # spesifik ve o işe doğrudan ait. Genel recall daha geniş ve daha gürültülü
        # olduğu için sonra gelir; bütçe daralırsa ilk kırpılacak olan odur.
        plan = [
            ("playbook", min(BUDGET_PLAYBOOK, remaining),
             lambda b: self._playbook_section(skill_name, b, query) if skill_name else None),
            ("project", min(BUDGET_PROJECT, remaining),
             lambda b: self._project_section(project_dir, b)),
            ("recall", min(BUDGET_RECALL, remaining),
             lambda b: self._recall_section(query, skill_name, b)),
            ("reports", min(BUDGET_REPORTS, remaining),
             lambda b: self._reports_section(query, skill_name, b)),
            ("code", min(BUDGET_CODE, remaining),
             lambda b: self._code_section(query, project_dir, b)),
            ("global", min(BUDGET_GLOBAL_MEMORY, remaining),
             lambda b: self._global_memory_section(b)),
        ]

        for _kind, cap, producer in plan:
            if remaining <= 0:
                break
            section = None
            try:
                section = producer(min(cap, remaining))
            except Exception as e:
                logger.warning("Bağlam bölümü kurulamadı (%s): %s", _kind, e)
            if section and section.body.strip():
                ctx.sections.append(section)
                remaining -= section.tokens

        return ctx
