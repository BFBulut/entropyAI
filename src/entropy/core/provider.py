"""
Sağlayıcı soyutlaması: Entropy'nin konuştuğu CLI'ları tek arayüzde toplar.

Uygulama şimdiye dek doğrudan `AgyProcessBridge`e bağlıydı: main.py onu kuruyor,
arayüz modları `bridge.selected_model` okuyor, zamanlayıcı `send_background_task_async`
çağırıyordu. İkinci bir sağlayıcı (Claude Code CLI) eklenince bu bağların hepsinin
tek bir sözleşmeye dayanması gerekti — `ProviderBridge`.

Sözleşme kasıtlı olarak Protocol: mevcut köprü QObject'ten türüyor ve davranışı
değişmemeli; soyut taban sınıfa taşımak metaclass çakışması (QObject + ABCMeta)
ve mevcut testlerin kırılması demekti. Protocol yalnızca "bu nesne şu metotları
sağlıyor mu" sorusunu yanıtlar, kalıtım zorlamaz.

Paylaşılan davranış (bağlam doluluğu, aktarım, sağlayıcı adı) `ProviderCommonMixin`
ile gelir; iki köprü de onu miras alır, böylece bağlam baskısı mantığı tek yerde.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Protocol, runtime_checkable

# Desteklenen sağlayıcılar. "claude_api" kasıtlı olarak burada yok: API anahtarı
# tespit edilse bile ücretli olduğu için kullanıcı açıkça açmadan seçilemez
# (bkz. config.claude_api_available / EntropyConfig.provider).
PROVIDERS = ("agy", "claude")

# Sağlayıcı başına bağlam penceresi (token). AGY tarafı için 1M varsayımı
# ayarlanabilir bir tahmindir: agy pencere boyutunu bildirmiyor, bu yüzden
# doluluk oranı bir üst sınır tahmini olarak hesaplanır.
DEFAULT_CONTEXT_WINDOWS: Dict[str, int] = {
    "agy": 1_000_000,
    "claude": 200_000,
}

# Claude tarafında model başına pencere; bilinmeyen model varsayılana düşer.
CLAUDE_MODEL_CONTEXT_WINDOWS: Dict[str, int] = {
    "claude-opus-5": 200_000,
    "claude-sonnet-5": 1_000_000,
    "claude-haiku-4-5": 200_000,
}

# Bağlam bu orana ulaşınca baskı sinyali yayılır ve (varsa) aktarım sayfası yazılır.
CONTEXT_PRESSURE_THRESHOLD = 0.60

# Aktarımdan sonra yeni konuşmada tutulan tur sayısı (tur = kullanıcı + asistan).
HANDOFF_KEEP_TURNS = 4


def estimate_tokens(text: Optional[str]) -> int:
    """
    Kaba token tahmini: 4 karakter ≈ 1 token.

    Gerçek tokenizer çağırmıyoruz çünkü bu değer yalnızca doluluk oranı için
    kullanılıyor ve her turda hesaplanıyor; tokenizer yüklemek (tiktoken benzeri)
    açılışa yüzlerce ms eklerdi. Türkçe metinde bu oran biraz iyimser, bu yüzden
    eşik (%60) zaten güvenli tarafta seçildi.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def context_window_for(provider: str, model: Optional[str] = None) -> int:
    """Sağlayıcı (ve varsa model) için bağlam penceresi boyutu."""
    if provider == "claude" and model:
        for name, size in CLAUDE_MODEL_CONTEXT_WINDOWS.items():
            if model.startswith(name):
                return size
    return DEFAULT_CONTEXT_WINDOWS.get(provider, 200_000)


@runtime_checkable
class ProviderBridge(Protocol):
    """
    Entropy'nin bir CLI sağlayıcısından beklediği en küçük yüzey.

    Arayüz, zamanlayıcı ve yetenek katmanı yalnızca bu metotlara dayanır; yeni
    bir sağlayıcı eklemek için başka hiçbir dosyaya dokunmak gerekmemeli.
    """

    #: "agy" | "claude"
    provider_name: str
    selected_model: str
    #: Akıl yürütme eforu (`--effort`); geçerli kümesi effort_levels() verir.
    selected_effort: str
    active_project_dir: Path

    # --- Yürütme ---
    def send_prompt_async(self, prompt: str, **kwargs) -> None: ...

    def send_background_task_async(
        self,
        task_id: str,
        task_name: str,
        prompt: str,
        **kwargs,
    ) -> None: ...

    # --- İptal / kapanış ---
    def terminate_current_process(self) -> None: ...

    def terminate_background_task(self, task_id: str) -> None: ...

    def shutdown(self, timeout: float = 3.0) -> Dict[str, int]: ...

    # --- Durum ---
    def fetch_available_models(self) -> List[str]: ...

    def auth_status(self) -> Dict[str, object]: ...

    def set_model(self, model_name: str) -> None: ...

    # --- Efor ---
    # Seviye kümesi sağlayıcıya göre değişir (agy: low|medium|high; claude:
    # + xhigh|max). Arayüz combo'sunu bu listeden doldurur, seçileni
    # set_effort ile yazar ve mevcut seçimi selected_effort'tan okur.
    def effort_levels(self) -> List[str]: ...

    def set_effort(self, level: str) -> None: ...

    def set_project_directory(self, project_path) -> None: ...

    # --- Bağlam ---
    def context_fill_ratio(self) -> float: ...

    # --- Ajan tanımları ---
    def agent_definitions_dir(self) -> Path: ...

    def list_agent_definitions(self) -> List[str]: ...


class ProviderCommonMixin:
    """
    İki köprünün ortak davranışı: bağlam doluluğu, baskı sinyali, aktarım,
    yetenek çözümü, bilişsel bağlam/manifest üretimi ve rapor kaydı.

    QObject'ten türeyen köprülerin ÖNÜNE konur (MRO'da mixin önce gelir); kendisi
    QObject değildir, bu yüzden Qt metaclass'ıyla çakışmaz.

    Yetenek/bağlam metotları eskiden yalnızca AGY köprüsündeydi; Claude köprüsü
    sohbet yolunu tamamlarken aynı mantığı ikinci kez yazmak yerine buraya
    taşındı. AGY köprüsündeki davranış birebir korundu (metot gövdeleri aynen
    taşındı), böylece mevcut testler değişmeden geçer.
    """

    provider_name: str = "agy"

    # Bu eşiğin altında seçilen yetenek "zayıf karar" sayılır. 0,6 keyfi değil:
    # score_skill_for_prompt seçilen kararları 0,5–1,0 aralığına yerleştirir, yani
    # 0,6 seçilmiş ama eşiğin hemen üstünde kalmış ilk beşte birlik dilimdir.
    LOW_CONFIDENCE_THRESHOLD = 0.6

    # ------------------------------------------------------------------
    # Yetenek çözümü
    # ------------------------------------------------------------------

    def recent_user_turns(self, n: int = 2) -> List[str]:
        """Son n kullanıcı mesajı; sınıflandırıcının anlamsal sorgusunu zenginleştirir."""
        try:
            history = getattr(self, "conversation_history", None) or []
            turns = [m.get("content", "") for m in history if m.get("role") == "user"]
            return [t for t in turns[-n:] if isinstance(t, str) and t.strip()]
        except Exception:
            return []

    def detect_skill_for_prompt(self, prompt: str, sm=None):
        """
        Mesaj için yetenek seçer; konuşma bağlamını sınıflandırıcıya taşır.

        Tüm çağrı noktaları (bağlam kurulumu, işçi, arayüz rozeti) buradan geçer;
        böylece son yetenek önceliği ve geçmiş her yerde aynı biçimde uygulanır.
        """
        return self.score_skill_for_prompt(prompt, sm=sm)[0]

    def score_skill_for_prompt(self, prompt: str, sm=None):
        """
        Yetenek kararı ve güven puanı (0–1); `bus.skill_detected` ile de yayınlanır.

        Karar eşiğin altındaysa yetenek None döner ve güven 0,5'in altındadır;
        arayüz tek sayıya bakarak "yetenek yok" ile "zayıf eşleşme"yi ayırt edebilir.
        Eski yetenek yöneticileriyle (score_skill_for_prompt'u olmayan) çağrıldığında
        yalnızca karar döner, güven 0,0 verilir.
        """
        if sm is None:
            from entropy.skills.manager import SkillManager

            sm = SkillManager(project_dir=getattr(self, "active_project_dir", None))
        kwargs = dict(
            last_skill=getattr(self, "last_active_skill", None),
            history=self.recent_user_turns(2),
        )
        scorer = getattr(sm, "score_skill_for_prompt", None)
        if callable(scorer):
            skill, confidence = scorer(prompt, **kwargs)
        else:
            skill, confidence = sm.auto_detect_skill_for_prompt(prompt, **kwargs), 0.0
        self.last_skill_confidence = float(confidence)
        try:
            from entropy.core.event_bus import bus

            bus.skill_detected.emit(skill.name if skill else "", float(confidence))
        except Exception:
            pass
        return skill, float(confidence)

    def resolve_target_skill(self, prompt: str, active_skill: Optional[str] = None, sm=None):
        """
        Bir tur için yeteneği üç kaynaktan sırayla çözer ve kısa afişini üretir.

        Sıra: (1) arayüzün seçtiği yetenek, (2) prompt içinde açıkça çağrılmış
        `/<yetenek>` komutu, (3) anlamsal otomatik algılama. Dönüş
        `(skill, banner)`; banner kademeli açığa çıkarma gereği tek-iki satırdır
        (38 KB'lık SKILL.md prompt'a yapıştırılmaz, yolu verilir).
        """
        try:
            from entropy.skills.manager import SkillManager

            if sm is None:
                sm = SkillManager(project_dir=getattr(self, "active_project_dir", None))
            all_skills = sm.list_skills()
            skills_map = {s.name.lower(): s for s in all_skills}
            target = None
            if active_skill and active_skill.lower() not in ("auto", "otomatik", "otomatik algıla"):
                target = skills_map.get(active_skill.lower())
            if not target:
                for s in all_skills:
                    if re.search(rf'(?:^|\s)/{re.escape(s.name)}\b', prompt or "", re.IGNORECASE):
                        target = s
                        break
            if not target:
                target = self.detect_skill_for_prompt(prompt, sm=sm)
            if not target:
                return None, ""
            script_info = ""
            if getattr(target, "scripts", None):
                names = ", ".join(sc.get("name", "") for sc in target.scripts if sc.get("name"))
                if names:
                    script_info = f" (Araçlar: {names})"
            banner = (
                f"[AKTİF UZMANLIK YETENEĞİ: {target.name.upper()}]{script_info}\n"
                f"Özet: {target.description}\n"
                f"Detaylı yönergeler ve araçlar için '{target.path}' dosyasını inceleyin."
            )
            return target, banner
        except Exception:
            return None, ""

    def low_confidence_manifest_note(self, target_skill) -> str:
        """
        Zayıf yönlendirme kararında kataloğa eklenecek tek satırlık uyarı.

        Neden: yönlendirici yanılıp yeteneği yine de zorladığında model, sanki
        kullanıcı o yeteneği açıkça istemiş gibi davranıyor ve alakasız bir
        yordamı uyguluyordu. Kararın zayıf olduğunu söylemek modele yeteneği
        yok sayma iznini açıkça verir. Karar güçlüyse (veya yetenek yoksa) hiç
        satır eklenmez: her turda enjekte edilen bir metin, gereksizken token
        yakar ve güçlü kararları da sulandırır.
        """
        if target_skill is None:
            return ""
        if float(getattr(self, "last_skill_confidence", 0.0)) >= self.LOW_CONFIDENCE_THRESHOLD:
            return ""
        return (
            f"> Not: yetenek seçimi düşük güvenli "
            f"({float(self.last_skill_confidence):.2f}); gerekiyorsa yeteneksiz yanıtla."
        )

    def last_decision_summary(self) -> Dict[str, object]:
        """
        Son yönlendirme kararının tek noktadan özeti (arayüz tüketimi için).

        `/skills` gibi yerel komutlar ile rozet aynı sayıyı göstersin diye karar,
        güven ve "zayıf mı" yargısı burada birleştirilir; eşik kopyalanırsa
        arayüz ile prompt'a düşen not zamanla ayrışır.
        """
        conf = float(getattr(self, "last_skill_confidence", 0.0))
        skill = getattr(self, "last_active_skill", None)
        if not skill:
            label = "yetenek yok"
        elif conf < self.LOW_CONFIDENCE_THRESHOLD:
            label = "zayıf eşleşme"
        else:
            label = "güçlü eşleşme"
        return {
            "skill": skill,
            "confidence": round(conf, 4),
            "low_confidence": bool(skill) and conf < self.LOW_CONFIDENCE_THRESHOLD,
            "label": label,
            "text": (f"Son karar: {skill} (güven {conf:.2f}, {label})"
                     if skill else f"Son karar: yetenek yok (güven {conf:.2f})"),
        }

    def is_code_modifying_intent(self, prompt: str, mode: str = "accept-edits") -> bool:
        """Determine whether a prompt intends to modify codebase files vs pure reading/conversation."""
        if mode in ["code", "write", "mutate", "edit"]:
            return True
        if mode in ["plan", "read", "read-only"]:
            return False

        tr_map = str.maketrans("\u00e7\u011f\u0131\u00f6\u015f\u00fc\u00c7\u011e\u0130\u00d6\u015e\u00dc", "cgiosuCGIOSU")
        prompt_norm = prompt.translate(tr_map).strip().lower()

        # Check explicit commands
        if any(prompt_norm.startswith(cmd) for cmd in ["/edit", "/write", "/create", "/fix", "/patch"]):
            return True

        # Check for informational or conversational questions
        q_pattern = (
            r"\b(?:selam|merhaba|hey|nasilsin|gunaydin|iyi aksamlar|kimsin|"
            r"nedir|nasil|ne demek|acikla|ozetle|oku|goster|listele|"
            r"what is|how does|how to|explain|summarize|read|show|list|who are)\b"
        )
        is_conversational = bool(re.search(q_pattern, prompt_norm))
        if is_conversational:
            has_modifying_directive = any(re.search(rf"\b{w}", prompt_norm) for w in [
                "uygula", "kodunu yaz", "kodu yaz", "degisikligi yap", "degisiklikleri yap",
                "dosyayi guncelle", "dosyalari guncelle", "apply", "commit", "save", "fix this", "duzelt"
            ])
            if not has_modifying_directive:
                return False

        modifying_patterns = [
            # Turkish verbs with conjugated suffixes (e.g. guncelleyelim, yapalim, ekleyelim, duzeltelim...)
            r"\bguncel(?:le|leme)",
            r"\bdegis(?:tir|iklik)",
            r"\bolustur",
            r"\bduzelt",
            r"\bduzenle",
            r"\bekle",
            r"\bsil(?:me|elim|iniz|dir)?\b",
            r"\bkodla(?:ma|mak|yalim|yiniz|r misin|rmisin|\b)",
            r"\buygula",
            r"\brefakt?or",
            r"\byaz(?:alim|iniz|dir|ar misin|armisin|alim mi|\b)",
            r"(?:guncelleme|degisiklik|duzeltme|ekleme|refactor).*\byap(?:alim|iniz|ar misin|armisin|\b)",
            r"\byap(?:alim|iniz|ar misin|armisin)?\b.*(?:guncelleme|degisiklik|duzeltme|ekleme|refactor)",
            # English verbs
            r"\b(?:write|writing|rewrite)\b",
            r"\b(?:edit|editing)\b",
            r"\b(?:modify|modifying|modification)\b",
            r"\b(?:update|updating)\b",
            r"\b(?:create|creating)\b",
            r"\b(?:delete|deleting|remove|removing)\b",
            r"\b(?:fix|fixing)\b",
            r"\b(?:implement|implementing)\b",
            r"\b(?:patch|patching)\b",
            r"\b(?:refactor|refactoring)\b",
            r"\b(?:add|adding)\b",
            r"\b(?:overwrite|overwriting)\b",
        ]

        for pat in modifying_patterns:
            if re.search(pat, prompt_norm):
                return True

        compound_patterns = [
            r"(?:dosya|class|fonksiyon|script|test|kodu|modul)\s+(?:yaz|olustur|degistir|ekle|sil|duzelt|guncelle)",
            r"(?:write|create|edit|modify|add|delete|update)\s+(?:file|class|function|script|code)",
        ]
        for cp in compound_patterns:
            if re.search(cp, prompt_norm):
                return True

        return False

    # ------------------------------------------------------------------
    # Bilişsel bağlam
    # ------------------------------------------------------------------

    def get_cognitive_context(self, prompt: str, target_skill=None, token_budget: int = None) -> str:
        """
        Ajana enjekte edilecek bilişsel bağlamı üretir.

        Toplama işi CognitiveContextBuilder'a devredilmiştir. Önceki sürüm sabit
        dilimler kullanıyordu (MEMORY.md'nin ilk 750 karakteri, ilk 2 raporun ilk
        satırının ilk 180 karakteri, 4 anı). Bu seçim alakaya değil sıraya dayandığı
        için kasadaki içeriğin yaklaşık %0,17'si ve çoğu ilgisiz kısmı gidiyordu.
        Yeni yol, sabit bir token bütçesini öncelik sırasına göre doldurur:
        yetenek yordamı (playbook) > ilgili anılar > rapor alıntıları > proje > kod.

        Yetenek kataloğunun sonuna ajan kataloğu da eklenir: Entropy bir işi kendi
        yapmak yerine bir ajana devredebileceğini ancak ajanları biliyorsa önerebilir.
        """
        from entropy.core.event_bus import bus

        # Kısa selamlaşmalar ağır bağlam enjeksiyonu gerektirmez.
        is_greeting = prompt.strip().lower() in [
            "selam", "selamlar", "merhaba", "merhabalar", "hey", "nasılsın",
            "günaydın", "iyi akşamlar", "iyi geceler", "naber"
        ]
        if is_greeting and not target_skill:
            return ""

        if target_skill is None:
            try:
                from entropy.skills.manager import SkillManager
                sm = SkillManager(project_dir=getattr(self, "active_project_dir", None))
                target_skill = self.detect_skill_for_prompt(prompt, sm=sm)
            except Exception:
                pass

        parts = []
        try:
            from entropy.memory.context_builder import CognitiveContextBuilder, DEFAULT_TOKEN_BUDGET

            builder = CognitiveContextBuilder()
            ctx = builder.build(
                prompt,
                skill_name=target_skill.name if target_skill else None,
                token_budget=token_budget or DEFAULT_TOKEN_BUDGET,
                project_dir=getattr(self, "active_project_dir", None),
            )
            self.last_context_summary = ctx.summary()
            rendered = ctx.render()
            if rendered.strip():
                parts.append(rendered)
        except Exception as e:
            bus.terminal_output_received.emit(f"[Bağlam Kurulum Hatası]: {e}\n")

        # Aktif yetenek kataloğu ayrı tutulur: bütçeye tabi değildir, çünkü ajanın
        # hangi araçlara sahip olduğunu her turda eksiksiz bilmesi gerekir.
        try:
            from entropy.skills.manager import SkillManager
            sm = SkillManager(project_dir=getattr(self, "active_project_dir", None))
            manifest = sm.get_skills_manifest(active_skill=target_skill.name if target_skill else None)
            if manifest:
                note = self.low_confidence_manifest_note(target_skill)
                if note:
                    manifest = f"{manifest}\n{note}"
                parts.append(manifest)
        except Exception:
            pass

        # Ajan kataloğu: devretme kuralıyla birlikte, ~150 token'lık üst sınırla.
        agents_section = self.agents_manifest_section()
        if agents_section:
            parts.append(agents_section)

        # Ofis kataloğu: ~120 token. Ajan listesinden ayrı çünkü devretme kuralı
        # farklı: tek adımlık iş ajana, çok adımlı iş ofise gider.
        offices_section = self.offices_manifest_section()
        if offices_section:
            parts.append(offices_section)

        return "\n\n".join(parts)

    def offices_manifest_section(self) -> str:
        """
        Manifest'in "Ofisler" bölümü: ad, amaç, orkestratör + devretme kuralı.

        Entropy TÜM orkestratörleri bilir (kural 6); liste bellek ajanının
        `desk_roster()` işlevinden gelir, o yoksa kayıt defterinden. Ters yön
        yoktur: ofis ajanları Entropy'yi bilmez.
        """
        try:
            from entropy.agents.desk_registry import desk_manifest

            return desk_manifest()
        except Exception:
            return ""

    def agents_manifest_section(self) -> str:
        """
        Manifest'in "Ajanlar" bölümü: ad, rol, yetenekler + devretme kuralı.

        Kayıt defteri henüz yoksa ya da hiç ajan tanımlı değilse boş döner; ajan
        farkındalığı isteğe bağlı bir katmandır ve köprü onsuz da çalışır.
        """
        try:
            from entropy.agents.registry import agents_manifest

            return agents_manifest()
        except Exception:
            return ""

    def get_mini_cognitive_context(self, prompt: str, target_skill=None) -> str:
        """Lightweight memory retrieval for follow-up turns."""
        try:
            from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
            cog = CognitiveMemorySystem()
            q = f"{target_skill.name} {prompt}" if target_skill else prompt
            recalled = cog.recall(q, limit=2)
            if recalled:
                items = [f"• {r.get('content', '')}" for r in recalled if r.get('content')]
                if items:
                    tag = f"Bağlamsal Hafıza ({target_skill.name})" if target_skill else "Bağlamsal Hafıza"
                    return f"[{tag}]:\n" + "\n".join(items)
        except Exception:
            pass
        return ""

    # ------------------------------------------------------------------
    # Token muhasebesi
    # ------------------------------------------------------------------

    def usage_breakdown(self) -> Dict[str, int]:
        """
        Rozetin göstereceği token kalemleri; `cache_write` ayrı kalem.

        Claude `cache_creation_input_tokens` (önbelleğe YAZMA) ile
        `cache_read_input_tokens` (önbellekten OKUMA) arasında fiyat farkı var:
        yazma normal girdiden pahalı, okuma ise çok ucuz. İkisi tek "cache"
        kaleminde toplandığında rozet, pahalı bir turu ucuz gibi gösteriyordu.
        AGY tarafında yazma kalemi hiç raporlanmaz; orada 0 döner ve arayüz
        alanı gizler.
        """
        cum = getattr(self, "last_cumulative_usage", None) or {}
        return {
            "input": int(getattr(self, "latest_input_tokens", 0) or 0),
            "output": int(getattr(self, "latest_output_tokens", 0) or 0),
            "thinking": int(getattr(self, "latest_thinking_tokens", 0) or 0),
            "cache_read": int(getattr(self, "latest_cache_read_tokens", 0) or 0),
            "cache_write": int(
                getattr(self, "latest_cache_creation_tokens", 0)
                or cum.get("cache_creation_tokens", 0)
                or 0
            ),
            "session_total": int(getattr(self, "session_total_tokens", 0) or 0),
            "background_total": int(getattr(self, "background_total_tokens", 0) or 0),
        }

    def context_window_size(self) -> int:
        """Aktif sağlayıcı/model için bağlam penceresi."""
        return context_window_for(
            getattr(self, "provider_name", "agy"),
            getattr(self, "selected_model", None),
        )

    def context_used_tokens(self) -> int:
        """
        Şu an bağlamda duran tahmini token sayısı.

        İki kalemin toplamı: (1) diskteki konuşma geçmişinin metin tahmini,
        (2) son turda sağlayıcının bildirdiği girdi token'ı — sistem istemi,
        bilişsel bağlam ve araç çıktıları buraya girer ve geçmiş metninde
        görünmez, bu yüzden yalnızca geçmişe bakmak doluluğu ciddi biçimde
        eksik ölçüyordu.
        """
        history = getattr(self, "conversation_history", None) or []
        hist_tokens = 0
        for turn in history:
            try:
                hist_tokens += estimate_tokens(str(turn.get("content", "")))
            except Exception:
                continue
        last_ctx = 0
        try:
            last_ctx = int(getattr(self, "latest_input_tokens", 0) or 0)
            last_ctx += int(getattr(self, "latest_cache_read_tokens", 0) or 0)
        except Exception:
            last_ctx = 0
        return max(hist_tokens, last_ctx) + min(hist_tokens, last_ctx) // 2

    def context_fill_ratio(self) -> float:
        """Bağlam doluluk oranı (0.0–1.0+); pencere bilinmiyorsa 0.0."""
        window = self.context_window_size()
        if window <= 0:
            return 0.0
        return self.context_used_tokens() / float(window)

    def check_context_pressure(self) -> float:
        """
        Doluluğu ölçer; eşiği aştıysa sinyal yayar ve aktarımı dener.

        Sinyal her turda değil, yalnızca eşiğin ÜSTÜNE ilk çıkışta yayılır:
        aksi hâlde uzun bir oturumda arayüz her turda uyarı gösterirdi. Aktarım
        başarılıysa oran düştüğü için bayrak kendiliğinden sıfırlanır.
        """
        ratio = self.context_fill_ratio()
        if ratio < CONTEXT_PRESSURE_THRESHOLD:
            self._context_pressure_announced = False
            return ratio
        if getattr(self, "_context_pressure_announced", False):
            return ratio
        self._context_pressure_announced = True
        try:
            from entropy.core.event_bus import bus

            bus.context_pressure.emit(float(ratio))
        except Exception:
            pass
        self.compact_context_via_handoff()
        return ratio

    def compact_context_via_handoff(self) -> Optional[str]:
        """
        Geçmişi aktarım sayfasına yazıp yerel geçmişi kısaltır.

        `entropy.memory.handoff.write_handoff` memory-rag tarafından sağlanır;
        henüz yoksa (import guard) hiçbir şey yapılmaz — köprü tek başına da
        çalışmak zorunda. Yeni konuşma = aktarım sayfası + son HANDOFF_KEEP_TURNS
        tur; böylece model devam eden işi kaybetmez ama pencere boşalır.
        """
        history = list(getattr(self, "conversation_history", None) or [])
        if not history:
            return None
        try:
            from entropy.memory.handoff import write_handoff  # type: ignore
        except Exception:
            return None

        meta = {
            "provider": getattr(self, "provider_name", "agy"),
            "model": getattr(self, "selected_model", ""),
            "project": str(getattr(self, "active_project_dir", "")),
            "ratio": self.context_fill_ratio(),
        }
        try:
            page = write_handoff(history, meta)
        except Exception:
            return None
        if not page:
            return None

        keep = history[-(HANDOFF_KEEP_TURNS * 2):]
        summary = {
            "role": "system",
            "content": (
                "[Bağlam Aktarımı] Önceki konuşma sıkıştırıldı; devam sayfası: "
                f"{page}"
            ),
        }
        new_history = [summary] + keep
        lock = getattr(self, "_state_lock", None)
        if lock is not None:
            with lock:
                self.conversation_history = new_history
        else:
            self.conversation_history = new_history
        try:
            import entropy.core.config as config_module

            config_module.save_chat_history(new_history)
        except Exception:
            pass
        return str(page)


# ---------------------------------------------------------------------------
# Ajan tanımları
# ---------------------------------------------------------------------------
#
# Biçim sağlayıcıya göre değişiyor:
#   agy    -> .agents/agents/<ad>/agent.md   (YAML ön bilgi + H1 gövde)
#   claude -> .claude/agents/<ad>.md         (YAML ön bilgi: name/description/
#                                             model/effort/tools + gövde)
# İkisi de sürecin çalışma dizinine göre keşfedilir.

AGENT_DEFINITION_LAYOUT = {
    "agy": (".agents/agents", "agent.md"),
    "claude": (".claude/agents", None),
}


def agent_definitions_dir(provider: str, root: Path | str) -> Path:
    """Sağlayıcının ajan tanımlarını aradığı dizin."""
    rel, _ = AGENT_DEFINITION_LAYOUT.get(provider, AGENT_DEFINITION_LAYOUT["agy"])
    return Path(root) / rel


def list_agent_definitions(provider: str, root: Path | str) -> List[str]:
    """Diskteki ajan adlarını verir (yoksa boş liste)."""
    base = agent_definitions_dir(provider, root)
    names: List[str] = []
    try:
        if not base.is_dir():
            return names
        _, filename = AGENT_DEFINITION_LAYOUT.get(provider, AGENT_DEFINITION_LAYOUT["agy"])
        if filename:
            for child in sorted(base.iterdir()):
                if child.is_dir() and (child / filename).is_file():
                    names.append(child.name)
        else:
            for child in sorted(base.glob("*.md")):
                names.append(child.stem)
    except Exception:
        return names
    return names


# ---------------------------------------------------------------------------
# Fabrika ve çalışırken sağlayıcı değiştirme
# ---------------------------------------------------------------------------


def create_bridge(cfg=None, provider: Optional[str] = None):
    """
    Ayarlardaki (ya da açıkça verilen) sağlayıcı için köprü örneği üretir.

    main.py ve arayüz yöneticisi köprüyü artık doğrudan `AgyProcessBridge()` ile
    değil buradan kurar; sağlayıcı adı ayarlardan geldiği için ikinci bir CLI
    eklemek tek satırlık bir kayıt işi olur.
    """
    if cfg is None:
        from entropy.core.config import config as cfg  # noqa: PLW0127

    name = (provider or getattr(cfg, "provider", "agy") or "agy").strip().lower()
    if name not in PROVIDERS:
        name = "agy"

    if name == "claude":
        from entropy.core.claude_bridge import ClaudeCodeBridge

        return ClaudeCodeBridge()

    from entropy.core.agy_bridge import AgyProcessBridge

    return AgyProcessBridge()


def switch_provider(current_bridge, provider: str, cfg=None):
    """
    Çalışırken sağlayıcı değiştirir: eskisini söndürür, yenisini kurar.

    Söndürme şart: eski köprünün arka plan agy/claude süreçleri ve ledger
    satırları aksi hâlde öksüz kalır (kapanış yolundaki aynı sorun).
    Döndürülen yeni köprüyü çağıran tarafın arayüze bağlaması gerekir.
    """
    if cfg is None:
        from entropy.core.config import config as cfg  # noqa: PLW0127

    name = (provider or "").strip().lower()
    if name not in PROVIDERS:
        raise ValueError(f"Bilinmeyen sağlayıcı: {provider!r} (geçerli: {', '.join(PROVIDERS)})")

    if current_bridge is not None:
        # Süren istek ÖNCE iptal edilir: shutdown arka plan görevlerini toplar
        # ama etkileşimli sohbet turu ayrı bir süreçtir; iptal edilmezse eski
        # sağlayıcının yanıtı yeni köprünün turuymuş gibi ekrana düşerdi.
        try:
            current_bridge.terminate_current_process()
        except Exception:
            pass
        try:
            current_bridge.shutdown(timeout=3.0)
        except Exception:
            pass
        # Kilidi serbest bırak: eski köprü "çalışıyor" durumundayken
        # değiştirilirse giriş kutusu kapalı kalıyordu.
        try:
            current_bridge._is_running = False
        except Exception:
            pass

    cfg.provider = name
    # Sağlayıcıya geçerken model de o sağlayıcınınki olur. Değer DOĞRULANIR
    # (Faz 9.1): zehirlenmiş bir ayar burada `selected_model`'i de bozuyordu.
    default_model = getattr(cfg, "provider_models", {}).get(name)
    try:
        import sys as _sys

        config_mod = _sys.modules["entropy.core.config"]
        if default_model and not config_mod.is_valid_model_for(name, default_model):
            default_model = config_mod.DEFAULT_PROVIDER_MODELS.get(name, default_model)
    except Exception:
        pass
    if default_model:
        cfg.selected_model = default_model
    try:
        cfg.save_settings()
    except Exception:
        pass

    new_bridge = create_bridge(cfg, provider=name)

    # Rozetler: model/durum göstergeleri yeni sağlayıcıyı yansıtsın ve çekirdek
    # "thinking"/"error" durumunda takılı kalmasın.
    try:
        from entropy.core.event_bus import bus

        bus.model_detected.emit(getattr(new_bridge, "selected_model", "") or name)
        bus.core_state_changed.emit("idle")
    except Exception:
        pass

    return new_bridge


_EFFORT_CMD_RE = re.compile(r"^\s*/effort\b\s*(?P<arg>[A-Za-z]*)\s*$", re.IGNORECASE)


def effort_command(text: str, bridge=None) -> Optional[Dict[str, str]]:
    """
    `/effort [<seviye>]` yerel komutunu ayrıştırır.

    Geçerli seviye kümesi köprüden (`bridge.effort_levels()`) okunur; sağlayıcı
    kümesi farklı olduğu için burada sabit liste tutulmaz. Dönüş: komut değilse
    None; argümansızsa {"action": "show"}; geçerli seviyeyle
    {"action": "set", "effort": <seviye>}; geçersizle {"action": "error", ...}.

    NOT: `/effort <seviye>` bir prompt İÇİNDE geçtiğinde (ör. "kodu incele
    /effort max") köprüler onu o turluk geçersiz kılma olarak zaten okur; bu
    ayrıştırıcı yalnızca TEK BAŞINA yazılan kalıcı ayar komutunu yakalar.
    """
    if not text:
        return None
    m = _EFFORT_CMD_RE.match(text)
    if not m:
        return None
    levels = []
    try:
        levels = list(bridge.effort_levels()) if bridge is not None else []
    except Exception:
        levels = []
    arg = (m.group("arg") or "").strip().lower()
    if not arg:
        return {"action": "show"}
    if levels and arg not in levels:
        return {
            "action": "error",
            "message": f"Bilinmeyen efor '{arg}'. Geçerli: {', '.join(levels)}.",
        }
    return {"action": "set", "effort": arg}


_PROVIDER_CMD_RE = re.compile(r"^\s*/provider\b\s*(?P<arg>[A-Za-z_\-]*)\s*$", re.IGNORECASE)


def provider_command(text: str) -> Optional[Dict[str, str]]:
    """
    `/provider [agy|claude]` yerel komutunu ayrıştırır.

    Dönüş: komut değilse None; argümansızsa {"action": "show"}; geçerli adla
    {"action": "set", "provider": <ad>}; geçersiz adla {"action": "error", ...}.
    Komutun kendisi burada YÜRÜTÜLMEZ — yürütme (köprü değiştirme + arayüzü
    yeniden bağlama) çağıranın işi; ayrıştırma köprü tarafında olduğu için
    slash_commands.py ve arayüz aynı kuralı iki kez yazmak zorunda kalmaz.
    """
    if not text:
        return None
    m = _PROVIDER_CMD_RE.match(text)
    if not m:
        return None
    arg = (m.group("arg") or "").strip().lower()
    if not arg:
        return {"action": "show"}
    if arg not in PROVIDERS:
        return {
            "action": "error",
            "message": f"Bilinmeyen sağlayıcı '{arg}'. Geçerli: {', '.join(PROVIDERS)}.",
        }
    return {"action": "set", "provider": arg}
