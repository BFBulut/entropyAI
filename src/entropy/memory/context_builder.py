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
# Wiki kavram/varlık sayfaları (bkz. memory/wiki.py). Playbook'tan hemen sonra,
# rapor alıntılarından önce gelir: sayfa playbook'un o sorguya ait bölümünün
# genişletilmiş hâlidir, ham rapordan daha yoğundur. En iyi 2 sayfa alınır;
# 400 token iki kısa sayfayı taşır, üçüncüsü bütçeyi rapor alıntılarından çalar.
BUDGET_WIKI_PAGES = 400
MAX_WIKI_PAGES = 2
# Önceki oturumun aktarım sayfası. Yalnızca yeni oturumun ilk turunda ödenir
# (sayfa "tüketildi" diye işaretlenir), her turda değil: 300 token her turda
# yeniden ödenirse aktarımın kazandırdığı bağlam maliyetiyle eşitlenir.
BUDGET_HANDOFF = 300
# Aktif alt ajanın kalıcı belleği (Agents/<ajan>/MEMORY.md). Küçük tutulur:
# ajan belleği olay kaydıdır, yordam değil; kararı playbook verir.
BUDGET_AGENT_MEMORY = 300
# Aktif ofisin kalıcı belleği (Offices/<ofis>/MEMORY.md). Ajan belleğiyle aynı
# büyüklük: ofis belleği de olay kaydıdır (hangi kart nasıl notlandı), yordam
# değil. Yalnızca meta["office"] doluysa ödenir.
BUDGET_OFFICE_MEMORY = 300

# CRAG esigi (Faz 11.10). Kor testte (denetim Ek A) isabetli sorgularin top-1
# hibrit skoru 0,478-0,585 araligindaydi; tek kacirmanin top-1 skoru 0,398'di.
# 0,45 bu iki kumeyi ayiriyor. Altinda kalan sorgu icin baglam kurucusu
# "beyinde yok" sinyali verir.
CRAG_MIN_SCORE = 0.45


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
    # Faz 11.10 (CRAG kapisi): geri cagirmanin en iyi hibrit skoru. 0.0 =
    # beyinde hic karsilik yok. Cagiran (arastirma akisi, arayuz) bu sayiya
    # bakarak "beyinde yok, disariya cikmali" karari verir; onceden sistem
    # zayif sonuclari da guvenle sunuyordu.
    brain_confidence: float = 0.0

    @property
    def brain_has_answer(self) -> bool:
        """Beyinde ise yarar bir karsilik var mi (CRAG esigi)."""
        return self.brain_confidence >= CRAG_MIN_SCORE

    @property
    def tokens(self) -> int:
        return sum(s.tokens for s in self.sections)

    def render(self) -> str:
        return "\n\n".join(s.render() for s in self.sections if s.body.strip())

    def summary(self) -> Dict[str, Any]:
        return {
            "total_tokens": self.tokens,
            "budget": self.budget,
            "brain_confidence": round(self.brain_confidence, 4),
            "brain_has_answer": self.brain_has_answer,
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
            # Faz 11.10: varsayılan kapsam L2+L3 (çalışma belleği ve epizodik
            # kayıtlar dışarıda) + graf komşularıyla PPR genişletmesi.
            hits = self.memory.hybrid_recall(query, top_k=12, expand_graph=True)
        except TypeError:
            # Eski imzalı bir bellek nesnesi (test sahtesi) geçilmiş olabilir.
            hits = self.memory.hybrid_recall(query, top_k=12)
        except Exception as e:
            logger.warning("Hafıza geri çağırma başarısız: %s", e)
            self._last_recall_best = 0.0
            return None
        self._last_recall_best = max((score for _, score in hits), default=0.0)
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
        sources = list(self.playbooks.source_reports(skill_name))
        # Sorgu sayfaları da havuza girer: damıtma onları kaynak saymaz ama bir
        # sonraki tur "bunu daha önce sormuştuk" bilgisini görmelidir.
        sources.extend(self._query_pages(skill_name))
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

    def _wiki_page_files(self, skill_name: Optional[str]) -> List[Path]:
        """Yeteneğin wiki kavram/varlık sayfaları."""
        if not skill_name:
            return []
        try:
            from entropy.memory.wiki import concepts_dir, entities_dir
        except Exception:
            return []
        out: List[Path] = []
        for d in (concepts_dir(skill_name, self.playbooks.vault_path),
                  entities_dir(skill_name, self.playbooks.vault_path)):
            if d.is_dir():
                out.extend(sorted(d.glob("*.md")))
        return out

    # Kırpılmış bir kavram sayfasının anlamlı kalabileceği asgari pay (token).
    # Bunun altında sayfa hiç alınmaz: iki satırlık bir kalıntı bağlamda yer
    # kaplar ama karar değiştirmez.
    MIN_WIKI_PAGE_TOKENS = 120

    def _wiki_pages_section(
        self, query: str, skill_name: Optional[str], budget: int,
        exclude_text: str = "",
    ) -> Optional[ContextSection]:
        """
        Sorguya en yakın en fazla MAX_WIKI_PAGES wiki sayfasını bağlama koyar.

        Sıralama rapor alıntılarıyla aynı iki aşamalı yolu izler: önce sözcüksel
        isabet, hiç isabet yoksa gömme benzerliği (`_semantic_rank`).

        `exclude_text` o ana kadar kurulmuş bağlamdır: playbook bölümü zaten
        aynı metni taşıyorsa sayfa alınmaz. Kavram sayfası playbook'un bir
        bölümünden türer; ikisini birden koymak bütçenin bir dilimini aynı
        cümleler için iki kez ödemek olur.
        """
        pages = self._wiki_page_files(skill_name)
        if not pages:
            return None
        terms = {t for t in re.findall(r"\w+", (query or "").lower()) if len(t) >= 3}
        scored: List[tuple] = []
        for p in pages:
            try:
                raw = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            low = raw.lower()
            hits = sum(low.count(t) for t in terms) if terms else 0
            scored.append((hits, p, raw))
        scored.sort(key=lambda x: x[0], reverse=True)
        if not scored or scored[0][0] == 0:
            scored = self._semantic_rank(query, scored)
            if not scored:
                return None

        blocks: List[str] = []
        picked: List[str] = []
        used = 0
        # Eleme sıralamadan SONRA yapılır ama tavan elemeden sonra uygulanır:
        # ilk iki aday playbook'ta zaten varsa sıradaki sayfalara bakılmalı,
        # yoksa bölüm boş döner (ölçüldü: 3 sorguda da 0 sayfa geliyordu).
        for score, path, raw in scored:
            if score <= 0 or len(blocks) >= MAX_WIKI_PAGES:
                break
            body = _strip_frontmatter(raw)
            # Başlık satırı ve "## İlgili"/"## Kaynaklar" bölümleri bağ
            # listesidir: bağlamda bilgi taşımaz, yalnızca token yer.
            body = re.split(r"(?m)^##\s+(?:İlgili|Kaynaklar)\s*$", body)[0].strip()
            if not body:
                continue
            if exclude_text and self._already_covered(body, exclude_text):
                continue
            block = f"— [{path.stem}]\n{body}"
            cost = estimate_tokens(block)
            if used + cost > budget:
                # Bütçeye sığmayan sayfa kırpılır; kalan pay bir sayfanın
                # anlamlı kalması için gereken tabanın altındaysa hiç alınmaz.
                room = budget - used
                if room < self.MIN_WIKI_PAGE_TOKENS:
                    continue
                block = _truncate_to_tokens(block, room)
                cost = estimate_tokens(block)
            blocks.append(block)
            picked.append(path.stem)
            used += cost
        if not blocks:
            return None
        return ContextSection(
            title=f"📗 {skill_name} — Wiki Sayfaları",
            body="\n\n".join(blocks),
            kind="wiki_pages",
            tokens=used,
        )

    @staticmethod
    def _already_covered(body: str, context_text: str) -> bool:
        """
        Sayfa gövdesi mevcut bağlamda zaten var mı (kaba ama ucuz ölçü).

        İlk anlamlı satırın normalize edilmiş hâli bağlamda geçiyorsa sayfa
        kopya sayılır; playbook bölümüyle kavram sayfası birebir aynı metni
        taşıdığı için bu tek satır ayrımı yapmaya yeter.
        """
        probe = ""
        for line in (body or "").splitlines():
            s = re.sub(r"\s+", " ", line.strip())
            if len(s) >= 25:
                probe = s[:80]
                break
        if not probe:
            return False
        return probe in re.sub(r"\s+", " ", context_text)

    def _query_pages(self, skill_name: Optional[str]) -> List[Path]:
        """Yeteneğin ve kasa genelinin wiki sorgu sayfaları (en yeniler önce)."""
        try:
            from entropy.memory.wiki import queries_dir
        except Exception:
            return []
        out: List[Path] = []
        for skill in (skill_name, None):
            d = queries_dir(skill, self.playbooks.vault_path)
            if d.is_dir():
                out.extend(sorted(d.glob("*.md"), key=lambda p: p.name, reverse=True))
        return out

    def _agent_memory_section(self, agent: Optional[str], budget: int) -> Optional[ContextSection]:
        """Aktif alt ajanın öğrendikleri ve son görevleri."""
        if not agent or not str(agent).strip():
            return None
        try:
            from entropy.memory.agent_memory import load_agent_memory

            body = load_agent_memory(
                str(agent), budget_tokens=budget, vault_path=self.playbooks.vault_path
            )
        except Exception as e:
            logger.warning("Ajan belleği okunamadı (%s): %s", agent, e)
            return None
        if not body.strip():
            return None
        body = _truncate_to_tokens(body, budget)
        return ContextSection(
            title=f"🤖 Ajan Belleği ({agent})",
            body=body,
            kind="agent_memory",
            tokens=estimate_tokens(body),
        )

    def _office_memory_section(self, office: Optional[str], budget: int) -> Optional[ContextSection]:
        """Aktif ofisin öğrendikleri ve son kart notları (meta["office"] varsa)."""
        if not office or not str(office).strip():
            return None
        try:
            from entropy.memory.agent_memory import load_office_memory

            body = load_office_memory(
                str(office), budget_tokens=budget, vault_path=self.playbooks.vault_path
            )
        except Exception as e:
            logger.warning("Ofis belleği okunamadı (%s): %s", office, e)
            return None
        if not body.strip():
            return None
        body = _truncate_to_tokens(body, budget)
        return ContextSection(
            title=f"🏢 Ofis Belleği ({office})",
            body=body,
            kind="office_memory",
            tokens=estimate_tokens(body),
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

    def _handoff_section(self, budget: int, consume: bool = True) -> Optional[ContextSection]:
        """
        Önceki oturumun aktarım sayfasından "Önceki oturum" bölümü.

        Sayfanın tamamı değil, bir sonraki oturumun gerçekten ihtiyaç duyduğu dört
        bölüm alınır: hedef, açık işler, sonraki adım, alınan kararlar. Dokunulan
        dosyalar ve kaynaklar bilerek dışarıda: onlar zaten proje/rapor
        bölümlerinden ve geri çağırmadan geliyor, burada 300 token'ı yerlerdi.
        """
        try:
            from entropy.memory.handoff import (
                SECTION_TITLES,
                mark_handoff_consumed,
                pending_handoff,
            )
        except Exception:
            return None

        page = pending_handoff(self.playbooks.vault_path)
        if not page:
            return None

        sections = page.get("sections") or {}
        lines: List[str] = []
        for key in ("hedef", "acik_isler", "sonraki_adim", "kararlar"):
            items = sections.get(key) or []
            if not items:
                continue
            lines.append(f"{SECTION_TITLES.get(key, key)}: " + "; ".join(items[:3]))
        if not lines:
            return None

        body = _truncate_to_tokens("\n".join(lines), budget)
        if not body.strip():
            return None
        if consume:
            mark_handoff_consumed(page["path"])
        return ContextSection(
            title=f"Önceki Oturum ({Path(page['path']).stem})",
            body=body,
            kind="handoff",
            tokens=estimate_tokens(body),
        )

    # -- birleştirme ----------------------------------------------------

    def build(
        self,
        query: str,
        skill_name: Optional[str] = None,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
        project_dir: Optional[Path] = None,
        include_handoff: bool = True,
        meta: Optional[Dict[str, Any]] = None,
    ) -> AssembledContext:
        """
        Bağlamı öncelik sırasına göre kurar ve bütçeyi aşmadan döndürür.

        Bir bölüm bütçesinden az yer kullanırsa artan pay sonraki bölümlere geçer;
        böylece playbook'u olmayan bir yetenekte bütçe rapor alıntılarına kayar.
        """
        ctx = AssembledContext(budget=token_budget)
        remaining = token_budget
        # CRAG kapisi icin geri cagirmanin en iyi skoru; _recall_section doldurur.
        self._last_recall_best = 0.0
        agent = (meta or {}).get("agent")
        office = (meta or {}).get("office")

        # Sıra = öncelik. Yordam ve proje hafızası önce gelir: ikisi de küçük,
        # spesifik ve o işe doğrudan ait. Genel recall daha geniş ve daha gürültülü
        # olduğu için sonra gelir; bütçe daralırsa ilk kırpılacak olan odur.
        plan = [
            # Aktarım en başta: "geçen sefer nerede kalmıştık" bilgisi olmadan
            # kurulan diğer bölümler doğru olsa bile yanlış işe hizmet eder.
            # Bekleyen sayfa yoksa üretici None döner ve hiç yer kaplamaz.
            ("handoff", min(BUDGET_HANDOFF, remaining),
             lambda b: self._handoff_section(b) if include_handoff else None),
            ("playbook", min(BUDGET_PLAYBOOK, remaining),
             lambda b: self._playbook_section(skill_name, b, query) if skill_name else None),
            # Wiki sayfaları playbook'un hemen ardından: aynı yordamın sorguya
            # ait bölümünün genişletilmiş hâli, ham rapordan daha yoğun.
            ("wiki_pages", min(BUDGET_WIKI_PAGES, remaining),
             lambda b: self._wiki_pages_section(
                 query, skill_name, b, exclude_text=ctx.render()) if skill_name else None),
            # Ajan belleği playbook'tan hemen sonra: "bu ajan bunu daha önce
            # denedi" bilgisi, proje ve geri çağırmadan daha spesifiktir.
            ("agent_memory", min(BUDGET_AGENT_MEMORY, remaining),
             lambda b: self._agent_memory_section(agent, b)),
            # Ofis belleği ajan belleğinden hemen sonra: ajanın kendi geçmişi
            # daha spesifik, ofisin ortak belleği bir adım daha genel.
            ("office_memory", min(BUDGET_OFFICE_MEMORY, remaining),
             lambda b: self._office_memory_section(office, b)),
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

        ctx.brain_confidence = float(getattr(self, "_last_recall_best", 0.0))
        return ctx
