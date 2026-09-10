"""Antigravity (AGY) CLI asynchronous bridge, persistent conversation resumption, and cognitive memory awareness."""

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, List, Dict, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from entropy.core.event_bus import bus
import sys as _sys
import entropy.core.config  # noqa: F401  (alt modulun yuklenmesi icin)
# entropy.core paketi 'config' adini config NESNESINE baglar; sohbet
# gecmisi yardimcilari icin gercek modul gerekiyor.
config_module = _sys.modules["entropy.core.config"]
from entropy.core.config import config, CHAT_HISTORY_FILE
from entropy.core.task_ledger import task_ledger, TaskStatus
from entropy.core.project_lock import LOCK_TIMEOUT_MARKER, project_lock_manager

# Arka plan görevinin proje kilidini bekleyeceği süre (sn). Modül düzeyinde:
# testler gerçek kilit çakışmasını makul sürede sürebilsin diye.
BACKGROUND_LOCK_TIMEOUT = 60.0

# Arka plan görevi başına araç adımı tavanı (Faz 7 / C2c). `send_background_task_async`
# `max_steps` almazsa sayaç KAPALIDIR: yalnızca kart koşumları (ofis alt kartları)
# açıkça sınır verir; etkileşimli sohbetin uzun araç zincirini kesmek istemiyoruz.
# İstem içindeki "en çok N araç adımı" kuralı bir ricadır ve model onu düzenli
# olarak aşıyordu; bu sayaç yaptırımdır.
DEFAULT_MAX_TOOL_STEPS = 20
MAX_STEPS_MARKER = "[ADIM SINIRI]"
from entropy.core.masking import mask_tool_output
import entropy.core.provider as provider_mod
from entropy.core.provider import (
    INTERACTIVE_IDLE_TIMEOUT_S,
    InteractiveSession,
    InteractiveSessionRegistry,
    ProviderCommonMixin,
    agent_definitions_dir as _agent_definitions_dir,
    followup_rejection,
    list_agent_definitions as _list_agent_definitions,
)

def is_trailing_sentence_word(word: str) -> bool:
    w = re.sub(r'[^a-zA-Z0-9çğıöşüÇĞİÖŞÜ]', '', word.lower())
    if not w:
        return True
    tr_map = str.maketrans("çğıöşü", "cgiosu")
    w_norm = w.translate(tr_map)
    sentence_prefixes = (
        "proje", "klasor", "dizin", "gelis", "kod", "olustur", "yap", "yaz",
        "test", "dosya", "icin", "ile", "veya", "lutfen", "calis", "alan",
        "konum", "kaydet", "tasi", "kopyala"
    )
    exact_stopwords = {
        "ve", "ile", "icin", "is", "in", "to", "and", "the", "for", "with",
        "about", "create", "build", "develop", "run", "test", "write", "make"
    }
    if w_norm in exact_stopwords:
        return True
    if any(w_norm.startswith(p) for p in sentence_prefixes):
        return True
    return False


def extract_windows_paths(text: str) -> List[Path]:
    """Extract Windows absolute directory paths from user prompt text."""
    found: List[Path] = []
    if not text or ":" not in text:
        return found

    # 1. Quoted paths (highest precedence: explicit quotes define boundaries)
    for m in re.findall(r'["\']([A-Za-z]:\\[^"\'\r\n<>|*?]+)["\']', text):
        clean = m.strip()
        try:
            p = Path(clean).resolve()
            if p not in found:
                found.append(p)
        except Exception:
            pass

    # 2. Match any candidate sequence starting with drive letter
    for m in re.findall(r'(?:^|[\s(])([A-Za-z]:\\[^"\'\r\n<>|*?]+)', text):
        cand = m.strip().rstrip(".,;:)")
        # Check if the full candidate exists on disk
        try:
            p = Path(cand).resolve()
            if p.exists():
                if p not in found:
                    found.append(p)
                continue
        except Exception:
            pass

        # If candidate doesn't exist as-is, peel off trailing words from right to left to see if prefix exists on disk
        parts = cand.split()
        matched_existing = False
        for i in range(len(parts) - 1, 0, -1):
            sub_cand = " ".join(parts[:i]).rstrip(".,;:)")
            try:
                sub_p = Path(sub_cand).resolve()
                if sub_p.exists():
                    if sub_p not in found:
                        found.append(sub_p)
                    matched_existing = True
                    break
            except Exception:
                pass

        if matched_existing:
            continue

        # 3. If it doesn't exist on disk at all (e.g. a new project path being created):
        # Collect tokens starting from parts[0], stopping immediately when a sentence word is met or file extension reached
        first_token = parts[0].rstrip(".,;:)") if parts else ""
        if not first_token:
            continue
        path_tokens = [first_token]
        if not re.search(r'\.[a-zA-Z0-9]{1,5}$', first_token):
            for token in parts[1:4]:
                clean_tok = token.rstrip(".,;:)")
                if is_trailing_sentence_word(clean_tok):
                    break
                path_tokens.append(clean_tok)
                if re.search(r'\.[a-zA-Z0-9]{1,5}$', clean_tok):
                    break

        chosen_str = " ".join(path_tokens).rstrip(".,;:)")
        try:
            chosen = Path(chosen_str).resolve()
            if chosen not in found:
                found.append(chosen)
        except Exception:
            pass

    return found


# Windows'ta CreateProcess komut satırı 32.767 karakterle sınırlı. Prompt bu sınıra
# yaklaşınca (yordam damıtma: 24 rapor ≈ 60k karakter) agy "[WinError 206] The
# filename or extension is too long" ile hiç başlamıyordu. Bu eşiğin üstündeki
# prompt'lar argv yerine stdin'den, agy'nin --input-format stream-json NDJSON
# biçimiyle verilir.
#
# Eşik, sohbet işçisinin zaten uyguladığı güvenli yükle aynı (26.500): işçi sistem
# bağlamını kırparak yükü bu değerin altında tutar ve kullanıcı metnine dokunmaz
# (test_windows_32kb_limit_never_truncates_user_prompt). Böylece olağan sohbetler
# kanıtlanmış argv yolunda kalır; stdin yalnızca kırpmanın çare olmadığı, kırpma
# uygulanmayan arka plan prompt'ları (damıtma, konsolidasyon) için devreye girer.
ARGV_PROMPT_SAFE_LIMIT = 26_500


def build_stdin_prompt_payload(prompt: str) -> str:
    """
    agy --input-format stream-json için tek satırlık kullanıcı mesajı üretir.

    Şema, kotasız problarla doğrulandı: {"event":"user","message":{"role":"user",
    "content":"..."}}. Eksik "event" / "message" / "content" alanları agy
    tarafından tur başlatılmadan reddedilir.
    """
    return json.dumps(
        {"event": "user", "message": {"role": "user", "content": prompt}},
        ensure_ascii=False,
    ) + "\n"


def prompt_via_stdin(prompt: str) -> bool:
    return len(prompt or "") > ARGV_PROMPT_SAFE_LIMIT


# `agy -p --help` bir `--effort low|medium|high` bayrağı gösterir AMA agy'nin
# modelleri eforu ADLARINA GÖMER (`gemini-3.8-flash-high`). İkisi birlikte
# verilince CLI turu hiç başlatmaz:
#   error: invalid model selection (--model "gemini-3.8-flash-high"
#   --effort "medium"): --model gemini-3.8-flash-high conflicts with
#   --effort=medium
# Bu yüzden argv'ye `--effort` HİÇ yazılmaz; efor model adıyla ifade edilir.
# Bu liste yalnızca eski ayarların onarımı için "bilinen seviye kümesi"dir;
# bir modelin GERÇEK seçenekleri `effort_levels()` ile katalogdan gelir.
AGY_EFFORT_LEVELS = ["low", "medium", "high"]
DEFAULT_AGY_EFFORT = "high"


class AgyProcessBridge(ProviderCommonMixin, QObject):
    """
    Bridges Entropy AI to the authenticated local Antigravity (agy) CLI.

    `ProviderCommonMixin` yalnızca ORTAK davranışı (bağlam doluluğu, baskı
    sinyali, aktarım) ekler; mevcut hiçbir metodun davranışı değişmez. Sınıf
    böylece `entropy.core.provider.ProviderBridge` sözleşmesini karşılar ve
    fabrika ile Claude köprüsünün yerine geçebilir.
    """

    provider_name = "agy"

    MODEL_PATTERNS = [
        re.compile(r"(?:Model\s+Selection|Active\s+Model|Using\s+Model|Model|Engine)\s*[:=]\s*([a-zA-Z0-9\.\-_\s\(\)]+)", re.IGNORECASE),
        re.compile(r"\[([a-zA-Z0-9\.\-_]+(?:flash|pro|sonnet|haiku|opus|codex|gpt|gemini|claude)[a-zA-Z0-9\.\-_]*)\]", re.IGNORECASE),
        re.compile(r"\bto\s+([a-zA-Z0-9\.\-_]+(?:flash|pro|sonnet|haiku|opus|codex|gpt|gemini|claude)[a-zA-Z0-9\.\-_]*)", re.IGNORECASE),
    ]

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        # OKUMA KAPISI (Faz 9.1): ayardaki model başka sağlayıcıya aitse (ör.
        # `claude-opus-5`) argv'ye geçirilmez; yedek değerin KENDİSİ de
        # doğrulanır, aksi hâlde zehirli ayar korumayı boşa çıkarıyordu.
        _default = getattr(config, "provider_models", {}).get("agy") or ""
        if not self._is_agy_model(_default):
            _default = config_module.DEFAULT_PROVIDER_MODELS["agy"]
        _current = config.selected_model or ""
        self.selected_model: str = _current if self._is_agy_model(_current) else _default
        self.current_model: str = self.selected_model or config.model_fallback_name
        # Efor MODELDEN türer: tek gerçek kaynak model adının son ekidir. Ayardaki
        # değer yalnızca model son eksizse (ör. `claude-sonnet-4-6`) veya modelde
        # o varyant yoksa devreye girer ve UYUMLU hâle onarılır — kullanıcının
        # Claude'da seçtiği "xhigh"/"max" agy'ye geçince geçersiz bir ad üretirdi.
        _model_effort = provider_mod.split_agy_model(self.selected_model)[1]
        _effort = (getattr(config, "provider_effort", {}) or {}).get("agy", "")
        self.selected_effort: str = (
            _model_effort
            or (_effort if _effort in AGY_EFFORT_LEVELS else DEFAULT_AGY_EFFORT)
        )
        if (getattr(config, "provider_effort", {}) or {}).get("agy") != self.selected_effort:
            try:
                config.provider_effort["agy"] = self.selected_effort
            except Exception:
                pass
        self.current_conversation_id: Optional[str] = config.last_conversation_id
        self.total_tokens_used: int = 0
        # Arka plan görevlerinin (damıtma, konsolidasyon, zamanlanmış araştırma)
        # uygulama oturumu boyunca harcadığı toplam. Sohbet sayaçlarından ayrı
        # tutulur: her arka plan görevi kendi AGY konuşmasıdır ve önceden hiç
        # sayılmıyordu — rozet damıtma sırasında "Tokens: 0" gösteriyordu.
        self.background_total_tokens: int = 0
        self.last_background_usage: Dict[str, int] = {}
        self.latest_input_tokens: int = 0
        self.latest_output_tokens: int = 0
        self.latest_thinking_tokens: int = 0
        self.latest_cache_read_tokens: int = 0
        self.session_total_tokens: int = 0
        self.session_cache_tokens: int = 0
        self.last_cumulative_usage: Dict[str, int] = (
            dict(config.last_cumulative_usage)
            if hasattr(config, "last_cumulative_usage") and config.last_cumulative_usage
            else {
                "input_tokens": 0,
                "output_tokens": 0,
                "thinking_tokens": 0,
                "cache_read_tokens": 0,
                "total_tokens": 0,
            }
        )
        self.session_turn_count: int = 0
        self.active_project_dir: Path = config.default_project_path
        self.conversation_history: List[Dict[str, str]] = []
        # Son turda devreye giren yetenek; "bunu slayt yap" gibi göndermeli takip
        # mesajlarında sınıflandırıcıya öncelik ipucu olarak verilir.
        self.last_active_skill: Optional[str] = None
        # Son yönlendirme kararının güven puanı (0-1); rozet gösterimi icin.
        self.last_skill_confidence: float = 0.0
        self._current_process: Optional[subprocess.Popen] = None
        self._background_processes: Dict[str, subprocess.Popen] = {}
        # Etkileşimli kartlar (Faz 10-C): ilk sonuçtan sonra da canlı kalan
        # kart süreçleri. Defter köprüye ait, sahne task_id ile erişir.
        self._interactive_sessions = InteractiveSessionRegistry()
        # Görev başına akış etiketi: `send_followup` kart bağlamını (ajan/ofis)
        # sinyalde koruyabilsin diye saklanır.
        self._interactive_stream_meta: Dict[str, dict] = {}
        # Arka plan görevi başına agy konuşma kimliği (Faz 8 / 3); ofis
        # harness'ı planlama çağrısından sonra buradan okur. `on_result`
        # sözleşmesi (metin, başarı) kimliği taşıyamıyor.
        self._background_conversations: Dict[str, str] = {}
        # Konuşma başına en son görülen KÜMÜLATİF usage; sürdürülen turun
        # gerçek maliyeti bunun farkıdır.
        self._conversation_usage_base: Dict[str, Dict[str, int]] = {}
        self._is_running: bool = False
        # Kapanış bayrağı: shutdown() sonrası hiçbir yeni agy süreci başlamamalı.
        # Aksi hâlde aboutToQuit ile süreç sonu arasında sıraya girmiş bir görev
        # tam da öldürdüğümüz ağacın yerine yenisini doğurur.
        self._shutting_down: bool = False
        # Kapanışta beklenecek yan iş parçacıkları (RAG ısıtma/indeksleme gibi).
        # Yalnızca zayıf takip: hepsi daemon, join yalnızca bütçe elverdiğince.
        self._side_threads: List[threading.Thread] = []
        self._prompt_queue: List[Tuple[str, Optional[List[str]], str]] = []
        self._lock = threading.Lock()
        # Süreç durumundan (self._lock) ayrı bir kilit: sohbet geçmişi ve token
        # sayaçları işçi iş parçacıklarından güncelleniyor. Aynı kilidi kullanmak
        # dosya yazımını süreç sonlandırmayla sıraya sokar; ayrı kilit ikisini
        # bağımsız tutar. Sayaç güncellemesi (x += n) atomik değildir: iki arka
        # plan görevi aynı anda bittiğinde biri diğerinin katkısını siler.
        self._state_lock = threading.Lock()
        # Bağlam baskısı sinyali eşiği ilk aşışta bir kez yayılır (bkz. mixin).
        self._context_pressure_announced = False

        # Sohbet geçmişi tek kaynaktan (config yardımcıları) yüklenir; arayüz
        # modları da aynı fonksiyonu kullanır, böylece köprü ve ekranlar ayrışmaz.
        self.conversation_history = config_module.load_chat_history()


    def _apply_stdin_prompt(self, cmd: List[str], force: bool = False) -> Optional[str]:
        """
        Uzun prompt'u argv'den çıkarıp stdin NDJSON yüküne çevirir.

        cmd içindeki "-p <prompt>" çiftini bulur; prompt ARGV_PROMPT_SAFE_LIMIT'i
        aşıyorsa argümanı boşaltır, "--input-format stream-json" ekler ve
        Popen'e yazılacak satırı döndürür. Aşmıyorsa cmd'ye dokunmaz, None döner.

        force=True (etkileşimli kart): uzunluğa BAKILMAZ. İlk istem de stdin'den
        gider, çünkü takip mesajlarının aynı borudan akabilmesi için sürecin
        `--input-format stream-json` ile başlaması gerekir.
        """
        try:
            idx = cmd.index("-p")
        except ValueError:
            return None
        if idx + 1 >= len(cmd) or not (force or prompt_via_stdin(cmd[idx + 1])):
            return None
        payload = build_stdin_prompt_payload(cmd[idx + 1])
        cmd[idx + 1] = ""
        if "--input-format" not in cmd:
            cmd.extend(["--input-format", "stream-json"])
        return payload

    @staticmethod
    def _feed_stdin(proc, payload: Optional[str], keep_open: bool = False):
        """
        Yükü sürecin stdin'ine ayrı bir iş parçacığından yazıp kapatır.

        Yazım neden bu iş parçacığında yapılmıyor: stdin'e büyük bir yük (uzun
        prompt + bilişsel bağlam, yüzlerce KB) yazarken boru tamponu dolarsa
        write() bloke olur. Çağıran ise henüz stdout'u okumaya başlamamıştır;
        agy bu sırada 64 KB'lık stdout tamponunu doldurursa iki taraf da
        birbirini bekler ve görev asılı kalır (klasik boru kilitlenmesi).
        Yazımı arka plana alarak okuma döngüsü hemen başlayabilir.

        keep_open=True (etkileşimli kart): yük yazıldıktan sonra stdin KAPANMAZ;
        takip mesajları aynı borudan gider. Kapatmayı oturum (`close`) üstlenir.
        """
        if not payload or getattr(proc, "stdin", None) is None:
            return

        def _writer():
            try:
                proc.stdin.write(payload)
                proc.stdin.flush()
            except Exception:
                pass
            finally:
                if keep_open:
                    return
                try:
                    proc.stdin.close()
                except Exception:
                    pass

        t = threading.Thread(target=_writer, name="agy-stdin-writer", daemon=True)
        t.start()
        return t

    @property
    def is_running(self) -> bool:
        return self._is_running

    def reset_conversation(self):
        """Start a fresh conversation topic in Antigravity and clear local chat history."""
        self.current_conversation_id = None
        config.last_conversation_id = None
        self.last_cumulative_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "thinking_tokens": 0,
            "cache_read_tokens": 0,
            "total_tokens": 0,
        }
        config.last_cumulative_usage = dict(self.last_cumulative_usage)
        config.save_settings()

        # Eski sohbet silinmez, arşive taşınır: kullanıcı yanlışlıkla "+ Yeni
        # Sohbet"e bastığında geçmişi .entropy/chat_archive/<zaman>.json'da kalır.
        self.last_archived_chat = config_module.archive_chat_history()
        self.conversation_history = []

        self.total_tokens_used = 0
        self.latest_input_tokens = 0
        self.latest_output_tokens = 0
        self.latest_thinking_tokens = 0
        self.latest_cache_read_tokens = 0
        self.session_total_tokens = 0
        self.session_cache_tokens = 0
        self.session_turn_count = 0
        self._prompt_queue.clear()
        bus.token_usage_updated.emit(0)
        arch_note = f" Önceki sohbet arşive alındı: {self.last_archived_chat}" if self.last_archived_chat else ""
        bus.terminal_output_received.emit(
            "\n[Entropy Core] Yeni diyalog oturumu başlatıldı. "
            f"(Kalıcı bilişsel hafıza ve bilgi grafiği korunuyor){arch_note}\n"
        )
        # Açık pencerelerin hepsi temizlensin: geçmiş yalnızca burada, kullanıcının
        # bilinçli isteğiyle sıfırlanır.
        bus.chat_history_cleared.emit()

    @staticmethod
    def _is_agy_model(name: str) -> bool:
        """
        Ad `agy --model`e verilebilir mi (Faz 9.1).

        Canlı liste tek doğru kaynak: `fetch_available_models()` `agy models`
        çıktısını `config.available_models`'a yazıyor (kota harcamaz). Liste
        alınamamışsa bilinen `gemini-*`/`gpt-*` ön ekleri ve agy'nin sunduğu
        claude adları devreye girer.
        """
        return config_module.is_agy_model_name(
            name, extra=list(getattr(config, "available_models", []) or [])
        )

    def set_model(self, model_name: str) -> bool:
        """
        YAZMA KAPISI (Faz 9.1): agy'ye ait olmayan adı reddeder.

        Üst çubuğun model kutusu serbest metin kabul ediyor; yabancı ad ayara
        yazıldığında sonraki her koşu geçersiz `--model` ile başlıyordu.
        """
        name = (model_name or "").strip()
        if not self._is_agy_model(name):
            bus.terminal_output_received.emit(
                f"\n[Model Reddedildi]: '{model_name}' bir AGY modeli değil; "
                f"seçim '{self.selected_model}' olarak kaldı.\n"
            )
            return False
        self.selected_model = name
        self.current_model = name
        # Efor model adının son ekidir: model değişince efor rozeti de değişir,
        # aksi hâlde kutu `pro-low` modelinde "high" göstermeye devam ederdi.
        _eff = provider_mod.split_agy_model(name)[1]
        if _eff:
            self.selected_effort = _eff
            try:
                config.provider_effort["agy"] = _eff
            except Exception:
                pass
        config.selected_model = name
        try:
            config.provider_models["agy"] = name
        except Exception:
            pass
        config.save_settings()
        bus.model_detected.emit(name)
        return True

    def model_for_run(self, model_name: Optional[str]) -> str:
        """Bu koşuda kullanılacak `--model` (kart modeli > oturum modeli)."""
        name = (model_name or "").strip()
        if name and self._is_agy_model(name):
            return name
        return self.selected_model

    def known_agy_models(self) -> List[str]:
        """Efor varyantlarını çözerken kullanılacak model kataloğu (canlı > yedek)."""
        live = [str(m) for m in (getattr(config, "available_models", []) or [])]
        return live or list(provider_mod.FALLBACK_AGY_MODELS)

    def effort_levels(self) -> List[str]:
        """
        Seçili modelin TABANI için gerçekten var olan efor varyantları.

        agy'de efor model adının son ekidir; sabit bir üçlü liste yanlıştı:
        `gemini-3.1-pro` yalnızca low/high sunuyor, `claude-sonnet-4-6` hiç efor
        sunmuyor. Arayüz kutusu bu listeyle doldurulur; boşsa kutu gizlenmeli.
        """
        return provider_mod.effort_levels_for(
            "agy", self.selected_model, available=self.known_agy_models()
        )

    def set_effort(self, level: str) -> bool:
        """
        Kalıcı efor seviyesini ayarlar — agy'de bu MODELİ DEĞİŞTİRMEK demektir.

        Dönüş True: seçim uygulandı. Geçersiz seviye (o modelde böyle bir varyant
        yok) ValueError yükseltir; arayüz kutusu zaten `effort_levels()` ile
        doldurulduğu için buraya ancak eski/zehirli bir ayar düşer.
        """
        low = (level or "").strip().lower()
        levels = self.effort_levels()
        if not levels:
            raise ValueError(
                f"'{self.selected_model}' modelinde efor seçimi yok "
                f"(efor model adının son ekidir)."
            )
        if low not in levels:
            raise ValueError(
                f"Geçersiz efor '{level}'. Geçerli: {', '.join(levels)}."
            )
        self.selected_effort = low
        new_model = provider_mod.compose_agy_model(
            self.selected_model, low, available=self.known_agy_models()
        )
        self.selected_model = new_model
        self.current_model = new_model
        try:
            config.selected_model = new_model
            config.provider_models["agy"] = new_model
            config.provider_effort["agy"] = low
            config.save_settings()
        except Exception:
            pass
        try:
            bus.model_detected.emit(new_model)
        except Exception:
            pass
        return True

    def effort_for_prompt(
        self, prompt: str, boost: bool = False, default_effort: Optional[str] = None
    ) -> Optional[str]:
        """
        Bu tur icin istenen efor: istemdeki `/effort <seviye>` > boost >
        `default_effort` (bu kosuya ACIKCA verilen modelin son eki) > kalici.

        `default_effort` neden var: agy'de efor model adinin son ekidir. Kart
        `gemini-3.8-flash-medium` sectiginde ust cubugun kalici eforu ("low")
        bu son eki eziyordu; canli kosumda argv `--model gemini-3.8-flash-low`
        cikiyordu (kartin modeli yurutmeye hic gecmiyordu). Acik secim kalici
        ayardan gucludur; yalniz istemdeki `/effort` ve boost onu asar.

        Donus None: modelin son ekine dokunma (efor varyanti olmayan modeller).
        """
        levels = self.effort_levels()
        if not levels:
            return None
        m = re.search(r'(?:^|\s)/effort\s+([A-Za-z]+)\b', prompt or "", re.IGNORECASE)
        if m and m.group(1).lower() in levels:
            return m.group(1).lower()
        if boost or re.search(r'(?:^|\s)/boost\b', prompt or "", re.IGNORECASE) or any(
            k in (prompt or "").lower()
            for k in ["otonom kodlama", "proje geliştir", "geliştir", "boost",
                      "teamwork", "subagent", "alt ajan"]
        ):
            return "high" if "high" in levels else levels[-1]
        if default_effort and default_effort in levels:
            return default_effort
        return self.selected_effort if self.selected_effort in levels else None

    def _explicit_run_effort(self, model_name):
        """Bu kosuya ACIKCA verilen modelin efor son eki (yoksa None)."""
        name = (model_name or "").strip()
        if not name or not self._is_agy_model(name):
            return None
        return provider_mod.split_agy_model(name)[1] or None

    def apply_effort_to_model(self, model_name: str, effort: Optional[str]) -> str:
        """Model adının efor son ekini bu turluk `effort` ile değiştirir."""
        name = (model_name or "").strip()
        if not name or not effort:
            return name
        return provider_mod.compose_agy_model(
            name, effort, available=self.known_agy_models()
        )

    def fetch_available_models(self) -> List[str]:
        """Dynamically fetch supported models from 'agy models' CLI."""
        agy_bin = self.find_agy_executable()
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
        try:
            res = subprocess.run(
                [agy_bin, "models"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
                timeout=10
            )
            if res.returncode == 0:
                models = []
                for line in res.stdout.splitlines():
                    line = line.strip()
                    if not line or "Fetching" in line:
                        continue
                    parts = line.split("\t")
                    model_id = parts[0].strip()
                    if model_id and model_id not in models:
                        models.append(model_id)
                if models:
                    config.available_models = models
                    return models
        except Exception:
            pass
        return config.available_models

    # Yetenek çözümü, bilişsel bağlam ve karar özeti artık
    # entropy.core.provider.ProviderCommonMixin'de: iki köprü de aynı mantığı
    # paylaşsın diye taşındı (davranış birebir aynı).

    def find_agy_executable(self) -> str:
        """Locate agy CLI binary in system PATH or default Windows installation folders."""
        path = shutil.which("agy") or shutil.which("agy.exe")
        if path:
            return path
        fallbacks = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Antigravity" / "bin" / "agy.exe",
            Path(os.environ.get("ProgramFiles", "")) / "Google" / "Antigravity" / "agy.exe",
            Path(os.environ.get("USERPROFILE", "")) / ".gemini" / "antigravity" / "bin" / "agy.exe",
        ]
        for fb in fallbacks:
            if fb.exists():
                return str(fb)
        return "agy"

    def auth_status(self) -> Dict[str, object]:
        """
        Sağlayıcının oturum durumu.

        agy'nin oturum sorgulayan bir alt komutu yok; `agy models` yalnızca
        kimlik doğrulanmışsa liste döndürdüğü için varlığı dolaylı ama güvenilir
        bir oturum kanıtı sayılır. KOTA HARCAMAZ: model listesi yerel/meta bir
        uç, model çağırmaz.
        """
        agy_bin = self.find_agy_executable()
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
        try:
            res = subprocess.run(
                [agy_bin, "models"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
                timeout=15,
            )
        except Exception as e:
            return {"provider": "agy", "logged_in": False, "error": str(e)}
        ok = res.returncode == 0 and bool((res.stdout or "").strip())
        out = {"provider": "agy", "logged_in": ok, "auth_method": "antigravity-cli"}
        if not ok:
            out["error"] = ((res.stderr or res.stdout or "").strip() or f"çıkış kodu {res.returncode}")[:300]
        return out

    def agent_definitions_dir(self) -> Path:
        """agy ajan tanımlarının dizini: <proje>/.agents/agents/"""
        return _agent_definitions_dir("agy", self.active_project_dir)

    def list_agent_definitions(self) -> List[str]:
        """Diskteki agy ajan adları (agent.md içeren alt klasörler)."""
        return _list_agent_definitions("agy", self.active_project_dir)

    def set_project_directory(self, project_path: Path | str):
        """Bind Entropy AI to a specific project folder."""
        self.active_project_dir = Path(project_path).resolve()
        config.default_project_path = self.active_project_dir
        config.save_settings()
        bus.project_changed.emit(str(self.active_project_dir))
        bus.terminal_output_received.emit(f"\n[Proje Değiştirildi]: Çalışma alanı '{self.active_project_dir.name}' ({self.active_project_dir}) olarak ayarlandı.\n")

        def _bg_index():
            try:
                from entropy.memory.rag.project_indexer import ProjectIndexer
                idx = ProjectIndexer(self.active_project_dir)
                count = idx.scan_and_index(max_files=100)
                bus.terminal_output_received.emit(f"[RAG İndeksleyici] '{self.active_project_dir.name}' projesinde {count} dosya indekslendi.\n")
            except Exception:
                pass

        warm = threading.Thread(target=_bg_index, name="entropy-rag-warmup", daemon=True)
        with self._lock:
            # Bitmiş iş parçacıklarını biriktirme; liste kapanışta gezilecek.
            self._side_threads = [t for t in self._side_threads if t.is_alive()]
            self._side_threads.append(warm)
        warm.start()


    def detect_model_from_text(self, text: str) -> Optional[str]:
        """Extract model name dynamically from text without hardcoding."""
        for pattern in self.MODEL_PATTERNS:
            match = pattern.search(text)
            if match:
                extracted = match.group(1).strip()
                if extracted and extracted != "Unknown":
                    return extracted
        return None

    # is_code_modifying_intent artık ProviderCommonMixin'de: proje kilidinin
    # okuma mı yazma mı alınacağını iki köprü de aynı kurala göre kararlaştırır.

    def _truncate_and_summarize_context(self) -> List[Dict[str, str]]:
        """Apply sliding window context truncation (RULE: agent-ui-routing)."""
        limit = config.context_window_size
        if len(self.conversation_history) <= limit:
            return self.conversation_history

        preserved = self.conversation_history[-limit:]
        older_count = len(self.conversation_history) - limit
        summary_turn = {
            "role": "system",
            "content": f"[Context Truncated: {older_count} older conversation turns were compressed to maintain optimal response latency.]"
        }
        return [summary_turn] + preserved

    def _save_chat_turn(self, user_prompt: str, assistant_resp: str):
        """Save conversation turns persistently to disk for app restart continuity."""
        try:
            CHAT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            # Kilit: sohbet turu işçi iş parçacığından ekleniyor, arka plan görevi
            # aynı anda geçmişi okuyabiliyor (recent_user_turns). Kilitsiz hâlde
            # iki tur araya girip dosyaya yarım liste yazılabiliyordu.
            with self._state_lock:
                self.conversation_history.append({"role": "user", "content": user_prompt})
                self.conversation_history.append({"role": "assistant", "content": assistant_resp})
                snapshot = list(self.conversation_history)
            config_module.save_chat_history(snapshot)
            # Diğer moddaki pencere de aynı turu görebilsin diye haber verilir.
            # Sinyal işçi iş parçacığından atılıyor; alıcılar kuyruklu bağlantı ile
            # ana iş parçacığında çalışır (alıcı QObject slotu).
            try:
                bus.chat_history_updated.emit()
            except Exception:
                pass
        except Exception:
            pass

    def send_prompt_async(
        self,
        prompt: str,
        image_attachments: Optional[List[str]] = None,
        pdf_attachments: Optional[List[str]] = None,
        active_skill: Optional[str] = None,
        mode: str = "accept-edits",
        is_background: bool = False,
        task_id: Optional[str] = None,
        task_name: Optional[str] = None,
        project_path: Optional[str] = None
    ):
        """Execute a user prompt against agy CLI, queueing if currently busy."""
        if is_background:
            if project_path:
                self.send_background_task_async(
                    task_id=task_id or "task-bg",
                    task_name=task_name or "Otonom Görev",
                    prompt=prompt,
                    mode=mode,
                    project_path=project_path
                )
            else:
                self.send_background_task_async(
                    task_id=task_id or "task-bg",
                    task_name=task_name or "Otonom Görev",
                    prompt=prompt,
                    mode=mode
                )
            return

        with self._lock:
            if self._is_running:
                self._prompt_queue.append((prompt, image_attachments, pdf_attachments, active_skill, mode, project_path))
                bus.terminal_output_received.emit(
                    f"\n[Entropy Core] Başka bir işlem yürütülüyor. Mesajınız sıraya alındı ({len(self._prompt_queue)}. sırada)...\n"
                )
                return
            self._is_running = True

        thread = threading.Thread(
            target=self._execute_prompt_worker,
            args=(prompt, image_attachments, pdf_attachments, active_skill, mode, project_path),
            daemon=True
        )
        thread.start()

    def send_background_task_async(
        self,
        task_id: str,
        task_name: str,
        prompt: str,
        mode: str = "accept-edits",
        project_path: Optional[str] = None,
        on_result: Optional[Callable[[str, bool], None]] = None,
        save_report: bool = True,
        agent: Optional[str] = None,
        needs_write: Optional[bool] = None,
        conversation_id: Optional[str] = None,
        max_steps: Optional[int] = None,
        model: Optional[str] = None,
        agent_spec: Optional[dict] = None,
        stream_meta: Optional[dict] = None,
        interactive: bool = False,
        on_followup_start: Optional[Callable[[str], object]] = None,
        on_followup_end: Optional[Callable[[str], object]] = None,
        effort: Optional[str] = None,
    ):
        """
        Execute an autonomous background task without locking the interactive user chat UI.

        interactive: etkileşimli kart kipi (Faz 10-C). True ve
        `config.desk_interactive_cards` açıksa süreç ilk `result` olayından
        sonra da CANLI kalır; kart her zamanki gibi finalize edilir (ledger,
        rapor, `task_completed`) ama sahnedeki bölmeden `send_followup` ile
        yeni turlar başlatılabilir. Bayrak kapalıysa eski davranış aynen kalır.

        on_followup_start(task_id) / on_followup_end(task_id): takip turunun
        başında ve sonunda çağrılan kancalar. Proje yazma kilidini yeniden alıp
        bırakmak harness'ın işidir (kilit API'si `agents/**` içinde); köprü
        yalnızca kancayı sunar. `on_followup_start` açıkça False dönerse takip
        mesajı gönderilmez (kilit alınamadı).

        stream_meta: `bus.agent_stream` yükünü etiketleyen bağlam
        ({"agent", "office", "card_id"}). Çağıran (ofis harness'ı / görev
        pompası) geçmezse alanlar boş kalır ve akış yine yayılır — sahne o
        olayları etiketsiz "entropy" avatarına düşürür.

        max_steps: akıştaki araç çağrısı olaylarının tavanı. Aşılırsa süreç
        `terminate_background_task` ile öldürülür ve görev `failed` biter.
        None ise sayaç kapalıdır (etkileşimli/serbest görevler).

        conversation_id: agy'nin `--conversation <id>` bayrağı. Verilirse çağrı
        AYNI agy konuşmasını sürdürür; Entropy'nin konuşma kimliği ile sağlayıcı
        oturumu `core.identity.ConversationMap` üzerinden eşlenir. None ise her
        arka plan görevi kendi sıfır bağlamıyla koşar (eski davranış).

        agent: agy'nin --agent seçeneği; araç kullanımı kısıtlı bir alt ajan (ör.
        damıtma) ile çalıştırmak için. None ise varsayılan ajan.

        on_result(full_text, success): görev bitince tam çıktıyla çağrılır. Sinyaller
        yalnızca kısa özet ve rapor yolu taşıdığı için, çıktının tamamına ihtiyaç
        duyan tüketiciler (yordam damıtma, bilişsel konsolidasyon) bunu kullanır.
        save_report=False: çıktı kasaya araştırma raporu olarak yazılmaz; ara
        ürünlerin rapor arşivini kirletmemesi ve sonraki damıtmaya kaynak olarak
        geri dönmemesi için.

        needs_write: proje kilidi türü. None ise prompt/moddan çıkarılır. False
        olduğunda PAYLAŞIMLI okuma kilidi alınır — okuma niyetli alt kartlar
        (ofis alt görevleri) tek yazma kilidi yüzünden sıraya girmesin diye;
        eskiden her arka plan görevi yazma kilidi alıyordu ve ofisin
        `max_parallel` ayarı fiilen 1'e düşüyordu.

        on_result SÖZLEŞMESİ: bu çağrı bir kez döndüyse geri çağrı MUTLAKA
        çalışır (erken dönüşler dahil). Aksi hâlde çağıranın kartı sonsuza dek
        `running` kalıyor ve ofis pompası hiç ilerlemiyordu.
        """
        with self._lock:
            if self._shutting_down:
                # Kapanış başladıktan sonra gelen görev reddedilir; başlatılsaydı
                # öksüz bir agy ağacı olarak geride kalırdı. Reddi geri çağrıya
                # bildirmek şart: sessiz dönüş çağıranı asılı bırakıyordu.
                self._notify_result(
                    on_result,
                    f"Arka plan görevi '{task_name}' başlatılmadı: köprü kapanıyor.",
                    False,
                )
                return
        thread = threading.Thread(
            target=self._execute_background_task_worker,
            args=(task_id, task_name, prompt, mode, project_path, on_result,
                  save_report, agent, needs_write, conversation_id, max_steps,
                  model, agent_spec, stream_meta, interactive,
                  on_followup_start, on_followup_end, effort),
            daemon=True
        )
        thread.start()

    def send_followup(self, task_id: str, text: str) -> bool:
        """
        Koşan bir kart sürecine stdin üzerinden ek kullanıcı mesajı gönderir.

        Sahnede bir sprite'a tıklayıp o ajanın terminaline yazmanın (10.2)
        altyapısı. agy'nin NDJSON kullanıcı olayı, uzun prompt yolunda zaten
        kullanılan `build_stdin_prompt_payload` ile birebir aynıdır — ikinci bir
        şema icat edilmez. Süreç yoksa, stdin borusu yoksa ya da kapanmışsa
        False döner (çağıran o zaman kullanıcıya "terminal kapalı" der).

        Etkileşimli kipte (Faz 10-C) mesaj oturuma verilir: işçi iş parçacığı
        uyanır, akış yeniden `working`e döner ve turun sonunda
        `bus.task_followup_completed` yayılır.
        """
        emit_stream = self._agent_stream_emitter(task_id, self._stream_meta_for(task_id))
        reason = followup_rejection(text)
        if reason:
            emit_stream("error", reason)
            return False

        session = self._interactive_sessions.get(task_id)
        if session is not None:
            if session.closed or not session.alive():
                self._interactive_sessions.pop(task_id)
                emit_stream("error", "Terminal kapalı: kartın süreci artık çalışmıyor.")
                return False
            if not session.send(str(text)):
                emit_stream("error", "Takip mesajı gönderilemedi (terminal kapalı ya da kilit alınamadı).")
                return False
            emit_stream("status", "Takip mesajı gönderildi…", state="thinking")
            return True

        # Etkileşimli olmayan (eski) yol: süreç hâlâ koşuyorsa stdin'e yazılır.
        with self._lock:
            proc = self._background_processes.get(task_id)
        stdin = getattr(proc, "stdin", None) if proc is not None else None
        if stdin is None or getattr(stdin, "closed", False):
            emit_stream("error", "Terminal kapalı: kartın süreci artık çalışmıyor.")
            return False
        try:
            stdin.write(build_stdin_prompt_payload(str(text)))
            stdin.flush()
        except Exception:
            emit_stream("error", "Terminal kapalı: kartın süreci artık çalışmıyor.")
            return False
        return True

    def _stream_meta_for(self, task_id: str) -> Optional[dict]:
        """Kart akış etiketini (ajan/ofis/kart) görev başına hatırlar."""
        with self._state_lock:
            return dict(self._interactive_stream_meta.get(task_id) or {}) or None

    def close_interactive(self, task_id: str, reason: str = "kullanıcı kapattı") -> bool:
        """
        Etkileşimli kart terminalini kapatır: stdin kapanır, süreç sonlanır.

        Kartın kendisi ilk sonuçta zaten tamamlanmıştı; bu yalnızca canlı
        kalan terminali söndürür. Bilinmeyen task_id için False.
        """
        session = self._interactive_sessions.get(task_id)
        if session is None:
            return False
        session.close(reason)
        # Süreç kendiliğinden çıkmazsa (stdin kapanınca çıkması beklenir)
        # zaman aşımıyla ağaç indirilir; işçi tarafı zaten temizliyor.
        self.terminate_background_task(task_id)
        self._interactive_sessions.pop(task_id)
        return True

    def interactive_task_ids(self) -> List[str]:
        """Şu an canlı olan etkileşimli kart terminalleri."""
        return self._interactive_sessions.active_ids()

    def _conversation_usage_delta(
        self, conversation_id: str, usage: Dict[str, int], store_only: bool = False
    ) -> Dict[str, int]:
        """
        Kümülatif konuşma usage'ını BU turun maliyetine indirger.

        Taban, aynı konuşmanın önceki turunda görülen kümülatif değerdir; yeni
        kümülatif her çağrıda saklanır. `store_only=True` yalnızca tabanı kurar
        (konuşmanın ilk turu). Negatif fark 0'a kırpılır: agy kimi zaman
        oturumu sıfırlıyor ve eksi maliyet muhasebeyi bozardı.
        """
        with self._state_lock:
            base = dict(self._conversation_usage_base.get(conversation_id) or {})
            self._conversation_usage_base[conversation_id] = dict(usage)
        if store_only or not base:
            return dict(usage)
        return {k: max(0, int(v or 0) - int(base.get(k, 0) or 0)) for k, v in usage.items()}

    def _remember_agent_session(self, agent, session_id: str) -> None:
        """
        Yakalanan oturum kimliğini ajanın kalıcı deposuna yazar (Faz 11-C.3).

        Sessizce başarısız olur: oturum kalıcılığı bir KONFOR, kartın kapanması
        ise sözleşme. Depo yazılamadığında bir sonraki koşu yeni oturum açar.
        """
        name = str(agent or "").strip()
        if not name or not session_id:
            return
        try:
            from entropy.core.identity import agent_session_store

            agent_session_store().record_captured(
                name, self.provider_name, str(session_id), cwd=os.getcwd()
            )
        except Exception:
            pass

    def background_conversation_id(self, task_id: str) -> Optional[str]:
        """Biten arka plan görevinin agy konuşma kimliği (`--conversation` girdisi)."""
        with self._lock:
            return self._background_conversations.get(task_id)

    @staticmethod
    def _notify_result(on_result, text: str, success: bool,
                       report_path: str = "") -> None:
        """Geri çağrıyı korumalı çağırır; geri çağrının hatası köprüyü düşürmez."""
        from entropy.core.provider import call_on_result

        call_on_result(on_result, text, success, report_path)

    def _execute_background_task_worker(
        self,
        task_id: str,
        task_name: str,
        prompt: str,
        mode: str = "accept-edits",
        project_path: Optional[str] = None,
        on_result: Optional[Callable[[str, bool], None]] = None,
        save_report: bool = True,
        agent: Optional[str] = None,
        needs_write: Optional[bool] = None,
        conversation_id: Optional[str] = None,
        max_steps: Optional[int] = None,
        model: Optional[str] = None,
        agent_spec: Optional[dict] = None,
        stream_meta: Optional[dict] = None,
        interactive: bool = False,
        on_followup_start: Optional[Callable[[str], object]] = None,
        on_followup_end: Optional[Callable[[str], object]] = None,
        effort: Optional[str] = None,
    ):
        emit_stream = self._agent_stream_emitter(task_id, stream_meta, model)
        # Kip bayrağı köprüde değil ayarda: kullanıcı etkileşimli kartları
        # kapattığında çağıranların hiçbirini değiştirmeden Faz 10-B davranışına
        # dönülür.
        interactive = bool(interactive) and bool(
            getattr(config, "desk_interactive_cards", True)
        )
        if interactive:
            with self._state_lock:
                self._interactive_stream_meta[task_id] = dict(stream_meta or {})
        project_dir = Path(project_path).resolve() if project_path else Path(self.active_project_dir).resolve()
        if not project_dir.exists():
            try:
                project_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

        # 1. Record task start in SQLite ledger
        task_ledger.record_task_start(
            task_id=task_id,
            task_name=task_name,
            project_path=str(project_dir),
            provider=self.provider_name,
            model=self.model_for_run(model),
        )

        # Kilit türü: çağıran açıkça söylediyse o, yoksa prompt/moddan çıkarım.
        # Okuma niyetli görevler paylaşımlı kilit alır ve birbirini beklemez.
        if needs_write is None:
            try:
                needs_write = self.is_code_modifying_intent(prompt, mode=mode)
            except Exception:
                needs_write = True

        write_acquired = False
        read_acquired = False
        # Geri çağrının bir kez ve yalnızca bir kez çalıştığının kaydı: rapor
        # yazımı sırasında patlayan bir istisna geri çağrıyı ikinci kez
        # tetiklemesin, hiç ulaşılamayan bir çıkış da onu atlamasın.
        notified = {"done": False}
        # Dış `except` de son usage'ı yazabilsin diye burada bağlanır; iç blok
        # akıştan okudukça günceller.
        task_usage: Dict[str, int] = {}
        # Birinci turun sonucu (etkileşimli kipte finalize erken çalışır).
        card_success = False
        interactive_session: Optional[InteractiveSession] = None
        try:
            if project_lock_manager.is_write_locked(project_dir):
                bus.terminal_output_received.emit(
                    f"\n[Proje Kilidi: Arka plan görevi için kilit bekleniyor ({task_name})...]\n"
                )
            if needs_write:
                write_acquired = project_lock_manager.acquire_write(project_dir, timeout=BACKGROUND_LOCK_TIMEOUT)
                acquired = write_acquired
                kind = "yazma kilidini (write lock)"
            else:
                read_acquired = project_lock_manager.acquire_read(project_dir, timeout=BACKGROUND_LOCK_TIMEOUT)
                acquired = read_acquired
                kind = "okuma kilidini (read lock)"
            if not acquired:
                err_msg = (
                    f"{LOCK_TIMEOUT_MARKER} Arka plan görevi '{task_name}' proje "
                    f"{kind} zaman aşımı nedeniyle alamadı."
                )
                bus.terminal_output_received.emit(f"\n[Proje Kilidi Hatası]: {err_msg}\n")
                task_ledger.record_task_failure(task_id=task_id, error=err_msg)
                # Geri çağrı burada da çalışmalı: kilit yüzünden hiç başlamayan
                # görev sessizce dönerse çağıranın kartı sonsuza dek `running`
                # kalıyor ve ofis pompası bir daha ilerlemiyordu.
                self._notify_result(on_result, err_msg, False)
                bus.task_completed.emit(task_id, False)
                return

            agy_bin = self.find_agy_executable()
            bus.terminal_output_received.emit(
                f"\n[⏰ Otonom Arka Plan Görevi: {task_name}] Başlatıldı...\n"
            )
            bus.core_pulse_triggered.emit(0.7)

            cmd = [
                agy_bin,
                "-p", prompt,
                "--output-format", "stream-json",
                "--mode", mode,
                "--print-timeout", "30m",
                "--dangerously-skip-permissions",
                "--add-dir", str(project_dir),
            ]
            # Kartın modeli bu koşuya uygulanır (Faz 9.5); yoksa oturum modeli.
            # Efor önceliği: prompt'taki tek seferlik `/effort <seviye>` >
            # boost/teamwork sezgisi > modelin kendi son eki. agy'de efor MODEL
            # ADININ PARÇASI olduğu için ayrı bayrak değil, ad yeniden bestelenir.
            run_model = self.model_for_run(model)
            # Faz 11-C.4: ajanın/kartın eforu agy'de AYRI BAYRAK DEĞİL, model
            # adının son ekidir (`--effort` ile `--model` çakışıyor). Öncelik:
            # istemdeki `/effort` > boost > çağrının eforu > modelin kendi son
            # eki > kalıcı ayar.
            run_model = self.apply_effort_to_model(
                run_model,
                self.effort_for_prompt(
                    prompt,
                    default_effort=(str(effort or "").strip().lower()
                                    or self._explicit_run_effort(model)),
                ),
            )
            if run_model and run_model != config.model_fallback_name:
                cmd.extend(["--model", run_model])
            if agent:
                cmd.extend(["--agent", agent])
            if conversation_id:
                cmd.extend(["--conversation", str(conversation_id)])

            # Detect any explicit Windows paths in prompt and grant access via --add-dir
            for p_obj in extract_windows_paths(prompt):
                try:
                    if (p_obj.exists() or p_obj.parent.exists()) and str(p_obj) not in cmd:
                        if not p_obj.exists() and "." not in p_obj.name:
                            try:
                                p_obj.mkdir(parents=True, exist_ok=True)
                            except Exception:
                                pass
                        cmd.extend(["--add-dir", str(p_obj)])
                except Exception:
                    pass

            full_response_acc = []
            ret_code = -1
            execution_error = None
            # Araç adımı sayacı (C2c) ve son görülen usage (A7a). `task_usage`
            # yalnızca `result` olayında dolarken, süreç yanıt vermeden ölünce
            # ledger'a NULL yazılıyordu; ara olaylardaki usage de saklanır.
            tool_steps = 0
            step_limit_hit = False
            # Popen'in kendisi hata verirse (agy bulunamadı) finally bloğu yine
            # çalışır; proc tanımsız kalmasın diye önceden bağlanıyor.
            proc = None
            # Aynı gerekçe: süreç hiç başlamazsa finally `turn_done`u okuyor.
            turn_done = False
            # Etkileşimli kipte kart daha döngü içindeyken finalize edilir;
            # bayrak, döngü sonrasında ikinci kez finalize edilmesini engeller.
            interactive_finalized = False

            def _usage_key() -> str:
                """
                Kümülatif usage tabanının anahtarı.

                agy aynı süreçteki turlarda `usage`ı BÜYÜTEREK verir; taban
                çıkarılmazsa ikinci turun maliyetine birincininki de eklenir.
                Konuşma kimliği biliniyorsa o, yoksa göreve özel anahtar.
                """
                with self._lock:
                    conv = self._background_conversations.get(task_id)
                return str(conv) if conv else f"task:{task_id}"

            def _release_locks() -> None:
                """Proje kilidini bırakır (bir kez; bayraklar sıfırlanır)."""
                nonlocal write_acquired, read_acquired
                if write_acquired:
                    try:
                        project_lock_manager.release_write(project_dir)
                    except Exception:
                        pass
                    write_acquired = False
                if read_acquired:
                    try:
                        project_lock_manager.release_read(project_dir)
                    except Exception:
                        pass
                    read_acquired = False

            def _finalize_followup(turn: int) -> None:
                """
                Takip turunu sonuçlandırır.

                Kart zaten `task_completed` ile kapandığı için ikinci bir
                tamamlanma sinyali yayılamaz; bölmeyi güncelleyen arayüz
                `bus.task_followup_completed` dinler. Ledger'da YENİ SÜTUN
                açılmaz: aynı satırın token toplamları artırılır.
                """
                text = "".join(full_response_acc).strip()
                ok = bool(text) and execution_error is None
                turn_usage = self._conversation_usage_delta(
                    _usage_key(), dict(task_usage or {})
                ) if task_usage else {}

                if turn_usage:
                    with self._state_lock:
                        self.last_background_usage = dict(turn_usage)
                        self.background_total_tokens += turn_usage.get("total_tokens", 0)
                    bus.token_usage_updated.emit(turn_usage.get("total_tokens", 0))
                    try:
                        prev = task_ledger.get_task(task_id) or {}
                        merged = {
                            k: int(prev.get(k) or 0) + int(turn_usage.get(k) or 0)
                            for k in ("input_tokens", "output_tokens", "total_tokens")
                        }
                        task_ledger.record_task_success(
                            task_id=task_id,
                            summary=mask_tool_output(text)[:300],
                            usage=merged,
                        )
                    except Exception:
                        pass

                if ok:
                    emit_stream("result", text)
                else:
                    emit_stream("error", execution_error or "Takip turu yanıtsız bitti.")
                try:
                    bus.task_followup_completed.emit({
                        "task_id": task_id,
                        "card_id": str((stream_meta or {}).get("card_id") or ""),
                        "text": text,
                        "usage": dict(turn_usage),
                        "turn": int(turn),
                        "success": ok,
                    })
                except Exception:
                    pass
            def _finalize_card(ret_code_override: Optional[int] = None) -> None:
                """
                Kartın BİRİNCİ turunu sonlandırır: token muhasebesi, ledger,
                sahne olayı, `on_result`, rapor ve `task_completed`.

                Faz 10-C'de gövde değişmedi, yalnızca ayrı bir ada taşındı:
                etkileşimli kipte süreç canlı kalırken bile kart tam olarak eski
                davranışla finalize edilmeli (kullanıcı sonucu beklemesin), takip
                turları ise ayrı bir yoldan (`_finalize_followup`) raporlanır.

                ret_code_override: etkileşimli kipte süreç hâlâ koştuğu için
                `proc.wait()` çağrılmaz; turun `result` olayı başarının kendisidir.
                """
                nonlocal task_usage, ret_code, card_success
                if ret_code_override is not None:
                    ret_code = ret_code_override
                full_text = "".join(full_response_acc).strip()
                success = ret_code == 0 and len(full_text) > 0 and execution_error is None
                card_success = success

                # Sürdürülen konuşmada agy'nin `usage` alanı KÜMÜLATİFTİR: ikinci
                # tur, birincinin token'larını da içerir. Taban çıkarılmazsa aynı
                # token ofis bütçesinden iki kez düşer ve bütçe erken tükenir.
                if task_usage and conversation_id:
                    task_usage = self._conversation_usage_delta(conversation_id, task_usage)
                elif task_usage:
                    conv_now = self._background_conversations.get(task_id)
                    if conv_now:
                        self._conversation_usage_delta(conv_now, task_usage, store_only=True)

                # Görev maliyeti oturum sayacına eklenir ve rozet yenilenir; ledger'a da
                # yazılır ki damıtma/konsolidasyon gibi işlerin gerçek kotası izlenebilsin.
                if task_usage:
                    # Eşzamanlı iki arka plan görevi aynı sayacı artırıyor; okuma-
                    # değiştirme-yazma kilitsizken bir görevin tüketimi kaybolabilir.
                    with self._state_lock:
                        self.last_background_usage = dict(task_usage)
                        self.background_total_tokens += task_usage.get("total_tokens", 0)
                        running_total = self.background_total_tokens
                    bus.terminal_output_received.emit(
                        f"[Token] {task_name}: {task_usage.get('total_tokens', 0):,} "
                        f"(girdi {task_usage.get('input_tokens', 0):,} / çıktı {task_usage.get('output_tokens', 0):,}) — "
                        f"arka plan toplamı {running_total:,}\n"
                    )
                    bus.token_usage_updated.emit(task_usage.get("total_tokens", 0))

                # Record in SQLite Task Ledger
                # Ledger özetine giden metin maskelenir: 300 karakterlik özetin
                # tamamı bir dosya dökümüyle dolduğunda görev panelinde satır hiçbir
                # şey anlatmıyordu (bkz. entropy.core.masking).
                masked_text = mask_tool_output(full_text)
                if success:
                    task_ledger.record_task_success(task_id=task_id, summary=masked_text[:300], usage=task_usage or None)
                elif not self._shutting_down:
                    err_detail = execution_error or f"Çıkış kodu: {ret_code}, yanıt uzunluğu: {len(full_text)}"
                    # usage ile: başarısız görev de token yaktı; sütun NULL kalırsa
                    # ofis bütçesi bu maliyeti hiç görmüyordu (A7a).
                    task_ledger.record_task_failure(
                        task_id=task_id, error=err_detail, usage=task_usage or None
                    )
                # Kapanışta süreci biz öldürdük: işçi burada "başarısız" yazsaydı
                # shutdown()'ın koyduğu CANCELLED'ın üstüne biner ve kullanıcı her
                # normal kapatmadan sonra sahte bir arıza kaydı görürdü.

                # Sahne için kart bitişi: başarı "idle" (volta), hata "error".
                if success:
                    emit_stream("result", full_text)
                else:
                    emit_stream("error", execution_error or full_text or "Görev başarısız.")

                # Tam çıktı, sinyallere sığmayan tüketicilere doğrudan verilir.
                # SIRA (Faz 11 kapanışı): rapor kasaya YAZILDIKTAN sonra haber
                # verilir; geri çağrı (kartın `_finish`i) rapor yolunu ancak o
                # zaman alabiliyor. `save_report=False` yolunda beklenecek bir
                # şey yok, geri çağrı hemen koşar.
                notified["done"] = True
                saved_report_path = ""

                if not save_report:
                    self._notify_result(on_result, full_text, success)
                    bus.task_completed.emit(task_id, success)
                    bus.terminal_output_received.emit(
                        f"\n[✔ Arka Plan Görevi: {task_name} Tamamlandı]\n"
                    )
                    return

                # Generate and save research report for completed background task
                clean_name = re.sub(r'[\\/*?:"<>|]', "_", task_name).strip() or task_id
                time_tag = datetime.datetime.now().strftime("%Y%m%d_%H%M")
                report_title = f"Gorev_{clean_name}_{time_tag}"

                try:
                    from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
                    from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
                    vm = ObsidianVaultManager()

                    report_content = f"# Otonom Görev Raporu: {task_name}\n\n"
                    report_content += f"- **Görev Kimliği**: `{task_id}`\n"
                    report_content += f"- **Tamamlanma Zamanı**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    report_content += f"- **Durum**: {'Başarılı' if success else 'Hata / Uyarı'}\n\n"
                    report_content += f"## Görev Çıktısı ve Bulgular\n\n{full_text}\n"

                    proj_name = self.active_project_dir.name if self.active_project_dir else None
                    # Arka plan görevi hangi yeteneğin işiyse rapor o yeteneğe atfedilir;
                    # zamanlanmış araştırma görevleri yordam damıtmanın ana kaynağıdır ve
                    # atıfsız rapor hiçbir yetenek için kaynak sayılmaz.
                    task_skill = None
                    try:
                        detected = self.detect_skill_for_prompt(prompt)
                        task_skill = detected.name if detected else None
                    except Exception:
                        task_skill = None
                    rep_path = vm.save_research_report(
                        report_title,
                        report_content,
                        tags=["otonom_gorev", task_id],
                        project_name=proj_name,
                        skill_name=task_skill,
                    )
                    saved_report_path = str(rep_path)

                    # Store distilled summary in cognitive memory
                    try:
                        cog = CognitiveMemorySystem()
                        cog.store_node(
                            category="semantic",
                            content=f"Otonom Görev Özeti [{task_name}]: {full_text[:300]}",
                            importance=0.85,
                            metadata={"source": "scheduled_task", "task_id": task_id, "path": str(rep_path)}
                        )
                    except Exception:
                        pass

                    bus.task_notification.emit(task_id, task_name, str(rep_path))
                    bus.cognitive_memory_updated.emit()
                    bus.knowledge_graph_updated.emit()

                except Exception as e:
                    bus.terminal_output_received.emit(f"[Otonom Rapor Hatası]: {e}\n")
                    bus.task_notification.emit(task_id, task_name, masked_text[:200])

                self._notify_result(on_result, full_text, success, saved_report_path)
                bus.task_completed.emit(task_id, success)
                bus.terminal_output_received.emit(
                    f"\n[✔ Otonom Arka Plan Görevi: {task_name} Tamamlandı]\n"
                )

            try:
                creationflags = 0
                if os.name == "nt":
                    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

                # Etkileşimli kipte istem HER ZAMAN stdin'den gider: takip
                # mesajlarının aynı boruya yazılabilmesi için sürecin
                # `--input-format stream-json` ile başlaması şart.
                stdin_payload = self._apply_stdin_prompt(cmd, force=interactive)
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE if stdin_payload else subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=creationflags,
                    cwd=str(project_dir) if project_dir.exists() else None
                )
                stdin_writer = self._feed_stdin(proc, stdin_payload, keep_open=interactive)
                with self._lock:
                    # Popen ile kayıt arasındaki yarış: kapanış tam bu aralıkta
                    # başladıysa süreç defterde olmadığı için öldürülmezdi.
                    late = self._shutting_down
                    if not late:
                        self._background_processes[task_id] = proc
                if late:
                    self._kill_tree(proc, wait_budget=1.0)
                    raise RuntimeError("Uygulama kapanıyor; görev başlatılmadı.")

                readline_fn = getattr(proc.stdout, "readline", None)
                stdout_stream = iter(readline_fn, '') if callable(readline_fn) else iter(proc.stdout)

                if interactive:
                    interactive_session = InteractiveSession(
                        task_id,
                        proc,
                        build_stdin_prompt_payload,
                        idle_timeout=float(
                            getattr(config, "desk_interactive_idle_timeout_s", None)
                            or INTERACTIVE_IDLE_TIMEOUT_S
                        ),
                        on_followup_start=on_followup_start,
                        on_followup_end=on_followup_end,
                    )
                    self._interactive_sessions.register(interactive_session)

                # Etkileşimli kipte okuma ilk `result` olayında kırılır: süreç
                # canlı kalır, kart finalize edilir ve takip turları aynı
                # akış yineleyicisinden okunmaya devam eder. Kip kapalıyken
                # akış eskisi gibi EOF'a kadar okunur.
                turn_done = False
                interactive_turn = 0
                while True:
                    turn_done = False
                    for raw_line in stdout_stream:
                        if not raw_line:
                            break
                        line_str = raw_line.strip()
                        if not line_str:
                            continue

                        try:
                            data = json.loads(line_str)
                            event = data.get("event")

                            if event == "step_update":
                                step = data.get("step_update", {})
                                step_type = step.get("step_type")
                                text_delta = step.get("text_delta")

                                # Ara olaydaki kümülatif usage saklanır: süreç
                                # `result` yayınlamadan ölürse ledger'a yazılacak
                                # tek maliyet kaydı budur.
                                step_usage = step.get("usage") or data.get("usage")
                                if isinstance(step_usage, dict):
                                    s_in = int(step_usage.get("input_tokens", 0) or 0)
                                    s_out = int(step_usage.get("output_tokens", 0) or 0)
                                    task_usage = {
                                        "input_tokens": s_in,
                                        "output_tokens": s_out,
                                        "thinking_tokens": int(step_usage.get("thinking_tokens", 0) or 0),
                                        "cache_read_tokens": int(step_usage.get("cache_read_tokens", 0) or 0),
                                        "total_tokens": int(step_usage.get("total_tokens", s_in + s_out) or 0),
                                    }

                                # Adım sayacı: agy iki ayrı biçimde araç olayı
                                # yayınlıyor (`step_type == "tool"` ve `tool_call`),
                                # ikisi de sayılır. Sınır aşılınca süreç öldürülür;
                                # istemdeki "en çok N adım" ricası yaptırımsızdı.
                                if max_steps and not step_limit_hit:
                                    if (step_type == "tool" and step.get("state", "ACTIVE") == "ACTIVE") \
                                            or step.get("tool_call"):
                                        tool_steps += 1
                                    if tool_steps > int(max_steps):
                                        step_limit_hit = True
                                        execution_error = (
                                            f"{MAX_STEPS_MARKER} Araç adımı sınırı aşıldı "
                                            f"({tool_steps} > {int(max_steps)}); görev durduruldu."
                                        )
                                        bus.terminal_output_received.emit(f"\n[{execution_error}]\n")
                                        self.terminate_background_task(task_id)
                                        break

                                # 1. Tool execution handling
                                if step_type == "tool":
                                    tool_name = step.get("tool_name") or step.get("tool_info", {}).get("name") or step.get("name", "Araç")
                                    params = step.get("tool_info", {}).get("parameters") or step.get("parameters", {})
                                    state = step.get("state", "ACTIVE")
                                    duration = step.get("duration_seconds", 0.0)
                                    tool_payload = self._tool_payload(tool_name, params)
                                    if state == "ACTIVE":
                                        param_str = json.dumps(params, ensure_ascii=False)[:300] if params else "{}"
                                        bus.terminal_output_received.emit(f"\n[⚡ ARAÇ YÜRÜTÜLÜYOR: {tool_name}]\n   Parametreler: {param_str}...\n")
                                        emit_stream("tool_call", f"{tool_name}: {tool_payload['input_summary']}", tool=tool_payload)
                                        bus.core_pulse_triggered.emit(0.7)
                                    elif state == "DONE":
                                        out = step.get("output") or step.get("result") or step.get("content")
                                        if out:
                                            out_str = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
                                            bus.terminal_output_received.emit(f"[✔ ARAÇ TAMAMLANDI: {tool_name} ({duration:.2f}s)]\n   Sonuç: {out_str[:300]}...\n")
                                        else:
                                            out_str = ""
                                            bus.terminal_output_received.emit(f"[✔ ARAÇ TAMAMLANDI: {tool_name} ({duration:.2f}s)]\n")
                                        emit_stream("tool_result", out_str, tool=tool_payload)
                                        bus.core_pulse_triggered.emit(0.5)
                                    elif state in ["ERROR", "FAILED"]:
                                        err = step.get("error") or step.get("message")
                                        if err:
                                            bus.terminal_output_received.emit(f"[❌ ARAÇ HATASI: {tool_name}]\n   Hata: {str(err)[:300]}...\n")
                                        else:
                                            bus.terminal_output_received.emit(f"[❌ ARAÇ HATASI: {tool_name}]\n")
                                        emit_stream("error", str(err or f"{tool_name} aracı hata verdi"), tool=tool_payload)
                                        bus.core_pulse_triggered.emit(0.3)
                                else:
                                    call = step.get("tool_call")
                                    if call:
                                        tool_name = call.get("name", "Araç")
                                        params = call.get("parameters") or call.get("args") or {}
                                        param_str = json.dumps(params, ensure_ascii=False)[:300] if params else ""
                                        if param_str:
                                            bus.terminal_output_received.emit(f"\n[🔧 Otonom Görev Aracı: {tool_name}]\n   Parametreler: {param_str}...\n")
                                        else:
                                            bus.terminal_output_received.emit(f"\n[🔧 Otonom Görev Aracı: {tool_name}...]\n")
                                        tool_payload = self._tool_payload(tool_name, params)
                                        emit_stream("tool_call", f"{tool_name}: {tool_payload['input_summary']}", tool=tool_payload)
                                        bus.core_pulse_triggered.emit(0.6)

                                    res = step.get("tool_result")
                                    if res:
                                        tool_name = res.get("name", "Araç") if isinstance(res, dict) else "Araç"
                                        res_content = res.get("content") or res.get("output") if isinstance(res, dict) else str(res)
                                        if res_content:
                                            bus.terminal_output_received.emit(f"[✔ Otonom Araç Tamamlandı: {tool_name}]\n   Sonuç: {str(res_content)[:300]}...\n")
                                        else:
                                            bus.terminal_output_received.emit(f"[✔ Otonom Araç Tamamlandı: {tool_name}]\n")
                                        emit_stream(
                                            "tool_result",
                                            str(res_content or ""),
                                            tool=self._tool_payload(tool_name, None),
                                        )
                                        bus.core_pulse_triggered.emit(0.4)

                                # 2. Thinking telemetry
                                thought = (
                                    step.get("thought") or
                                    step.get("reasoning") or
                                    step.get("thinking") or
                                    step.get("thought_delta") or
                                    step.get("reasoning_content") or
                                    data.get("thought") or
                                    data.get("thought_delta") or
                                    data.get("reasoning")
                                )
                                step_idx = step.get("step_index", 1)
                                if thought and isinstance(thought, str) and thought.strip():
                                    bus.terminal_output_received.emit(f"[🧠 Otonom Görev Düşünce (Adım #{step_idx})]: {thought.strip()}\n")
                                    emit_stream("thinking", thought.strip())
                                    bus.core_pulse_triggered.emit(0.5)
                                elif (step_type in ["agent_thought", "thinking", "thought", "reasoning"] or (step_type == "agent_response" and not text_delta)):
                                    bus.terminal_output_received.emit(f"[🧠 Otonom Görev Düşünülüyor (Adım #{step_idx})...]\n")
                                    emit_stream("status", f"Düşünülüyor (adım #{step_idx})…")
                                    bus.core_pulse_triggered.emit(0.5)

                                # 3. Text delta
                                if text_delta:
                                    bus.terminal_output_received.emit(text_delta)
                                    # Kart yolunda `token_chunk_received` BUGÜNE DEK
                                    # hiç yayılmıyordu (yalnızca sohbet yolunda);
                                    # eski tüketiciler için geriye uyum.
                                    bus.token_chunk_received.emit(text_delta)
                                    emit_stream("text", text_delta)
                                    full_response_acc.append(text_delta)
                                    bus.core_pulse_triggered.emit(0.5)

                            elif event == "result":
                                result = data.get("result", {})
                                resp = result.get("response", "")
                                if not full_response_acc and resp:
                                    bus.terminal_output_received.emit(resp)
                                    bus.token_chunk_received.emit(resp)
                                    emit_stream("text", resp)
                                    full_response_acc.append(resp)

                                # Konuşma kimliği: ofis çağrıları (plan → değerlendirme
                                # → yeniden plan) aynı agy konuşmasında sürsün diye
                                # saklanır. Alt kartlar bunu HİÇ kullanmaz.
                                conv = data.get("conversation_id") or result.get("conversation_id")
                                if conv:
                                    with self._lock:
                                        self._background_conversations[task_id] = str(conv)
                                    # Faz 11-C.3: agy kimliği ÖNCEDEN atanamıyor
                                    # (Claude'daki `--session-id` karşılığı yok),
                                    # bu yüzden akıştan yakalanan kimlik ajanın
                                    # kalıcı oturum dosyasına yazılır; sonraki
                                    # koşu `--conversation <id>` alır.
                                    self._remember_agent_session(agent, str(conv))

                                # Her arka plan görevi yeni bir konuşma olduğundan agy'nin
                                # kümülatif "usage" değeri doğrudan bu görevin maliyetidir.
                                usage = result.get("usage")
                                if isinstance(usage, dict):
                                    cum_in = int(usage.get("input_tokens", 0) or 0)
                                    cum_out = int(usage.get("output_tokens", 0) or 0)
                                    task_usage = {
                                        "input_tokens": cum_in,
                                        "output_tokens": cum_out,
                                        "thinking_tokens": int(usage.get("thinking_tokens", 0) or 0),
                                        "cache_read_tokens": int(usage.get("cache_read_tokens", 0) or 0),
                                        "total_tokens": int(usage.get("total_tokens", cum_in + cum_out) or 0),
                                    }

                                if interactive:
                                    # Tur bitti; süreç canlı kalıyor. Okuma burada
                                    # kesilmezse akış EOF beklerken kart hiç
                                    # sonuçlanmaz ve kullanıcı boşuna bekler.
                                    turn_done = True
                                    break

                        except json.JSONDecodeError:
                            bus.terminal_output_received.emit(raw_line)
                            bus.token_chunk_received.emit(raw_line)
                            emit_stream("text", raw_line)
                            full_response_acc.append(raw_line)

                    if not (interactive and turn_done and interactive_session is not None):
                        # Akış EOF'a geldi (ya da kip kapalı): eski yol.
                        break

                    # --- Tur bitti, süreç canlı: kart/tur sonuçlandırılır ---
                    if interactive_turn == 0:
                        _finalize_card(ret_code_override=0)
                        interactive_finalized = True
                        # Kümülatif usage tabanı: sonraki turların maliyeti
                        # bunun farkıdır (agy aynı süreçte toplamı büyütür).
                        self._conversation_usage_delta(
                            _usage_key(), dict(task_usage or {}), store_only=True
                        )
                        # Bekleyen terminal, koşan kart değildir: proje kilidi
                        # ve ofis paralellik sayacı burada serbest bırakılır.
                        _release_locks()
                    else:
                        _finalize_followup(interactive_turn)
                        interactive_session.finish_turn()

                    # Yeni tur sıfırdan birikir; adım sayacı da tur başınadır
                    # (istem "en çok N adım" derken bir turu kastediyor).
                    full_response_acc = []
                    task_usage = {}
                    tool_steps = 0
                    step_limit_hit = False
                    emit_stream("status", "Takip mesajı bekliyor…", state="idle")
                    if not interactive_session.wait_for_followup():
                        emit_stream(
                            "status",
                            f"Terminal kapandı ({interactive_session.close_reason or 'kapatıldı'}).",
                            state="idle",
                        )
                        break
                    interactive_turn += 1
                    emit_stream("status", "Takip mesajı alındı; sürdürülüyor…", state="working")

                # Yazıcı iş parçacigi normalde okuma bitmeden tamamlanir; yine de
                # surec beklenmeden once kapandigi dogrulanir.
                if stdin_writer is not None:
                    stdin_writer.join(timeout=5.0)
                if interactive_finalized:
                    # Terminal kapandı: stdin de kapatıldığı için sürecin
                    # kendiliğinden çıkması beklenir; inatçıysa finally indirir.
                    try:
                        proc.stdout.close()
                    except Exception:
                        pass
                    try:
                        ret_code = proc.wait(timeout=5.0)
                    except Exception:
                        ret_code = -1
                else:
                    proc.stdout.close()
                    ret_code = proc.wait()

            except Exception as e:
                execution_error = str(e)
                err_msg = f"[Otonom Görev Hata] {task_name} yürütülemedi: {execution_error}\n"
                bus.terminal_output_received.emit(err_msg)
                emit_stream("error", err_msg)
                full_response_acc.append(err_msg)
                ret_code = -1
            finally:
                # Buraya yalnızca terminal kapandıktan sonra gelinir; etkileşimli
                # oturum defteri de burada temizlenir (aksi hâlde kapanmış bir
                # kart için `send_followup` hâlâ True dönerdi).
                with self._lock:
                    self._background_processes.pop(task_id, None)
                if interactive_session is not None:
                    interactive_session.close("tur döngüsü bitti")
                    self._interactive_sessions.pop(task_id)
                    with self._state_lock:
                        self._interactive_stream_meta.pop(task_id, None)
                # Temizlik, görevin sonucunu etkilememeli: buradaki bir istisna
                # dış except'e sızarsa tamamlanmış bir görev FAILED kaydedilir.
                # Bu yüzden poll() de dahil tüm blok korunur.
                try:
                    if proc and proc.poll() is None:
                        pid = proc.pid
                        if sys.platform == "win32" or os.name == "nt":
                            subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        else:
                            proc.terminate()
                        proc.wait(timeout=2.0)
                except Exception:
                    pass

            # Etkileşimli kartta finalize DÖNGÜ İÇİNDE yapıldı; burada ikinci
            # kez çalıştırmak ledger'ı, raporu ve `on_result`u tekrarlardı.
            if not interactive_finalized:
                _finalize_card()

        except Exception as outer_err:
            try:
                task_rec = task_ledger.get_task(task_id)
                if (not self._shutting_down) and task_rec and task_rec.get("status") == TaskStatus.RUNNING.value:
                    task_ledger.record_task_failure(
                        task_id=task_id, error=str(outer_err), usage=task_usage or None
                    )
            except Exception:
                pass
            if not notified["done"]:
                notified["done"] = True
                self._notify_result(on_result, f"Otonom görev kritik hata: {outer_err}", False)
            bus.task_completed.emit(task_id, False)
            bus.terminal_output_received.emit(f"\n[Otonom Görev Kritik Hata]: {outer_err}\n")
            emit_stream("error", f"Otonom görev kritik hata: {outer_err}")
        finally:
            if write_acquired:
                try:
                    project_lock_manager.release_write(project_dir)
                except Exception:
                    pass
            if read_acquired:
                try:
                    project_lock_manager.release_read(project_dir)
                except Exception:
                    pass

    def _execute_prompt_worker(
        self,
        prompt: str,
        image_attachments: Optional[List[str]] = None,
        pdf_attachments: Optional[List[str]] = None,
        active_skill: Optional[str] = None,
        mode: str = "accept-edits",
        project_path: Optional[str] = None
    ):
        # Sohbet yolu da sahneye görünür: Entropy'nin kendi avatarı
        # (agent="entropy", office="", card_id="") aynı sözleşmeden beslenir.
        emit_stream = self._agent_stream_emitter("", None, None)
        project_dir = Path(project_path).resolve() if project_path else Path(self.active_project_dir).resolve()
        if not project_dir.exists():
            try:
                project_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
        is_write = self.is_code_modifying_intent(prompt, mode=mode)
        lock_acquired = False
        is_exclusive = is_write

        if is_write:
            if project_lock_manager.is_write_locked(project_dir):
                bus.terminal_output_received.emit(
                    "\n[Proje Kilidi: Arka plan görevi çalışıyor, işlem bekleniyor...]\n"
                )
            lock_acquired = project_lock_manager.acquire_write(project_dir, timeout=30.0)
        else:
            if project_lock_manager.is_write_locked(project_dir):
                bus.terminal_output_received.emit(
                    "\n[Proje Kilidi: Arka plan görevi çalışıyor, işlem bekleniyor...]\n"
                )
            lock_acquired = project_lock_manager.acquire_read(project_dir, timeout=30.0)

        if not lock_acquired:
            bus.terminal_output_received.emit(
                "\n[Proje Kilidi: Zaman aşımı! Arka plan görevi projeyi kullanıyor. Lütfen görevin bitmesini bekleyin.]\n"
            )
            bus.core_state_changed.emit("idle")
            with self._lock:
                self._is_running = False
                if self._prompt_queue:
                    next_task = self._prompt_queue.pop(0)
                    self._is_running = True
                    next_prompt = next_task[0]
                    next_imgs = next_task[1] if len(next_task) > 1 else None
                    next_pdfs = next_task[2] if len(next_task) > 2 else None
                    next_skill = next_task[3] if len(next_task) > 3 else None
                    next_mode = next_task[4] if len(next_task) > 4 else "accept-edits"
                    next_proj = next_task[5] if len(next_task) > 5 else None
                    threading.Thread(
                        target=self._execute_prompt_worker,
                        args=(next_prompt, next_imgs, next_pdfs, next_skill, next_mode, next_proj),
                        daemon=True
                    ).start()
            return

        raw_user_prompt = prompt
        working_prompt = prompt

        # 1. Process PDF Attachments if any (Multi-page full ingestion)
        if pdf_attachments:
            try:
                from entropy.skills.pdf_engine import PDFIngestionEngine
                pdf_eng = PDFIngestionEngine()
                pdf_blocks = []
                for pdf_file in pdf_attachments:
                    res = pdf_eng.ingest_and_store_memory(pdf_file)
                    meta = res["metadata"]
                    content_body = res["full_content"]
                    # Multi-page safe budget: ensure every single page has representation
                    max_pdf_chars = 14000
                    if len(content_body) > max_pdf_chars:
                        pages = res.get("pages", [])
                        if pages:
                            chars_per_page = max(200, max_pdf_chars // len(pages))
                            sampled_blocks = []
                            for pg in pages:
                                p_num = pg.get("page", 1)
                                p_txt = pg.get("text", "").strip()
                                snippet = p_txt[:chars_per_page]
                                if len(p_txt) > chars_per_page:
                                    snippet += " ...[sayfa devamı]"
                                sampled_blocks.append(f"--- [Sayfa {p_num} / {meta['pages']}] ---\n{snippet}")
                            content_body = "\n\n".join(sampled_blocks) + f"\n\n[Belge {meta['pages']} sayfa içerir. Tüm sayfalar taranarak özetlendi. Tam metin arşivi: {res['digest_path']}]"
                        else:
                            content_body = content_body[:max_pdf_chars] + f"\n\n[... PDF içeriği ilk {max_pdf_chars} karakter dahil edildi. Arşiv: {res['digest_path']}]"
                    pdf_blocks.append(
                        f"\n[EKLENEN PDF BELGESİ: {meta['filename']} - {meta['pages']} Sayfa, {meta['word_count']} Kelime]:\n"
                        f"{content_body}\n"
                        f"(Tam özet arşivi: {res['digest_path']})\n"
                    )
                if pdf_blocks:
                    working_prompt = "\n".join(pdf_blocks) + "\n\n" + raw_user_prompt
            except Exception as e:
                bus.terminal_output_received.emit(f"[PDF İşleme Hatası]: {e}\n")

        # 2. Skill Resolution (Explicit Slash Command, active_skill parameter, or Semantic Auto-Detection)
        target_skill = None
        compact_skill_banner = ""
        try:
            from entropy.skills.manager import SkillManager
            sm = SkillManager(project_dir=self.active_project_dir)
            all_skills = sm.list_skills()
            skills_map = {s.name.lower(): s for s in all_skills}

            if active_skill and active_skill.lower() not in ["auto", "otomatik", "otomatik algıla"]:
                target_skill = skills_map.get(active_skill.lower())

            # Check if any skill is explicitly summoned via slash command in prompt
            if not target_skill:
                for s in all_skills:
                    if re.search(rf'(?:^|\s)/{re.escape(s.name)}\b', raw_user_prompt, re.IGNORECASE):
                        target_skill = s
                        break

            # Fall back to semantic auto-detection
            if not target_skill:
                target_skill = self.detect_skill_for_prompt(raw_user_prompt, sm=sm)

            if target_skill:
                script_info = ""
                if target_skill.scripts:
                    s_names = ", ".join([sc.get("name", "") for sc in target_skill.scripts if sc.get("name")])
                    if s_names:
                        script_info = f" (Araçlar: {s_names})"
                # Progressive Disclosure: compact 1-2 line banner instead of pasting 38KB markdown
                compact_skill_banner = (
                    f"[AKTİF UZMANLIK YETENEĞİ: {target_skill.name.upper()}]{script_info}\n"
                    f"Özet: {target_skill.description}\n"
                    f"Detaylı yönergeler ve araçlar için '{target_skill.path}' dosyasını inceleyin."
                )
                bus.terminal_output_received.emit(f"[🎯 Yetenek Devrede]: '{target_skill.name}' yeteneği aktif olarak kullanılıyor.\n")
        except Exception:
            pass

        bus.core_state_changed.emit("thinking")
        bus.agent_turn_started.emit(raw_user_prompt)

        agy_bin = self.find_agy_executable()

        # Check if continuing an existing conversation or starting turn 1
        if self.session_turn_count >= 15 and self.current_conversation_id:
            bus.terminal_output_received.emit(
                "\n[Entropy Core] Oturum bağlamı 15 tura ulaştı. Bağlam özetlenerek yeni temiz bir AGY oturumuna aktarılıyor...\n"
            )
            self.current_conversation_id = None
            config.last_conversation_id = None
            config.save_settings()
            self.last_cumulative_usage = {
                "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "cache_read_tokens": 0, "total_tokens": 0
            }
            self.session_turn_count = 0

        # Regex and natural language detection (/plan, /boost, /effort, /grill-me, /teamwork-preview, /goal, /learn)
        if re.search(r'(?:^|\s)/plan\b', raw_user_prompt, re.IGNORECASE):
            mode = "plan"

        is_boost_intent = bool(
            re.search(r'(?:^|\s)/boost\b', raw_user_prompt, re.IGNORECASE) or
            any(phrase in raw_user_prompt.lower() for phrase in [
                "boost yöntemi", "boost modu", "tam kapasite", "maksimum akıl yürütme", "derin planlama", "derin mimari"
            ])
        )
        is_teamwork_intent = bool(
            re.search(r'(?:^|\s)/teamwork-preview\b', raw_user_prompt, re.IGNORECASE) or
            any(phrase in raw_user_prompt.lower() for phrase in [
                "teamwork preview", "teamwork", "takım çalışması", "orkestratör sistemi", "orkestrasyon",
                "sub-agent", "subagent", "alt ajan", "çoklu ajan", "ajan geliştir", "proje geliştir"
            ])
        )

        slash_directives = []
        if is_boost_intent:
            slash_directives.append(
                "[MOD: BOOST] Maksimum akıl yürütme, derin mimari planlama ve tam otonom orkestrasyon devrede. "
                "Projeyi uçtan uca tasarla, alt görevlere böl, dosya oluşturma araçlarını (write_to_file, replace_file_content, run_command) "
                "ve alt ajan araçlarını (invoke_subagent, define_subagent, manage_subagents) kullanarak dosyaları fiilen diske oluştur, testleri yaz ve çalıştırarak doğrula."
            )
        if re.search(r'(?:^|\s)/grill-me\b', raw_user_prompt, re.IGNORECASE):
            slash_directives.append("[MOD: GRILL-ME] Kullanıcının sunduğu fikir, mimari veya kodu acımasızca sorgula; kör noktaları, ölçekleme darboğazlarını ve riskleri doğrudan yüzeye çıkar.")
        if is_teamwork_intent:
            slash_directives.append(
                "[MOD: TEAMWORK-PREVIEW] Görevi orkestratör, uygulayıcı uzman (CodeArchitect), test mimarı (Tester) ve araştırmacı (Researcher) perspektifinden bölümlere ayır. "
                "Yalnızca statik bir önizleme sunmakla kalma; çoklu ajan iş akışını aktif olarak koordine et, alt görevleri belirle ve projenin somut kodlarını ve dosyalarını fiilen oluşturmaya başla."
            )
        goal_m = re.search(r'(?:^|\s)/goal\s+([^\n\r]+)', raw_user_prompt, re.IGNORECASE)
        if goal_m:
            slash_directives.append(f"[OTURUM HEDEFİ]: '{goal_m.group(1).strip()}' hedefini bu oturumun birincil odak noktası olarak al.")
        elif re.search(r'(?:^|\s)/goal\b', raw_user_prompt, re.IGNORECASE):
            slash_directives.append("[OTURUM HEDEFİ]: Kullanıcının belirttiği temel hedefi bu oturumun birincil odak noktası olarak al.")
        if re.search(r'(?:^|\s)/learn\b', raw_user_prompt, re.IGNORECASE):
            slash_directives.append("[MOD: LEARN]: Bu oturumda ulaşılan nihai çözüm, mimari kararlar ve kuralları kalıcı bilişsel hafızaya ve Obsidian kasanıza kaydedilmek üzere özetle.")

        autonomous_rules = (
            "TEMEL YÜRÜTME VE KODLAMA KURALLARI:\n"
            "1. Kullanıcı senden yeni bir proje oluşturmanı, bir sistemi kodlamanı veya dosyalar oluşturmanı istediğinde: "
            "ASLA sadece 'dosyaları oluşturdum, mimariyi kurdum' şeklinde metin çıktısı vermekle yetinme! "
            "FİİLİ OLARAK dosya oluşturma ve düzenleme araçlarını (write_to_file, replace_file_content, run_command) kullanarak "
            "çalışma dizininde dosyaları oluştur, kodları yaz ve otomatik testleri çalıştırarak doğrula.\n"
            "2. Karmaşık, çok ofisli veya çoklu ajan mimarisine sahip projelerde tek başına çalışmak yerine "
            "Antigravity'nin alt ajan araçlarını (invoke_subagent, define_subagent, manage_subagents) kullan; "
            "CodeArchitect (mimari ve şasi), Developer (uygulama ve entegrasyon), Tester (testler ve doğrulama) "
            "ve Researcher (araştırma ve raporlama) gibi uzman rollere görev delege et.\n"
            "3. Kodladığın her yeni modül veya proje için otomatik testleri (pytest vb.) çalıştır ve %100 başarı oranını sağla."
        )

        max_cli_payload = 26000

        if self.current_conversation_id:
            # Yetenek belirlendiyse hatırlanır; belirlenmediyse önceki değer korunur ki
            # araya giren yeteneksiz bir tur ("tamam", "devam") önceliği silmesin.
            if target_skill is not None:
                self.last_active_skill = target_skill.name
            mini_context = self.get_mini_cognitive_context(raw_user_prompt, target_skill=target_skill)
            prefix_parts = [autonomous_rules]
            if compact_skill_banner:
                prefix_parts.append(compact_skill_banner)
            if slash_directives:
                prefix_parts.extend(slash_directives)
            if mini_context:
                prefix_parts.append(mini_context)
            prefix_context = "\n\n".join(prefix_parts)

            # Never truncate user prompt; truncate prefix context if needed to stay below Windows limit
            if prefix_context:
                available_prefix = max(0, max_cli_payload - len(working_prompt) - 2)
                if len(prefix_context) > available_prefix:
                    prefix_context = prefix_context[:available_prefix]
                turn_prompt = f"{prefix_context}\n\n{working_prompt}" if prefix_context else working_prompt
            else:
                turn_prompt = working_prompt

            cmd = [
                agy_bin,
                "-p", turn_prompt,
                "--conversation", self.current_conversation_id,
                "--output-format", "stream-json",
                "--mode", mode,
                "--print-timeout", "30m",
                "--dangerously-skip-permissions",
                "--add-dir", str(project_dir),
            ]
        else:
            cognitive_context = self.get_cognitive_context(raw_user_prompt, target_skill=target_skill)
            system_directive = (
                "Sen Entropy AI adında otonom bir masaüstü yapay zeka işletim sistemisin. "
                "Kullanıcıya daima Türkçe ve samimi, net, profesyonel bir üslupla yanıt ver.\n"
                "Kendi hafıza sisteminden, Obsidian notlarından ve geçmiş kararlarından tamamen haberdarsın.\n"
                f"{autonomous_rules}\n"
            )
            if compact_skill_banner:
                system_directive += f"\n{compact_skill_banner}\n"

            if slash_directives:
                system_directive += "\n" + "\n".join(slash_directives) + "\n"

            if cognitive_context:
                # Kırpma bağlamın SONUNU keser; ajan kataloğu orada duruyor ve
                # sessizce düşüyordu. Kırpılmışsa geri eklenir: ajanları bilmeyen
                # bir tur işi devretmeyi hiç öneremez.
                if len(cognitive_context) > 6000:
                    agents_section = self.agents_manifest_section()
                    cognitive_context = cognitive_context[:6000]
                    if agents_section and agents_section not in cognitive_context:
                        cognitive_context = f"{cognitive_context}\n\n{agents_section}"
                system_directive += f"\n{cognitive_context}\n"

            # Inject recent chat history summary if starting a fresh session
            if self.conversation_history:
                recent = self.conversation_history[-6:]
                system_directive += "\nÖnceki Sohbet Özeti:\n" + "\n".join(
                    [f"- {'Kullanıcı' if m.get('role')=='user' else 'Entropy'}: {m.get('content', '')[:100]}" for m in recent]
                ) + "\n"

            user_msg = f"\nKullanıcı Mesajı: {working_prompt}"
            # Safe payload calculation: NEVER truncate user message, trim system directive if needed
            available_dir = max(0, max_cli_payload - len(user_msg))
            if len(system_directive) > available_dir:
                system_directive = system_directive[:available_dir]

            full_prompt_payload = f"{system_directive}{user_msg}" if system_directive else user_msg

            cmd = [
                agy_bin,
                "-p", full_prompt_payload,
                "--output-format", "stream-json",
                "--mode", mode,
                "--print-timeout", "30m",
                "--dangerously-skip-permissions",
                "--add-dir", str(project_dir),
            ]

        # Efor agy'de ayrı bayrak DEĞİL, model adının son ekidir; `--effort` ile
        # son ekli model birlikte verilirse CLI turu hiç başlatmaz.
        run_model = self.apply_effort_to_model(
            self.selected_model,
            self.effort_for_prompt(
                raw_user_prompt,
                boost=bool(is_boost_intent or is_teamwork_intent),
            ),
        )
        if run_model and run_model != config.model_fallback_name:
            cmd.extend(["--model", run_model])

        if image_attachments:
            for img in image_attachments:
                if Path(img).exists():
                    cmd.extend(["--add-dir", str(Path(img).parent)])

        # Detect any explicit Windows paths in prompt and grant access via --add-dir
        for p_obj in extract_windows_paths(raw_user_prompt):
            try:
                if (p_obj.exists() or p_obj.parent.exists()) and str(p_obj) not in cmd:
                    if not p_obj.exists() and "." not in p_obj.name:
                        try:
                            p_obj.mkdir(parents=True, exist_ok=True)
                        except Exception:
                            pass
                    cmd.extend(["--add-dir", str(p_obj)])
            except Exception:
                pass

        full_response_acc = []

        try:
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

            stdin_payload = self._apply_stdin_prompt(cmd)
            self._current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE if stdin_payload else subprocess.DEVNULL,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
                cwd=str(project_dir) if project_dir.exists() else None
            )
            stdin_writer = self._feed_stdin(self._current_process, stdin_payload)

            short_prompt = raw_user_prompt.replace("\n", " ")[:65]
            if len(raw_user_prompt) > 65:
                short_prompt += "..."
            status_tag = f"Sohbet: {self.current_conversation_id[:8]}..." if self.current_conversation_id else "Yeni Sohbet"
            bus.terminal_output_received.emit(f"\n[Entropy Core | {self.selected_model} | {status_tag}] > {short_prompt}\n")

            readline_fn = getattr(self._current_process.stdout, "readline", None)
            stdout_stream = iter(readline_fn, '') if callable(readline_fn) else iter(self._current_process.stdout)

            for raw_line in stdout_stream:
                if not raw_line:
                    break
                line_str = raw_line.strip()
                if not line_str:
                    continue

                try:
                    data = json.loads(line_str)
                    
                    # Capture and persist conversation ID
                    c_id = data.get("conversation_id")
                    if c_id:
                        self.current_conversation_id = c_id
                        config.last_conversation_id = c_id
                        config.save_settings()

                    event = data.get("event")

                    if event == "init":
                        init_data = data.get("init", {})
                        model = init_data.get("model")
                        if model:
                            self.current_model = model
                            bus.model_detected.emit(model)

                    elif event == "step_update":
                        step = data.get("step_update", {})
                        step_type = step.get("step_type")
                        text_delta = step.get("text_delta")

                        # 1. Tool handling
                        if step_type == "tool":
                            tool_name = step.get("tool_name") or step.get("tool_info", {}).get("name") or step.get("name", "Araç")
                            params = step.get("tool_info", {}).get("parameters") or step.get("parameters", {})
                            state = step.get("state", "ACTIVE")
                            duration = step.get("duration_seconds", 0.0)
                            if state == "ACTIVE":
                                param_str = json.dumps(params, ensure_ascii=False)[:300] if params else "{}"
                                bus.terminal_output_received.emit(f"\n[⚡ ARAÇ YÜRÜTÜLÜYOR: {tool_name}]\n   Parametreler: {param_str}...\n")
                                _tp = self._tool_payload(tool_name, params)
                                emit_stream("tool_call", f"{tool_name}: {_tp['input_summary']}", tool=_tp)
                                bus.core_pulse_triggered.emit(0.7)
                            elif state == "DONE":
                                out = step.get("output") or step.get("result") or step.get("content")
                                if out:
                                    out_str = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
                                    bus.terminal_output_received.emit(f"[✔ ARAÇ TAMAMLANDI: {tool_name} ({duration:.2f}s)]\n   Sonuç: {out_str[:300]}...\n")
                                else:
                                    bus.terminal_output_received.emit(f"[✔ ARAÇ TAMAMLANDI: {tool_name} ({duration:.2f}s)]\n")
                                bus.core_pulse_triggered.emit(0.5)
                            elif state in ["ERROR", "FAILED"]:
                                err = step.get("error") or step.get("message")
                                if err:
                                    bus.terminal_output_received.emit(f"[❌ ARAÇ HATASI: {tool_name}]\n   Hata: {str(err)[:300]}...\n")
                                else:
                                    bus.terminal_output_received.emit(f"[❌ ARAÇ HATASI: {tool_name}]\n")
                                bus.core_pulse_triggered.emit(0.3)
                        else:
                            call = step.get("tool_call")
                            if call:
                                tool_name = call.get("name", "Araç")
                                params = call.get("parameters") or call.get("args") or {}
                                param_str = json.dumps(params, ensure_ascii=False)[:300] if params else ""
                                if param_str:
                                    bus.terminal_output_received.emit(f"\n[🔧 Araç Yürütülüyor: {tool_name}]\n   Parametreler: {param_str}...\n")
                                else:
                                    bus.terminal_output_received.emit(f"\n[🔧 Araç Yürütülüyor: {tool_name}...]\n")
                                bus.core_pulse_triggered.emit(0.7)

                            res = step.get("tool_result")
                            if res:
                                tool_name = res.get("name", "Araç") if isinstance(res, dict) else "Araç"
                                res_content = res.get("content") or res.get("output") if isinstance(res, dict) else str(res)
                                if res_content:
                                    bus.terminal_output_received.emit(f"[✔ Araç Tamamlandı: {tool_name}]\n   Sonuç: {str(res_content)[:300]}...\n")
                                else:
                                    bus.terminal_output_received.emit(f"[✔ Araç Tamamlandı: {tool_name}]\n")
                                bus.core_pulse_triggered.emit(0.5)

                        # 2. Thinking telemetry (sent to terminal)
                        thought = (
                            step.get("thought") or
                            step.get("reasoning") or
                            step.get("thinking") or
                            step.get("thought_delta") or
                            step.get("reasoning_content") or
                            data.get("thought") or
                            data.get("thought_delta") or
                            data.get("reasoning")
                        )
                        step_idx = step.get("step_index", 1)
                        if thought and isinstance(thought, str) and thought.strip():
                            bus.terminal_output_received.emit(f"[🧠 Düşünce (Adım #{step_idx})]: {thought.strip()}\n")
                            emit_stream("thinking", thought.strip())
                            bus.core_pulse_triggered.emit(0.6)
                        elif (step_type in ["agent_thought", "thinking", "thought", "reasoning"] or (step_type == "agent_response" and not text_delta)):
                            bus.terminal_output_received.emit(f"[🧠 Düşünülüyor / Akıl Yürütülüyor (Adım #{step_idx})...]\n")
                            bus.core_pulse_triggered.emit(0.6)

                        # 3. Text delta (sent strictly to chat window)
                        if text_delta:
                            full_response_acc.append(text_delta)
                            try:
                                bus.token_chunk_received.emit(text_delta)
                                emit_stream("text", text_delta)
                                bus.core_pulse_triggered.emit(0.8)
                            except (RuntimeError, Exception):
                                pass

                        usage = step.get("usage")
                        if usage:
                            step_out = usage.get("output_tokens", 0)
                            if step_out > self.latest_output_tokens:
                                self.latest_output_tokens = step_out

                    elif event == "result":
                        result = data.get("result", {})
                        resp = result.get("response", "")
                        if not full_response_acc and resp:
                            full_response_acc.append(resp)
                            bus.token_chunk_received.emit(resp)
                        resp_len = len(resp or "".join(full_response_acc))
                        bus.terminal_output_received.emit(f"\n[✔ Yanıt Akışı Tamamlandı ({resp_len} karakter)]\n")
                        emit_stream("result", resp or "".join(full_response_acc))

                        usage = result.get("usage")
                        if usage:
                            # 1. Total lifetime cumulative tokens for this AGY session
                            cum_in = usage.get("input_tokens", 0)
                            cum_out = usage.get("output_tokens", 0)
                            cum_think = usage.get("thinking_tokens", 0)
                            cum_cache = usage.get("cache_read_tokens", 0)
                            cum_total = usage.get("total_tokens", cum_in + cum_out)

                            # 2. Compute exact delta tokens for THIS active turn
                            turn_output = max(0, cum_out - self.last_cumulative_usage.get("output_tokens", 0))
                            turn_input = max(0, cum_in - self.last_cumulative_usage.get("input_tokens", 0))
                            turn_thinking = max(0, cum_think - self.last_cumulative_usage.get("thinking_tokens", 0))
                            turn_cache = max(0, cum_cache - self.last_cumulative_usage.get("cache_read_tokens", 0))

                            # If turn_output is 0 but step had output, fallback to step output
                            if turn_output == 0 and self.latest_output_tokens > 0:
                                turn_output = self.latest_output_tokens

                            turn_total = turn_output + turn_input

                            self.latest_output_tokens = turn_output
                            self.latest_input_tokens = turn_input
                            self.latest_thinking_tokens = turn_thinking
                            self.latest_cache_read_tokens = turn_cache
                            self.session_total_tokens = cum_total
                            self.session_cache_tokens = cum_cache
                            self.total_tokens_used = turn_total

                            # Store baseline for next turn's delta and persist
                            self.last_cumulative_usage = {
                                "input_tokens": cum_in,
                                "output_tokens": cum_out,
                                "thinking_tokens": cum_think,
                                "cache_read_tokens": cum_cache,
                                "total_tokens": cum_total,
                            }
                            config.last_cumulative_usage = dict(self.last_cumulative_usage)
                            config.save_settings()
                            self.session_turn_count += 1
                            bus.token_usage_updated.emit(turn_total)

                except json.JSONDecodeError:
                    bus.terminal_output_received.emit(raw_line)
                    full_response_acc.append(raw_line)
                    bus.token_chunk_received.emit(raw_line)
                    bus.core_pulse_triggered.emit(0.6)

            if stdin_writer is not None:
                stdin_writer.join(timeout=5.0)
            self._current_process.stdout.close()
            ret_code = self._current_process.wait()

        except Exception as e:
            err_msg = f"[Entropy AI Hata] agy CLI yürütülemedi: {str(e)}\n"
            try:
                bus.terminal_output_received.emit(err_msg)
            except (RuntimeError, Exception):
                pass
            full_response_acc.append(err_msg)
            ret_code = -1

        finally:
            if lock_acquired:
                try:
                    if is_exclusive:
                        project_lock_manager.release_write(project_dir)
                    else:
                        project_lock_manager.release_read(project_dir)
                except Exception:
                    pass

            next_task = None
            with self._lock:
                self._is_running = False
                self._current_process = None
                if self._prompt_queue:
                    next_task = self._prompt_queue.pop(0)
                    self._is_running = True

            full_text = "".join(full_response_acc)
            try:
                self._save_chat_turn(raw_user_prompt, full_text)
                bus.core_state_changed.emit("idle")
                bus.agent_turn_completed.emit(full_text)
            except (RuntimeError, Exception):
                pass

            # Bağlam doluluğu tur BİTTİKTEN sonra ölçülür: girdi token'ı ancak
            # result olayıyla belli olur, öncesinde ölçüm bir önceki turu
            # yansıtırdı. Eşik aşılırsa bus.context_pressure yayılır ve (varsa)
            # aktarım sayfasıyla geçmiş sıkıştırılır.
            try:
                self.check_context_pressure()
            except Exception:
                pass

            # Auto-recovery only if AGY produced truly empty output or was denied
            stripped_text = full_text.strip()
            is_truly_empty_or_denied = (
                (len(stripped_text) < 50 and (not stripped_text or "jetski: no output produced" in stripped_text or ret_code != 0)) or
                "auto-denied" in stripped_text
            )
            # Never reset if rich output (> 200 chars) was successfully generated
            if len(full_text) <= 200 and is_truly_empty_or_denied and self.current_conversation_id:
                bus.terminal_output_received.emit(
                    "\n[Entropy Core] Oturum kilitlendi veya yanıtsız kaldı. Gelecek mesaj için temiz oturuma geçiliyor...\n"
                )
                self.current_conversation_id = None
                config.last_conversation_id = None
                config.save_settings()
                self.last_cumulative_usage = {
                    "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "cache_read_tokens": 0, "total_tokens": 0
                }
                self.session_turn_count = 0

            # Auto-save research reports and technical dossiers (including autonomous scheduled tasks)
            is_err = "jetski: no output produced" in full_text or "auto-denied" in full_text or "Traceback" in full_text
            is_task_prompt = "[otonom planlı görev:" in raw_user_prompt.lower()
            is_explicit_learn = bool(re.search(r'(?:^|\s)/learn\b', raw_user_prompt, re.IGNORECASE))
            is_explicit_research = is_explicit_learn or any(w in raw_user_prompt.lower() for w in [
                "araştır", "araştırma yap", "rapor hazırla", "raporla", "analiz et", "derinlemesine incele", "dossier", "dokümantasyon oluştur"
            ])
            has_markdown_structure = ("# " in full_text or "## " in full_text) and len(full_text) > 250

            if not is_err and (is_task_prompt or (is_explicit_research and has_markdown_structure)):
                try:
                    from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
                    from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
                    vm = ObsidianVaultManager()

                    if is_task_prompt:
                        match = re.search(r"\[OTONOM PLANLI GÖREV:\s*([^\]]+)\]", raw_user_prompt, re.IGNORECASE)
                        task_name = match.group(1).strip() if match else "Otonom Görev"
                        time_tag = datetime.datetime.now().strftime("%Y%m%d_%H%M")
                        clean_title = f"Gorev_{task_name.replace(' ', '_')}_{time_tag}"
                    else:
                        clean_prompt = re.sub(r'^(?:\[SİZ\]:\s*)?', '', raw_user_prompt.strip(), flags=re.IGNORECASE)
                        clean_prompt = re.sub(r'^(?:/[a-zA-Z0-9_\-:]+\s*)+', '', clean_prompt.strip())
                        first_line = clean_prompt.strip().split("\n")[0][:40]
                        clean_title = re.sub(r'[\\/*?:"<>|]', "", first_line).strip() or "Araştırma Raporu"

                    proj_name = self.active_project_dir.name if self.active_project_dir else None
                    # Rapor, üreten yeteneğe atfedilir: Skills/<yetenek>/Reports/ altına
                    # düşer ve skill: etiketi alır. Bu atıf olmadan yordam damıtma o
                    # yetenek için kaynak bulamaz (eski kasada 0 rapor atıflıydı).
                    rep_path = vm.save_research_report(
                        clean_title,
                        full_text,
                        project_name=proj_name,
                        skill_name=(target_skill.name if target_skill else None),
                    )

                    # Extract distilled summary (Layer 6 consolidation) rather than storing massive full text
                    paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip() and not p.startswith("#")]
                    distilled_summary = paragraphs[0][:250] if paragraphs else full_text[:200]

                    # Also store distilled summary in cognitive memory graph
                    try:
                        cog = CognitiveMemorySystem()
                        cog.store_node(
                            category="semantic",
                            content=f"Araştırma/Görev Özeti [{clean_title}]: {distilled_summary}",
                            importance=0.88,
                            metadata={
                                "source": "task_or_research",
                                "path": str(rep_path),
                                "skill": target_skill.name if target_skill else None
                            }
                        )
                    except Exception:
                        pass

                    if is_task_prompt:
                        bus.task_notification.emit(task_name, task_name, str(rep_path))
                    else:
                        bus.report_created.emit(str(rep_path))
                    bus.cognitive_memory_updated.emit()
                    bus.knowledge_graph_updated.emit()

                    bus.terminal_output_received.emit(
                        f"\n[📚 Araştırma Raporu & Hafıza Kaydedildi]: '{clean_title}.md' bilişsel hafızaya işlendi ve Obsidian kasanıza kaydedildi.\n"
                    )
                except Exception:
                    pass

            # Automatically log interaction to Obsidian Daily Note
            try:
                from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
                vm = ObsidianVaultManager()
                short_p = raw_user_prompt.replace("\n", " ")[:60]
                short_r = full_text.replace("\n", " ")[:100]
                vm.append_daily_log(f"- **Etkileşim**: {short_p} -> {short_r}...")
            except Exception:
                pass

            if next_task:
                next_prompt = next_task[0]
                next_imgs = next_task[1] if len(next_task) > 1 else None
                next_pdfs = next_task[2] if len(next_task) > 2 else None
                next_skill = next_task[3] if len(next_task) > 3 else None
                next_mode = next_task[4] if len(next_task) > 4 else "accept-edits"
                next_proj = next_task[5] if len(next_task) > 5 else None
                next_thread = threading.Thread(
                    target=self._execute_prompt_worker,
                    args=(next_prompt, next_imgs, next_pdfs, next_skill, next_mode, next_proj),
                    daemon=True
                )
                next_thread.start()

    def terminate_current_process(self):
        """
        Cancel the currently active agy execution and its child language_server process tree.

        Kilit yalnızca sürecin alınması ve durumun sıfırlanması için tutulur.
        taskkill + wait(2s) kilidin içinde çalışırsa: bu metot arayüz iş
        parçacığından çağrıldığı için pencere saniyelerce donar ve aynı anda
        işçinin finally bloğu (aynı kilidi isteyen) bekler. terminate_background_task
        zaten bu deseni kullanıyordu; ikisi artık aynı.
        """
        with self._lock:
            proc = self._current_process if self._is_running else None
            if proc is None:
                return
            self._is_running = False

        try:
            pid = proc.pid
            if sys.platform == "win32":
                subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except Exception:
                pass
            bus.terminal_output_received.emit("\n[Entropy AI] İşlem kullanıcı tarafından durduruldu.\n")
        except Exception:
            pass
        bus.core_state_changed.emit("idle")

    def terminate_background_task(self, task_id: str):
        """Cancel an autonomous background task and its child language_server process tree."""
        with self._lock:
            proc = self._background_processes.get(task_id)
        if proc and proc.poll() is None:
            try:
                pid = proc.pid
                if sys.platform == "win32" or os.name == "nt":
                    subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    proc.terminate()
                try:
                    proc.wait(timeout=2.0)
                except Exception:
                    pass
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Kapanış
    # ------------------------------------------------------------------

    @staticmethod
    def _kill_tree(proc, wait_budget: float) -> None:
        """Süreci ve TÜM çocuklarını öldürür (Windows'ta taskkill /T)."""
        try:
            if proc.poll() is not None:
                return
        except Exception:
            return
        try:
            pid = proc.pid
            if sys.platform == "win32" or os.name == "nt":
                # /T şart: agy kendi altında language_server ve MCP süreçleri
                # açıyor. Yalnız ebeveyni öldürmek onları öksüz bırakır ve
                # uygulama kapandıktan sonra da CPU/port tutmaya devam ederler.
                subprocess.run(
                    f"taskkill /F /T /PID {pid}",
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            else:
                proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=max(0.0, wait_budget))
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def shutdown(self, timeout: float = 3.0) -> Dict[str, int]:
        """
        Uygulama kapanırken köprüyü düzenli biçimde söndürür.

        Neden: tepsiden çıkış, son pencerenin kapatılması ve tek kopya devri
        yollarının üçü de süreci sonlandırıyordu ama çalışan agy süreçlerine
        hiç dokunmuyordu. Sonuç: arka plan görevi (damıtma, konsolidasyon,
        zamanlanmış araştırma) ve altındaki language_server ağacı öksüz kalıp
        çalışmayı sürdürüyor, ledger'daki satır sonsuza dek RUNNING kalıyordu;
        bir sonraki açılışta `mark_orphans_failed` bunları "başarısız" diye
        işaretliyor, kullanıcı ise hiç istemediği bir hata görüyordu.

        Sırayla: yeni iş kabulünü kapat -> tüm süreç ağaçlarını taskkill /T ile
        indir -> RUNNING/PENDING ledger satırlarını CANCELLED yap -> yetenek
        izleyicisini ve yan iş parçacıklarını (RAG ısıtma vb.) durdur.

        Toplam bekleme `timeout` saniyeyi aşmaz: bu metot arayüz iş
        parçacığından (aboutToQuit) çağrılır, uzaması kapanışı dondurur.
        Yeniden çağrı güvenlidir.

        Döndürdüğü sayaç: {"processes": öldürülen süreç, "tasks": iptal edilen
        ledger satırı, "threads": beklenen yan iş parçacığı}.
        """
        deadline = time.monotonic() + max(0.0, float(timeout))
        with self._lock:
            if self._shutting_down:
                return {"processes": 0, "tasks": 0, "threads": 0}
            self._shutting_down = True
        # Etkileşimli terminaller önce salıverilir: bekleyen işçi iş parçacığı
        # `wait_for_followup`tan çıkmazsa aşağıdaki taskkill'in ardından boru
        # hatasıyla uyanır ve kapanışı geciktirir.
        self._interactive_sessions.close_all("uygulama kapanıyor")
        with self._lock:
            procs = list(self._background_processes.items())
            self._background_processes.clear()
            current = self._current_process
            self._current_process = None
            self._is_running = False
            self._prompt_queue.clear()
            side_threads = list(self._side_threads)
            self._side_threads.clear()

        killed = 0
        for _task_id, proc in procs:
            try:
                alive = proc.poll() is None
            except Exception:
                alive = False
            self._kill_tree(proc, wait_budget=max(0.0, deadline - time.monotonic()))
            killed += int(alive)
        if current is not None:
            try:
                alive = current.poll() is None
            except Exception:
                alive = False
            self._kill_tree(current, wait_budget=max(0.0, deadline - time.monotonic()))
            killed += int(alive)

        cancelled = 0
        try:
            # Modül düzeyindeki task_ledger kullanılır, yerel import edilmez:
            # entropy.core paketi `from .task_ledger import task_ledger` yaptığı
            # için `entropy.core.task_ledger` adı modülü değil TaskLedger
            # örneğini gösteriyor; yerel import testlerde (ve ileride başka bir
            # yalıtımda) yanlış nesneyi çözerdi.
            cancelled = task_ledger.cancel_active("Uygulama kapandı; görev yarıda kesildi.")
        except Exception:
            pass

        try:
            from entropy.skills.manager import stop_skill_watcher

            stop_skill_watcher()
        except Exception:
            pass

        joined = 0
        for t in side_threads:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                if t.is_alive():
                    t.join(timeout=remaining)
                joined += 1
            except Exception:
                pass

        return {"processes": killed, "tasks": cancelled, "threads": joined}
