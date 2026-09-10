"""12-Layer Cognitive Memory Architecture (Mem0 + Supabase pgvector & Local SQLite Fallback)."""

import hashlib
import json
import logging
import math
import os
import re
import sqlite3
import threading
import time
from collections import Counter, OrderedDict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from entropy.core.config import config
from entropy.memory.categories import (
    DEFAULT_RECALL_CATEGORIES,
    EPISODIC,
    normalize_category,
)
from entropy.memory.gate import (
    ACTION_GRAY as GATE_GRAY,
    ACTION_NOOP as GATE_NOOP,
    ACTION_REJECT as GATE_REJECT,
    ACTION_SUPERSEDE as GATE_SUPERSEDE,
    MemoryGate,
    gate_enabled,
)

# Faz 10-A: bellek katmanı loglara HİÇ yazmıyordu (teşhis notu §A.1: 363 satırlık
# entropy.log'da "cognitive_memory", "embedding", "recall", "dream" için 0 eşleşme).
# Sessiz `except Exception: pass` blokları yüzünden kullanıcı "hafızam çalışmıyor
# ama hata da görmüyorum" durumundaydı. Artık her yutulan istisna buraya yazılır.
logger = logging.getLogger("entropy.memory.cognitive")

# `last_errors` listesinin üst sınırı: hata döngüsünde bellek şişmesin.
MAX_TRACKED_ERRORS = 20

# Rüya döngüsünde bir turda yenilenecek en fazla gömme sayısı. Sinirsel çıkarım
# metin başına ~90 ms; 200 satır ~18 sn eder ve rüya zaten arka plan görevidir.
REEMBED_DREAM_BATCH = 200

# Açılış ısınmasında yenilenecek gömme sayısı: açılışı geciktirmemek için küçük.
REEMBED_WARMUP_BATCH = 32


class DreamResult(list):
    """
    `dream_and_consolidate` dönüşü: sentezlenen kuralların listesi + hata kaydı.

    Neden list alt sınıfı: eski çağıranlar (`main.py:157`,
    `ui/widgets/tasks_widget.py:425`) dönüşü liste gibi kullanıyor. Sözlüğe
    çevirmek onları kırardı; liste kalıp `.errors` / `.report` eklemek kısmi
    başarısızlığı görünür kılar ve geriye dönük uyumu korur.
    """

    def __init__(self, *args):
        super().__init__(*args)
        self.errors: List[Dict[str, Any]] = []
        self.report: Dict[str, Any] = {}

    @property
    def ok(self) -> bool:
        return not self.errors

# numpy sert bir bağımlılık (pyproject) ama yokluğunda bellek modülü tamamen
# çökmemeli: vektörleştirilmiş geri çağırma kapanır, eski skaler yol çalışır.
try:
    import numpy as _np
except Exception:  # pragma: no cover - numpy kurulu olmayan ortam
    _np = None
    logger.warning("numpy yüklenemedi: vektörleştirilmiş geri çağırma kapalı, skaler yola düşülüyor")

@dataclass
class CognitiveMemoryNode:
    id: str
    # Kapalı küme (Faz 11.1, memory/categories.py): working | episodic |
    # semantic | procedural. Kimlik/kural (L4) kategori değil, `is_identity`
    # bayrağıdır.
    category: str
    content: str
    importance: float   # 0.0 to 1.0
    created_at: float   # epoch timestamp
    last_accessed: float
    access_count: int = 1
    metadata: Dict[str, Any] = None
    embedding: Optional[List[float]] = None
    # -- şema v2 alanları ------------------------------------------------
    provenance: str = ""            # kaynak yolu / URL / görev künyesi
    confidence: float = 0.5         # güven bandı
    valid_from: Optional[float] = None
    valid_to: Optional[float] = None  # None = hâlâ geçerli
    archived: int = 0               # ölçülü unutma bayrağı (silme yok)
    novelty: float = 1.0            # kapının verdiği yenilik puanı
    is_identity: int = 0            # L4 kimlik / kullanıcı onaylı kural

    def calculate_ebbinghaus_strength(self, current_time: Optional[float] = None, decay_rate: float = 0.05) -> float:
        """Layer 5: Ebbinghaus Forgetting Curve strength calculation."""
        now = current_time or time.time()
        days_elapsed = max(0.0, (now - self.last_accessed) / 86400.0)
        # Repetition stabilizes memory (increased access_count flattens decay)
        stability = 1.0 + math.log(self.access_count + 1)
        strength = self.importance * math.exp(- (decay_rate * days_elapsed) / stability)
        return max(0.0, min(1.0, strength))

# Gömme modeli. Çok dilli olması zorunlu: kullanıcı içeriğinin ve sorguların
# büyük kısmı Türkçe ve önceki İngilizce model (BAAI/bge-small-en-v1.5) Türkçede
# ayırt edemiyordu. Ölçüm (6 Türkçe yönlendirme sorgusu, medya vs finans):
#     bge-small-en-v1.5   : 4/6 doğru, sınıflar arası ortalama ayrım 0.041
#     multilingual-MiniLM : 5/6 doğru, ortalama ayrım 0.179  (4.4x daha geniş)
# 0.04'lük ayrım gürültü seviyesindedir; hybrid_recall'da vektör ağırlığı 0.40
# olduğu için skorun bu kısmı Türkçe sorgularda neredeyse rastgele çalışıyordu.
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384

# Yedek model: çok dilli model indirilemezse en azından İngilizce içerik çalışsın.
EMBEDDING_FALLBACK_MODEL = "BAAI/bge-small-en-v1.5"

# Gömme önbelleğinin üst sınırı (metin sayısı). 512 x 384 float ~ 1,5 MB.
EMBEDDING_CACHE_SIZE = 512


class LocalEmbeddingEngine:
    """Zero-API, 100% offline neural embedding engine with fast fallback (T2.1)."""
    _instance = None
    _model = None
    _is_neural = False
    _model_name = ""
    # Kurulum kilidi: ısıtma iş parçacığı ile ana iş parçacığı aynı anda
    # get_instance() çağırırsa model iki kez yüklenirdi (~2 sn boşa gider).
    _init_lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Model değişiminden sonra yeniden kurulum için (testler ve ayar değişikliği)."""
        with cls._init_lock:
            cls._instance = None

    def __init__(self):
        self._model = None
        self._is_neural = False
        self._model_name = ""
        # Gömme önbelleği: sinirsel çıkarım metin başına ~90 ms. Aynı metin
        # (sorgu, yetenek tanımı, düğüm içeriği) bir oturumda defalarca
        # gömülüyordu; sonuç aynı metin için birebir aynı olduğundan tutulabilir.
        # Önbellek örneğe bağlıdır: model değişince reset_instance() ile düşer.
        self._cache: "OrderedDict[str, List[float]]" = OrderedDict()
        self._cache_lock = threading.Lock()
        for candidate in (EMBEDDING_MODEL_NAME, EMBEDDING_FALLBACK_MODEL):
            try:
                from fastembed import TextEmbedding

                self._model = TextEmbedding(model_name=candidate)
                self._is_neural = True
                self._model_name = candidate
                break
            except Exception:
                logger.warning("Gömme modeli yüklenemedi: %s", candidate, exc_info=True)
                continue
        if not self._is_neural:
            logger.error(
                "Hiçbir sinirsel gömme modeli yüklenemedi; hash tabanlı yedeğe düşüldü. "
                "Anlamsal geri çağırma kalitesi düşecek."
            )

    @property
    def model_name(self) -> str:
        """Aktif modelin adı; boş string sinirsel modelin yüklenemediğini gösterir."""
        return self._model_name

    def embed_text(self, text: str) -> List[float]:
        """Generate a 384-dimensional dense embedding vector (önbellekli)."""
        return self.embed_text_status(text)[0]

    def embed_text_status(self, text: str) -> Tuple[List[float], str]:
        """
        Gömme + durumu döndürür: `("ok"|"fallback"|"empty")`.

        Faz 10-A: eski `embed_text` sinirsel çıkarım patladığında sessizce hash
        yedeğine düşüyordu. Hash vektörü sinirsel uzayla aynı uzayda DEĞİLDİR;
        o düğümün anlamsal geri çağırması kalıcı olarak ölür. Çağıran artık
        durumu görüp düğümü `embedding_status='pending'` ile işaretleyebilir ve
        `reembed_stale()` sonradan doldurur.
        """
        if not text or not text.strip():
            return [0.0] * 384, "empty"

        with self._cache_lock:
            cached = self._cache.get(text)
            if cached is not None:
                self._cache.move_to_end(text)
                return list(cached), "ok"

        vector: Optional[List[float]] = None
        status = "ok"
        if self._is_neural and self._model is not None:
            try:
                vecs = list(self._model.embed([text]))
                vector = [float(x) for x in vecs[0]]
            except Exception:
                logger.warning(
                    "Gömme üretimi başarısız (%s), hash yedeğine düşülüyor; düğüm "
                    "yeniden gömme için işaretlenecek.", self._model_name, exc_info=True,
                )
                vector = None
        if vector is None:
            # Sinirsel model hiç yoksa bu beklenen durumdur (kalıcı hash modu);
            # model varken başarısızlıksa geçicidir ve yeniden denenmelidir.
            status = "fallback" if self._is_neural else "ok"
            vector = self._hash_dense_embedding(text, dim=384)

        with self._cache_lock:
            # Başarısız çıkarımın hash sonucu önbelleğe konmaz: aksi hâlde aynı
            # metin bir daha asla sinirsel olarak gömülemezdi.
            if status != "fallback":
                self._cache[text] = vector
                while len(self._cache) > EMBEDDING_CACHE_SIZE:
                    self._cache.popitem(last=False)
        return list(vector), status

    def cache_stats(self) -> Dict[str, int]:
        """Önbelleğin doluluğu; ölçüm ve testler için."""
        with self._cache_lock:
            return {"entries": len(self._cache), "capacity": EMBEDDING_CACHE_SIZE}

    def _hash_dense_embedding(self, text: str, dim: int = 384) -> List[float]:
        """Deterministic dense representation when neural model is unavailable or initializing."""
        vec = [0.0] * dim
        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            return vec
        for token in tokens:
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            sign = 1.0 if (h % 2 == 0) else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

_WARMUP_LOCK = threading.Lock()
_WARMUP_THREAD: Optional[threading.Thread] = None


def embedding_warmup_enabled() -> bool:
    """
    Gömme motorunun arka planda ısıtılıp ısıtılmayacağı.

    ENTROPY_EMBEDDING_WARMUP=0 (ya da false/no/off) ile kapatılır. Ölçüm alırken
    ya da modelin hiç yüklenmemesi istendiğinde bayrak kapatılabilir olmalı.
    """
    raw = (os.environ.get("ENTROPY_EMBEDDING_WARMUP") or "").strip().lower()
    return raw not in ("0", "false", "no", "off")


def maintenance_enabled() -> bool:
    """
    Açılış bakımı (depo uzlaştırma + bekleyen gömme tamamlama) açık mı.

    ENTROPY_MEMORY_MAINTENANCE=0 ile kapatılır; ölçüm alırken ya da salt okunur
    bir profille açılırken kapatılabilir olmalıdır.
    """
    # Test koşumu üretim profiline dokunmamalı: bazı testler (ör.
    # tests/test_ui_modes.py:186) varsayılan yolla `CognitiveMemorySystem()`
    # kuruyor; arka planda uzlaştırma başlatmak gerçek veritabanını
    # sessizce değiştirirdi.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    raw = (os.environ.get("ENTROPY_MEMORY_MAINTENANCE") or "").strip().lower()
    return raw not in ("0", "false", "no", "off")


def warm_embedding_engine(blocking: bool = False) -> Optional[threading.Thread]:
    """
    fastembed modelini arka plan iş parçacığında yükler (~1,9 sn tek seferlik).

    Ana iş parçacığı bloklanmaz ve Qt'ye hiç dokunulmaz: iş parçacığı yalnızca
    LocalEmbeddingEngine.get_instance() çağırır, sonucu sınıf değişkenine yazar.
    İlk gerçek hybrid_recall çağrısı bu yüzden modeli hazır bulur.
    """
    global _WARMUP_THREAD
    if not embedding_warmup_enabled():
        return None
    if LocalEmbeddingEngine._instance is not None:
        return None

    def _run():
        try:
            LocalEmbeddingEngine.get_instance()
        except Exception:
            # Isıtma en iyi çaba: başarısız olursa ilk çağrı eskisi gibi yükler.
            logger.warning("Gömme motoru ısıtması başarısız", exc_info=True)

    with _WARMUP_LOCK:
        if _WARMUP_THREAD is not None and _WARMUP_THREAD.is_alive():
            thread = _WARMUP_THREAD
        else:
            thread = threading.Thread(
                target=_run, name="entropy-embedding-warmup", daemon=True
            )
            _WARMUP_THREAD = thread
            thread.start()
    if blocking:
        thread.join()
    return thread


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two dense vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = 0.0
    norm1 = 0.0
    norm2 = 0.0
    for a, b in zip(v1, v2):
        dot += a * b
        norm1 += a * a
        norm2 += b * b
    if norm1 <= 0.0 or norm2 <= 0.0:
        return 0.0
    sim = dot / (math.sqrt(norm1) * math.sqrt(norm2))
    return max(0.0, min(1.0, sim))

def compute_bm25_score(query_tokens: List[str], doc_tokens: List[str], avg_doc_len: float = 25.0, k1: float = 1.2, b: float = 0.75) -> float:
    """BM25 term frequency saturation and document length normalization (T2.2)."""
    if not query_tokens or not doc_tokens:
        return 0.0
    doc_len = len(doc_tokens)
    score = 0.0
    for q in query_tokens:
        count = doc_tokens.count(q)
        if count > 0:
            tf = (count * (k1 + 1)) / (count + k1 * (1 - b + b * (doc_len / max(1.0, avg_doc_len))))
            score += tf
    return min(1.0, score / max(1.0, len(query_tokens) * 1.5))

BM25_K1 = 1.2
BM25_B = 0.75
BM25_AVG_DOC_LEN = 25.0

# Şema v2 sütunları; `get_node` / `get_all_nodes` bunları da okur.
V2_COLUMNS = ", provenance, confidence, valid_from, valid_to, archived, novelty, is_identity"


def _row_to_memory_node(row) -> "CognitiveMemoryNode":
    """Tek satır -> düğüm. Şema v2 sütunları yoksa (eski dosya) varsayılan alınır."""
    return CognitiveMemoryNode(
        id=row[0],
        category=row[1],
        content=row[2],
        importance=row[3],
        created_at=row[4],
        last_accessed=row[5],
        access_count=row[6],
        metadata=json.loads(row[7] or "{}"),
        embedding=json.loads(row[8]) if (len(row) > 8 and row[8]) else None,
        provenance=(row[9] if len(row) > 9 else "") or "",
        confidence=(row[10] if len(row) > 10 and row[10] is not None else 0.5),
        valid_from=(row[11] if len(row) > 11 else None),
        valid_to=(row[12] if len(row) > 12 else None),
        archived=int(row[13] or 0) if len(row) > 13 else 0,
        novelty=(row[14] if len(row) > 14 and row[14] is not None else 1.0),
        is_identity=int(row[15] or 0) if len(row) > 15 else 0,
    )


_RECALL_COLUMNS = (
    "id, category, content, importance, created_at, last_accessed, "
    "access_count, metadata_json, embedding_json, embedding_model"
)


class _RecallIndex:
    """
    Hibrit geri çağırmanın bellek içi tarama yapısı.

    Neden var: her sorgu 846 satırı SQLite'tan okuyup her satırın 384 boyutlu
    gömmesini JSON'dan çözüyor, içeriğini yeniden belirteçliyor ve kosinüsü saf
    Python döngüsüyle hesaplıyordu (sorgu başına ~214-350 ms). Bu yapının hepsi
    bir kez kurulur; sorgu yalnızca bir matris çarpımı ve ters indeks araması
    yapar. Veritabanı imzası (satır sayısı + son erişim + erişim toplamı + aktif
    model) değişince yapı yeniden kurulur.
    """

    __slots__ = (
        "signature", "model", "size",
        "ids", "categories", "contents", "importances", "created_ats",
        "last_accesseds", "access_counts", "metadata_jsons", "embeddings",
        "matrix", "imp_arr", "acc_arr", "last_arr", "doc_lens", "postings",
    )

    def __init__(self, signature: tuple, model: str):
        self.signature = signature
        self.model = model
        self.size = 0
        self.ids: List[str] = []
        self.categories: List[str] = []
        self.contents: List[str] = []
        self.importances: List[float] = []
        self.created_ats: List[float] = []
        self.last_accesseds: List[float] = []
        self.access_counts: List[int] = []
        self.metadata_jsons: List[Optional[str]] = []
        self.embeddings: List[Optional[List[float]]] = []
        self.matrix = None            # (n, dim) satırları birim boya indirgenmiş
        self.imp_arr = None
        self.acc_arr = None
        self.last_arr = None
        self.doc_lens = None
        self.postings: Dict[str, tuple] = {}

    def node_at(self, i: int) -> "CognitiveMemoryNode":
        """Önbellekteki alanlardan yeni bir düğüm nesnesi üretir (paylaşılan nesne dönmez)."""
        return CognitiveMemoryNode(
            id=self.ids[i],
            category=self.categories[i],
            content=self.contents[i],
            importance=self.importances[i],
            created_at=self.created_ats[i],
            last_accessed=self.last_accesseds[i],
            access_count=self.access_counts[i],
            metadata=json.loads(self.metadata_jsons[i] or "{}"),
            embedding=list(self.embeddings[i]) if self.embeddings[i] else None,
        )


def default_cognitive_db_path() -> Path:
    """
    Varsayilan bilissel bellek veritabani yolu (TEK KAYNAK).

    `ENTROPY_COGNITIVE_DB` gecersiz kilar. Uc ayri yerde (`vault_manager`,
    `memory_inspector_dialog`, `reports_viewer`) yol elle kuruluyordu; bu
    yuzden test yalitimi delinip kullanicinin GERCEK veritabani aciliyordu.
    """
    override = os.environ.get("ENTROPY_COGNITIVE_DB", "").strip()
    if override:
        path = Path(override)
    else:
        path = Path.home() / ".entropy" / "cognitive_memory.db"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return path


class CognitiveMemorySystem:
    """Manages multi-layered cognitive memory with Supabase pgvector and offline SQLite fallback."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            # `ENTROPY_COGNITIVE_DB` varsayilan yolu gecersiz kilar. Testler
            # bunu tmp'ye yonlendirir: yol gecmeyen her `CognitiveMemorySystem()`
            # aksi hâlde kullanicinin gercek `~/.entropy/cognitive_memory.db`
            # dosyasina yaziyordu (kasa yalitiminin bellek karsiligi).
            self.db_path = default_cognitive_db_path()
            self._is_default_db = True
        else:
            self.db_path = Path(db_path)
            self._is_default_db = False
        
        # Hibrit geri çağırma önbelleği; ilk sorguda kurulur.
        self._recall_index: Optional[_RecallIndex] = None
        self._recall_stat_sig: Optional[tuple] = None
        self._recall_lock = threading.RLock()

        # Faz 10-A: sessiz istisnaların görünür kaydı. En fazla
        # MAX_TRACKED_ERRORS girdi tutulur; UI/teşhis buradan okur.
        self.last_errors: List[Dict[str, Any]] = []
        self._error_lock = threading.Lock()
        # Graf katmanı köprüsü (tembel kurulur; graph_store bu modülü içe
        # aktardığı için modül düzeyinde import döngü yaratır).
        self._graph_store = None
        self._graph_lock = threading.RLock()
        self._graph_sync_enabled = True

        # Yazma kapısı (Faz 11.2). Tembel kurulur ki `ENTROPY_MEMORY_GATE`
        # ve katı kip bayrağı örnek ömrü boyunca değil, ilk yazımda okunsun.
        self._gate: Optional[MemoryGate] = None
        self.last_gate_decision = None

        self._init_sqlite_db()
        self._seed_ego_identity()
        # Gömme motoru (~1,9 sn) arka planda yüklenir; bellek sistemi uygulama
        # açılışında kurulduğu için ısıtma da orada başlamış olur. Ana iş
        # parçacığı bloklanmaz, Qt'ye dokunulmaz, bayrakla kapatılabilir.
        try:
            warm_embedding_engine()
        except Exception:
            self._record_error("warm_embedding_engine", "Gömme motoru ısıtması başlatılamadı")
        # Açılış bakımı yalnızca gerçek profil veritabanı için otomatik koşar;
        # testlerin geçici veritabanları arka plan iş parçacığı açmaz (belirlilik).
        if self._is_default_db:
            self.startup_maintenance(background=True)

    # -- açılış bakımı (Faz 10-A) -----------------------------------------

    def startup_maintenance(self, background: bool = True) -> Optional[Dict[str, Any]]:
        """
        Açılışta iki depoyu uzlaştırır ve bekleyen gömmeleri tamamlar.

        Idempotenttir ve sapma/bekleyen yoksa neredeyse bedavadır (iki COUNT
        sorgusu). Model çağrısı yapmaz, kota harcamaz.
        """
        # Bayrak yalnızca kendiliğinden (arka planda) koşmayı kapatır; açık
        # çağrı (background=False) her zaman çalışır, çünkü niyet açıktır.
        if background and not maintenance_enabled():
            return None
        if background:
            thread = threading.Thread(
                target=self._run_startup_maintenance, name="entropy-memory-maintenance", daemon=True
            )
            thread.start()
            return None
        return self._run_startup_maintenance()

    def _run_startup_maintenance(self) -> Dict[str, Any]:
        started = time.time()
        out: Dict[str, Any] = {"reconciled": None, "reembedded": None}
        try:
            if self.store_drift() > 0:
                out["reconciled"] = self.reconcile_stores()
        except Exception as exc:
            self._record_error("startup_maintenance", "Açılış uzlaştırması başarısız", exc)
        try:
            if self.pending_embedding_count() > 0:
                out["reembedded"] = self.reembed_stale(batch_limit=REEMBED_WARMUP_BATCH)
        except Exception as exc:
            self._record_error("startup_maintenance", "Bekleyen gömmeler tamamlanamadı", exc)
        out["duration_s"] = round(time.time() - started, 3)
        return out

    def pending_embedding_count(self) -> int:
        """Gömmesi başarısız olup 'pending' işaretlenmiş satır sayısı."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM cognitive_nodes "
                    "WHERE COALESCE(embedding_status, 'ok') = 'pending'"
                ).fetchone()
            return int(row[0]) if row else 0
        except sqlite3.Error:
            return 0

    # -- hata görünürlüğü (Faz 10-A) --------------------------------------

    def _record_error(self, stage: str, message: str, exc: Optional[BaseException] = None) -> Dict[str, Any]:
        """
        Yutulan bir istisnayı görünür kılar: log + sayaç + (varsa) bus sinyali.

        `stage` işlev adıdır; UI aynı aşamanın tekrarını gruplayabilsin diye ayrı
        alanda tutulur. Dönüş değeri çağıranın `errors` listesine ekleyebileceği
        sözlüktür.
        """
        detail = f"{message}: {exc}" if exc is not None else message
        logger.warning("[bellek:%s] %s", stage, detail, exc_info=exc is not None)
        entry = {"stage": stage, "message": message, "error": str(exc) if exc else "", "at": time.time()}
        with self._error_lock:
            self.last_errors.append(entry)
            while len(self.last_errors) > MAX_TRACKED_ERRORS:
                self.last_errors.pop(0)
        # UI'ya duyuru: `bus.memory_error` sinyali HENÜZ tanımlı değil (core/**
        # bu fazın kapsamı dışında). Sinyal eklendiğinde bu kod kendiliğinden
        # yayınlamaya başlar; yoksa sessizce atlanır.
        try:
            from entropy.core.event_bus import bus  # yerel içe aktarma: döngü ve açılış maliyeti yok

            signal = getattr(bus, "memory_error", None)
            if signal is not None:
                signal.emit(stage, detail)
        except Exception:
            pass
        return entry

    def clear_errors(self) -> None:
        with self._error_lock:
            self.last_errors.clear()

    def _init_sqlite_db(self):
        """Initialize local SQLite persistence schema with embedding vector support (T2.1)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cognitive_nodes (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance REAL DEFAULT 0.5,
                    created_at REAL,
                    last_accessed REAL,
                    access_count INTEGER DEFAULT 1,
                    metadata_json TEXT,
                    embedding_json TEXT
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_category ON cognitive_nodes (category);
            """)
            # Migration check: ensure embedding_json column exists
            cursor.execute("PRAGMA table_info(cognitive_nodes)")
            cols = [row[1] for row in cursor.fetchall()]
            if "embedding_json" not in cols:
                cursor.execute("ALTER TABLE cognitive_nodes ADD COLUMN embedding_json TEXT")
            # Gömmenin hangi modelle üretildiği kaydedilir. Farklı modeller farklı
            # vektör uzayları üretir; karışık uzaylarda kosinüs benzerliği anlamsız
            # sonuç verir ve bu sessizce olur. Model adı saklanınca eskiyen gömmeler
            # tespit edilip yeniden üretilebilir.
            if "embedding_model" not in cols:
                cursor.execute("ALTER TABLE cognitive_nodes ADD COLUMN embedding_model TEXT")
            # Faz 10-A: gömme üretimi patladığında düğüm ATILMAZ; hash yedeğiyle
            # yazılır ve burada 'pending' işaretlenir. reembed_stale() rüya
            # döngüsünde ve açılış ısınmasında bu satırları gerçek modelle doldurur.
            if "embedding_status" not in cols:
                cursor.execute("ALTER TABLE cognitive_nodes ADD COLUMN embedding_status TEXT DEFAULT 'ok'")
            # -- şema v2 (Faz 11.1) --------------------------------------
            # Hepsi idempotent ALTER: var olan veritabanı yerinde yükselir,
            # eski satırlar varsayılan değerle doldurulur.
            #   provenance : kaynak yolu / URL / görev künyesi. L2 anlamsal
            #                yazımın kabul koşulu (Manufactured Confidence:
            #                konsolidasyon kaynağı silince duyum kesin olguya
            #                dönüşüyor).
            #   confidence : güven bandı (0-1). Güçlü kaynak 0,75; zayıf 0,40.
            #   valid_from / valid_to : çift zamanlı geçerlilik (Zep deseni).
            #                `valid_to` NULL = hâlâ geçerli.
            #   archived   : ölçülü unutma. Silme YOK; bayrak (rate-distortion).
            #   novelty    : kapının verdiği yenilik puanı (1 - en yakın kosinüs).
            #   is_identity: L4 kimlik/kural bayrağı. Beşinci bir kategori
            #                açılmaz; kategori kapalı küme olarak dörtte kalır.
            for column, ddl in (
                ("provenance", "ALTER TABLE cognitive_nodes ADD COLUMN provenance TEXT DEFAULT ''"),
                ("confidence", "ALTER TABLE cognitive_nodes ADD COLUMN confidence REAL DEFAULT 0.5"),
                ("valid_from", "ALTER TABLE cognitive_nodes ADD COLUMN valid_from REAL"),
                ("valid_to", "ALTER TABLE cognitive_nodes ADD COLUMN valid_to REAL"),
                ("archived", "ALTER TABLE cognitive_nodes ADD COLUMN archived INTEGER DEFAULT 0"),
                ("novelty", "ALTER TABLE cognitive_nodes ADD COLUMN novelty REAL DEFAULT 1.0"),
                ("is_identity", "ALTER TABLE cognitive_nodes ADD COLUMN is_identity INTEGER DEFAULT 0"),
            ):
                if column not in cols:
                    cursor.execute(ddl)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_archived ON cognitive_nodes (archived)"
            )
            conn.commit()

    def reembed_stale(self, batch_limit: Optional[int] = None) -> Dict[str, int]:
        """
        Aktif modelden farklı bir modelle üretilmiş gömmeleri yeniden hesaplar.

        Model değişimi sonrası çağrılır. Yapılmazsa eski ve yeni vektörler aynı
        havuzda karışır ve benzerlik skorları güvenilmez olur.
        """
        engine = LocalEmbeddingEngine.get_instance()
        active = engine.model_name or "hash-fallback"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Faz 10-A: model uyuşmazlığına EK olarak 'pending' işaretli
            # (gömmesi başarısız olmuş) satırlar da yeniden gömülür.
            cursor.execute(
                "SELECT id, content FROM cognitive_nodes "
                "WHERE embedding_model IS NULL OR embedding_model != ? "
                "   OR COALESCE(embedding_status, 'ok') = 'pending'",
                (active,),
            )
            rows = cursor.fetchall()

        stale_total = len(rows)
        if batch_limit is not None:
            rows = rows[:batch_limit]

        updates = []
        failed = 0
        for node_id, content in rows:
            try:
                vector, status = engine.embed_text_status(content or "")
                if status == "fallback":
                    # Hâlâ üretilemiyor: 'pending' kalsın, bir sonraki turda denenir.
                    failed += 1
                    continue
                updates.append((json.dumps(vector), active, node_id))
            except Exception as exc:
                failed += 1
                self._record_error("reembed_stale", f"Yeniden gömme başarısız: {node_id}", exc)
                continue

        if updates:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.executemany(
                    "UPDATE cognitive_nodes SET embedding_json = ?, embedding_model = ?,"
                    " embedding_status = 'ok' WHERE id = ?",
                    updates,
                )
                conn.commit()
            self._invalidate_recall_index()
        if stale_total or failed:
            logger.info(
                "reembed_stale: %s bayat/pending satır, %s güncellendi, %s başarısız",
                stale_total, len(updates), failed,
            )

        if updates:
            self._invalidate_recall_index()
        return {"stale": stale_total, "reembedded": len(updates), "failed": failed, "model": active}

    def _seed_ego_identity(self):
        """Layer 12: Ensure core Ego / Identity persona node exists."""
        ego_id = "ego-entropy-core"
        if not self.get_node(ego_id):
            self._update_ego_identity()

    def _update_ego_identity(self):
        """Ensure core Ego / Identity persona node reflects current system capabilities."""
        ego_id = "ego-entropy-core"
        ego_content = (
            "I am Entropy AI, an autonomous agentic desktop operating system for Windows. "
            "I operate on-device using the Antigravity CLI without demanding external API keys. "
            "I integrate an Obsidian exocortex with bidirectional GraphRAG, 384-dimensional local neural vector embeddings, "
            "Python AST syntax-aware codebase indexing, and background dreaming consolidation."
        )
        # Faz 11.1: "ego" ARTIK BİR KATEGORİ DEĞİL. Kategori kapalı kümede
        # dört değerdir; kimlik `is_identity` bayrağıyla taşınır. Düğümün
        # kimliği (`ego-entropy-core`) korunur — arayüz grafiği ve testler
        # bu kimliğe bağlı.
        ego_node = CognitiveMemoryNode(
            id=ego_id,
            category="semantic",
            content=ego_content,
            importance=1.0,
            created_at=time.time(),
            last_accessed=time.time(),
            access_count=100,
            metadata={"type": "core_identity", "immutable": True},
            provenance="entropy:core_identity",
            confidence=1.0,
            novelty=1.0,
            is_identity=1,
        )
        self._save_node(ego_node)

    def migrate_and_clean_database(self) -> Dict[str, int]:
        """
        Audits existing SQLite database:
        - Removes corrupted nodes with replacement characters or malformed titles.
        - Backfills dense 384-d vector embeddings for all remaining nodes.
        - Synchronizes Ego node with current architectural invariants.
        """
        cleaned_count = 0
        reembedded_count = 0

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, category, content, importance, metadata_json, embedding_json FROM cognitive_nodes")
            rows = cursor.fetchall()

            for r in rows:
                nid, cat, content, importance, meta_json, emb_json = r
                # Check for corrupted encoding or fragmented garbage
                if "\ufffd" in content or "Aratrma" in content or len(content.strip()) < 5:
                    cursor.execute("DELETE FROM cognitive_nodes WHERE id = ?", (nid,))
                    cleaned_count += 1
                    continue

                # Check if embedding is missing or empty
                emb = json.loads(emb_json) if emb_json else None
                if not emb or len(emb) != EMBEDDING_DIM:
                    engine = LocalEmbeddingEngine.get_instance()
                    new_emb = engine.embed_text(content)
                    cursor.execute(
                        "UPDATE cognitive_nodes SET embedding_json = ?, embedding_model = ? WHERE id = ?",
                        (json.dumps(new_emb), engine.model_name or "hash-fallback", nid),
                    )
                    reembedded_count += 1

            conn.commit()

        self._invalidate_recall_index()
        self._update_ego_identity()
        return {"cleaned": cleaned_count, "reembedded": reembedded_count}

    def _generate_node_id(self, category: str, content: str) -> str:
        h = hashlib.sha256(f"{category}:{content.strip().lower()}".encode("utf-8")).hexdigest()[:16]
        return f"{category}-{h}"

    def _save_node(self, node: CognitiveMemoryNode, embedding_status: str = ""):
        # Kategori disiplini son savunma hattı: `_save_node` diske giden TEK
        # yoldur (record_memory, ego tohumu, konsolidasyon hepsi buradan geçer).
        # Serbest metin kategori burada kanonik dörtlüye indirgenir; kimlik
        # kovası açılmaz, bayrağa çevrilir.
        resolution = normalize_category(node.category)
        node.category = resolution.category
        if resolution.is_identity:
            node.is_identity = 1
        engine = LocalEmbeddingEngine.get_instance()
        if node.embedding is None or len(node.embedding) == 0:
            node.embedding, status = engine.embed_text_status(node.content)
            embedding_status = embedding_status or status
        active_model = engine.model_name or "hash-fallback"
        # Gömme sinirsel modelle üretilemediyse satır o modelin adıyla
        # etiketlenmemeli: reembed_stale bir daha asla dokunmazdı.
        if embedding_status == "fallback":
            active_model = "hash-fallback"
        status_col = "pending" if embedding_status == "fallback" else "ok"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cognitive_nodes (id, category, content, importance, created_at, last_accessed, access_count, metadata_json, embedding_json, embedding_model, embedding_status, provenance, confidence, valid_from, valid_to, archived, novelty, is_identity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    importance = excluded.importance,
                    last_accessed = excluded.last_accessed,
                    access_count = cognitive_nodes.access_count + 1,
                    metadata_json = excluded.metadata_json,
                    embedding_json = excluded.embedding_json,
                    embedding_model = excluded.embedding_model,
                    embedding_status = excluded.embedding_status,
                    provenance = CASE WHEN excluded.provenance != '' THEN excluded.provenance ELSE cognitive_nodes.provenance END,
                    confidence = excluded.confidence,
                    valid_to = excluded.valid_to,
                    archived = excluded.archived,
                    novelty = excluded.novelty,
                    is_identity = excluded.is_identity
            """, (
                node.id,
                node.category,
                node.content,
                node.importance,
                node.created_at,
                node.last_accessed,
                node.access_count,
                json.dumps(node.metadata or {}),
                json.dumps(node.embedding or []),
                active_model,
                status_col,
                node.provenance or "",
                node.confidence if node.confidence is not None else 0.5,
                node.valid_from if node.valid_from is not None else node.created_at,
                node.valid_to,
                int(node.archived or 0),
                node.novelty if node.novelty is not None else 1.0,
                int(node.is_identity or 0),
            ))
            conn.commit()
        self._invalidate_recall_index()
        # Faz 10-A (P0): yazma yolu artık TEK giriş noktasından iki depoya da
        # yazar. Önceden yalnızca cognitive_nodes güncelleniyordu ve graf
        # katmanı yalnızca elle koşturulan göçle doluyordu; gerçek veritabanında
        # 35 düğüm grafın dışında kalmıştı.
        self._sync_node_to_graph(node)

    # -- graf katmanı köprüsü (Faz 10-A, P0) ------------------------------

    def graph_store(self):
        """
        Aynı veritabanı dosyası üzerindeki `GraphStore` (tembel, süreç başına tek).

        `graph_store` modülü bu modülü içe aktardığı için import yereldir.
        Kurulum başarısızsa None döner; yazma yolu bundan etkilenmez.
        """
        if not self._graph_sync_enabled:
            return None
        with self._graph_lock:
            if self._graph_store is not None:
                return self._graph_store
            try:
                from entropy.memory.graph_store import GraphStore

                self._graph_store = GraphStore(memory=self)
            except Exception as exc:
                self._graph_sync_enabled = False
                self._record_error("graph_store", "Graf katmanı kurulamadı, senkron kapatıldı", exc)
                return None
            return self._graph_store

    def _sync_node_to_graph(self, node: CognitiveMemoryNode) -> bool:
        """Tek düğümü graf tablolarına yansıtır (kenarlar dâhil). Sessiz kalmaz."""
        store = self.graph_store()
        if store is None:
            return False
        try:
            store.sync_from_cognitive(node_ids=[node.id], similarity_edges=False)
            return True
        except Exception as exc:
            self._record_error("sync_node_to_graph", f"Düğüm grafa yazılamadı: {node.id}", exc)
            return False

    def reconcile_stores(self, similarity_edges: bool = True) -> Dict[str, Any]:
        """
        İki depo arasındaki sapmayı kapatır: `cognitive_nodes` \\ `nodes`.

        Idempotenttir: sapma yoksa hiçbir yazma yapmaz ve `synced=0` döner.
        Açılışta ve rüya döngüsünde çağrılır; sayılar günlüğe yazılır.
        """
        started = time.time()
        store = self.graph_store()
        if store is None:
            return {"synced": 0, "drift_before": -1, "drift_after": -1, "duration_s": 0.0,
                    "error": "graph_store_unavailable"}
        try:
            before = self.store_drift()
            if before == 0:
                # Idempotent kısayol: sapma yoksa hiçbir yazma yapılmaz.
                # (Tam uzlaştırma 1400+ düğümde O(n^2) benzerlik hesabı demektir;
                # her rüya turunda bedava koşmamalı.)
                return {"synced": 0, "entity_nodes": 0, "edges": 0, "drift_before": 0,
                        "drift_after": 0, "duration_s": round(time.time() - started, 3)}
            result = store.sync_from_cognitive(similarity_edges=similarity_edges)
            after = self.store_drift()
            payload = {
                "synced": result.get("synced_nodes", 0),
                "entity_nodes": result.get("entity_nodes", 0),
                "edges": result.get("edges", 0),
                "drift_before": before,
                "drift_after": after,
                "duration_s": round(time.time() - started, 3),
            }
            if before or after:
                logger.info(
                    "Depo uzlaştırma: sapma %s -> %s, %s düğüm senkronlandı (%.3f sn)",
                    before, after, payload["synced"], payload["duration_s"],
                )
            return payload
        except Exception as exc:
            self._record_error("reconcile_stores", "Depo uzlaştırma başarısız", exc)
            return {"synced": 0, "drift_before": -1, "drift_after": -1,
                    "duration_s": round(time.time() - started, 3), "error": str(exc)}

    def store_drift(self) -> int:
        """`cognitive_nodes`'ta olup graf `nodes`'ta olmayan satır sayısı."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM cognitive_nodes c "
                    "LEFT JOIN nodes n ON c.id = n.id WHERE n.id IS NULL"
                ).fetchone()
            return int(row[0]) if row else 0
        except sqlite3.Error:
            # `nodes` tablosu henüz yoksa sapma tanımsızdır, sıfır sayılır.
            return 0

    def delete_memory(self, node_id: str) -> Dict[str, int]:
        """
        Bir anıyı HER İKİ depodan siler (tek silme giriş noktası).

        Önceden silme yalnızca `cognitive_nodes`'tan yapılıyordu
        (`ui/dialogs/memory_inspector_dialog.py:494-499`); graf düğümü ve
        kenarları yerinde kalıp geri çağırmaya sızmaya devam ediyordu.
        """
        removed = {"cognitive_nodes": 0, "nodes": 0, "edges": 0}
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM cognitive_nodes WHERE id = ?", (node_id,))
                removed["cognitive_nodes"] = cur.rowcount or 0
                for table, where in (("nodes", "id = ?"), ("edges", "src = ? OR dst = ?")):
                    try:
                        params = (node_id,) if table == "nodes" else (node_id, node_id)
                        cur.execute(f"DELETE FROM {table} WHERE {where}", params)
                        removed[table] = cur.rowcount or 0
                    except sqlite3.Error:
                        # Graf tabloları hiç kurulmamış olabilir (eski profil).
                        removed[table] = 0
                conn.commit()
        except sqlite3.Error as exc:
            self._record_error("delete_memory", f"Anı silinemedi: {node_id}", exc)
            return removed
        self._invalidate_recall_index()
        return removed

    def get_node(self, node_id: str) -> Optional[CognitiveMemoryNode]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, category, content, importance, created_at, last_accessed,"
                " access_count, metadata_json, embedding_json" + V2_COLUMNS +
                " FROM cognitive_nodes WHERE id = ?", (node_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return _row_to_memory_node(row)

    def get_all_nodes(self) -> List[CognitiveMemoryNode]:
        """Return all cognitive memory nodes from local SQLite persistence."""
        nodes = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, category, content, importance, created_at, last_accessed,"
                " access_count, metadata_json, embedding_json" + V2_COLUMNS +
                " FROM cognitive_nodes")
            for row in cursor.fetchall():
                nodes.append(_row_to_memory_node(row))
        return nodes

    def record_memory(
        self,
        category: str,
        content: str,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
        provenance: str = "",
    ) -> Tuple[CognitiveMemoryNode, bool]:
        """
        Yazma yolunun TEK giriş noktası (Faz 11.2).

        Sıra:
          1. Birebir kimlik (içerik özeti) eşleşmesi — eski davranış, en ucuz yol.
          2. `MemoryGate.admit()` — kategori, fikstür, kaynak, yoğunluk, üç bant.
             `ENTROPY_MEMORY_GATE=0` ile atlanır (geri alma bayrağı).

        Döner: `(node, is_novel)`. RED kararında düğüm yazılmaz ve `node` kapının
        ürettiği geçici (kalıcı olmayan) düğümdür — çağıranların hepsi dönüşü
        yalnızca günlük/`bus` için kullanıyor, bu yüzden imza değişmiyor.
        """
        node_id = self._generate_node_id(category, content)
        existing = self.get_node(node_id)
        now = time.time()

        if existing is None and gate_enabled():
            decision = self.gate.admit(
                category, content, importance=importance,
                metadata=metadata, provenance=provenance,
            )
            self.last_gate_decision = decision
            if decision.action == GATE_REJECT:
                self._record_error("memory_gate", f"Yazma reddedildi: {decision.reason}")
                rejected = CognitiveMemoryNode(
                    id=node_id, category=decision.category, content=content,
                    importance=importance, created_at=now, last_accessed=now,
                    access_count=0, metadata=dict(metadata or {}),
                    provenance=decision.provenance, confidence=decision.confidence,
                    novelty=0.0, archived=1,
                )
                return rejected, False
            if decision.action == GATE_NOOP and decision.nearest_id:
                # Kopya: yeni düğüm AÇILMAZ. Mevcut düğümün erişim sayacı ve
                # son görülme zamanı güncellenir (SAGE NOOP bandı).
                near = self.get_node(decision.nearest_id)
                if near is not None:
                    near.last_accessed = now
                    near.importance = max(near.importance, importance)
                    if metadata:
                        near.metadata.update(metadata)
                    self._save_node(near)
                    return near, False
            # ADD / GRAY / SUPERSEDE: düğüm yazılır, kararın izi düğüme işlenir.
            if decision.embedding_status == "fallback":
                # Gömme motoru patladıysa düğüm KAYBEDİLMEZ: hash yedeğiyle
                # yazılır, 'pending' işaretlenir; hata görünür kalır (Faz 10-A
                # sözleşmesi, kapı eklendikten sonra da geçerli).
                self._record_error(
                    "record_memory", f"Gömme üretilemedi, düğüm 'pending' kaydedildi: {node_id}"
                )
            # Kapının zenginleştirdiği metadata kullanılır: eşlenen kategorinin
            # ham değeri (`legacy_category`) orada işaretlenir.
            metadata = dict(decision.metadata or metadata or {})
            metadata["gate_action"] = decision.action
            if decision.nearest_id:
                metadata["gate_nearest"] = decision.nearest_id
            node_id = self._generate_node_id(decision.category, content)
            new_node = CognitiveMemoryNode(
                id=node_id,
                category=decision.category,
                content=content,
                importance=max(0.0, min(1.0, importance)),
                created_at=now,
                last_accessed=now,
                access_count=1,
                metadata=metadata,
                embedding=decision.embedding,
                provenance=decision.provenance,
                confidence=decision.confidence,
                valid_from=now,
                novelty=decision.novelty,
                is_identity=1 if decision.is_identity else 0,
            )
            self._save_node(new_node, embedding_status=decision.embedding_status)
            if decision.action == GATE_GRAY:
                self.gate.enqueue_gray(decision, node_id=node_id)
            elif decision.action == GATE_SUPERSEDE and decision.nearest_id:
                self._supersede_node(decision.nearest_id, node_id, now)
            return new_node, True

        if existing:
            # Not novel: update existing node
            existing.last_accessed = now
            existing.access_count += 1
            existing.importance = max(existing.importance, importance)
            if metadata:
                existing.metadata.update(metadata)
            self._save_node(existing)
            return existing, False

        # Novel memory: insert new node with dense embedding.
        # Gömme başarısız olsa bile düğüm KAYBEDİLMEZ: hash yedeğiyle yazılır,
        # 'pending' işaretlenir, reembed_stale() sonradan gerçek vektörü koyar.
        embedding, embed_status = LocalEmbeddingEngine.get_instance().embed_text_status(content)
        if embed_status == "fallback":
            self._record_error(
                "record_memory", f"Gömme üretilemedi, düğüm 'pending' kaydedildi: {node_id}"
            )
        new_node = CognitiveMemoryNode(
            id=node_id,
            category=category,
            content=content,
            importance=max(0.0, min(1.0, importance)),
            created_at=now,
            last_accessed=now,
            access_count=1,
            metadata=metadata or {},
            embedding=embedding
        )
        self._save_node(new_node, embedding_status=embed_status)
        return new_node, True

    # -- yazma kapısı (Faz 11.2) ------------------------------------------

    @property
    def gate(self) -> MemoryGate:
        if self._gate is None:
            self._gate = MemoryGate(self)
        return self._gate

    def nearest_neighbor(
        self, content: str
    ) -> Tuple[Optional[str], float, Optional[List[float]], str]:
        """
        Korpustaki en yakın komşu: `(node_id, kosinüs, gömme, gömme_durumu)`.

        Kapının yoğunluk adımı budur. Gömme geri döndürülür ki `_save_node`
        aynı metni ikinci kez gömmesin (düğüm başına ~90 ms).
        Ham kosinüs kullanılır; `hybrid_recall`daki 0,50-1,00 → 0-1 germesi
        BURADA UYGULANMAZ: bant eşikleri (0,80 / 0,95) ham kosinüs üzerinden
        kalibre edildi (denetim §3.2 tablosu da ham kosinüstür).
        """
        text = (content or "").strip()
        if not text:
            return None, 0.0, None, ""
        engine = LocalEmbeddingEngine.get_instance()
        embedding, status = engine.embed_text_status(text)
        if not embedding:
            return None, 0.0, None, status

        if _np is not None:
            try:
                idx = self._get_recall_index()
                if idx.size == 0:
                    return None, 0.0, embedding, status
                arr = _np.asarray(embedding, dtype=_np.float64)
                norm = math.sqrt(float(arr @ arr))
                if norm <= 0.0:
                    return None, 0.0, embedding, status
                sims = idx.matrix @ (arr / norm)
                best = int(_np.argmax(sims))
                return idx.ids[best], float(max(0.0, min(1.0, sims[best]))), embedding, status
            except Exception as exc:  # pragma: no cover - savunma
                self._record_error("nearest_neighbor", "İndeksli komşu araması düştü", exc)

        best_id, best_sim = None, 0.0
        for node in self.get_all_nodes():
            if not node.embedding:
                continue
            sim = cosine_similarity(embedding, node.embedding)
            if sim > best_sim:
                best_id, best_sim = node.id, sim
        return best_id, best_sim, embedding, status

    def _supersede_node(self, old_id: str, new_id: str, when: float) -> None:
        """
        Çelişen eski düğümü **silmez**, geçersizleştirir (Zep/Graphiti deseni).

        `valid_to` kapatılır, `archived=1` ile geri çağırma kapsamından çıkar;
        gövde ve kaynak yerinde kalır, denetlenebilirlik korunur.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE cognitive_nodes SET valid_to = ?, archived = 1 WHERE id = ?",
                    (when, old_id),
                )
                conn.commit()
            self._invalidate_recall_index()
        except sqlite3.Error as exc:
            self._record_error("_supersede_node", f"{old_id} geçersizleştirilemedi", exc)

    def archived_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM cognitive_nodes WHERE COALESCE(archived, 0) = 1"
            ).fetchone()
        return int(row[0] if row else 0)

    def hybrid_recall(
        self,
        query: str,
        top_k: int = 5,
        min_threshold: float = 0.15,
        categories: Optional[Tuple[str, ...]] = None,
        include_episodic: bool = False,
        expand_graph: bool = False,
    ) -> List[Tuple[CognitiveMemoryNode, float]]:
        """
        T2.2 & T2.3: Recollection Engine with Multi-Criteria Hybrid Scoring & Noise Pruning.
        Score = 0.40 * VectorSim + 0.20 * BM25 + 0.25 * Ebbinghaus + 0.15 * Recency
        Filters out noise where final_score < min_threshold.

        numpy varsa bellek içi indeks üzerinden vektörleştirilmiş yol, yoksa
        eski satır satır tarama kullanılır; iki yol da aynı sıralamayı üretir.

        Faz 11.10 — kapsam süzgeci ve graf genişletmesi:
          * `categories` verilmezse varsayılan kapsam **L2 + L3**'tür
            (`semantic`, `procedural`). L0 çalışma belleği hiç gelmez; L1
            epizodik yalnızca `include_episodic=True` ile gelir. Denetimdeki
            tek kaçırma (10 sorgudan #9), 322 üyeli epizodik fikstür kümesinin
            top-5'i işgal etmesiydi.
          * `expand_graph=True` ise ilk sonuçlar tohum alınıp
            `graph_store` PPR'si ile 1-2 atlama komşu eklenir (HippoRAG 2).
        """
        scope = tuple(categories) if categories else tuple(DEFAULT_RECALL_CATEGORIES)
        if include_episodic and EPISODIC not in scope:
            scope = scope + (EPISODIC,)

        results: List[Tuple[CognitiveMemoryNode, float]] = []
        if _np is not None:
            try:
                results = self._hybrid_recall_indexed(query, top_k, min_threshold, scope)
            except Exception as exc:
                # İndeks kurulamazsa geri çağırma tamamen kaybolmasın; ama artık
                # sessiz değil: kullanıcı yavaşlığın nedenini görebilmeli.
                self._invalidate_recall_index()
                self._record_error(
                    "hybrid_recall", "İndeksli geri çağırma düştü, skaler yola geçildi", exc
                )
                results = self._hybrid_recall_scalar(query, top_k, min_threshold, scope)
        else:
            results = self._hybrid_recall_scalar(query, top_k, min_threshold, scope)

        if expand_graph and results:
            results = self._expand_with_ppr(results, top_k, scope)
        return results

    def _expand_with_ppr(
        self,
        seeds: List[Tuple["CognitiveMemoryNode", float]],
        top_k: int,
        scope: Tuple[str, ...],
    ) -> List[Tuple["CognitiveMemoryNode", float]]:
        """
        İlk sonuçları tohum alıp graf komşularını ekler (HippoRAG 2 deseni).

        Kod zaten vardı (`graph_store._personalized_pagerank`) ama okuma yoluna
        bağlı değildi. Komşular listenin SONUNA eklenir ve skorları tohumun
        skorunun altında kalacak biçimde ölçeklenir: sıralamanın ilk k'sı
        (8/10 Hit@1 veren kısım) korunur, genişletme yalnızca kuyruğu doldurur.
        """
        try:
            store = self.graph_store()
            if store is None:
                return seeds
            seed_scores = {node.id: score for node, score in seeds[:3]}
            if not seed_scores:
                return seeds
            ranked = store._personalized_pagerank(seed_scores, hops=2)
        except Exception as exc:
            self._record_error("_expand_with_ppr", "PPR genişletmesi başarısız", exc)
            return seeds

        have = {node.id for node, _ in seeds}
        floor = min(score for _, score in seeds) if seeds else 0.0
        extras: List[Tuple["CognitiveMemoryNode", float]] = []
        for node_id, weight in sorted(ranked.items(), key=lambda kv: -kv[1]):
            if node_id in have or len(seeds) + len(extras) >= top_k:
                break
            node = self.get_node(node_id)
            if node is None or node.category not in scope or node.archived:
                continue
            extras.append((node, min(floor, float(weight)) * 0.99))
        return seeds + extras

    # -- geri çağırma: bellek içi indeks ---------------------------------

    def _invalidate_recall_index(self) -> None:
        """Yazma sonrası önbelleği düşürür; süreç içi değişiklikler anında görünür."""
        with self._recall_lock:
            self._recall_index = None
            self._recall_stat_sig = None

    def _recall_signature(self) -> tuple:
        """
        Veritabanının ucuz parmak izi: satır sayısı, en son erişim, erişim toplamı
        ve en yeni kayıt zamanı. Düğüm eklendiğinde, güncellendiğinde (upsert
        last_accessed ve access_count'u değiştirir) ya da silindiğinde değişir.
        İçerik değişimi zaten yeni bir kimlik üretir (kimlik = içerik özeti).
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(MAX(last_accessed), 0.0), "
                "COALESCE(SUM(access_count), 0), COALESCE(MAX(created_at), 0.0) "
                "FROM cognitive_nodes"
            ).fetchone()
        return tuple(row or (0, 0.0, 0, 0.0))

    def _db_stat_signature(self) -> Optional[tuple]:
        """Veritabanı dosyasının boyut+mtime imzası; toplam sorgusundan ucuz kısayol."""
        try:
            st = self.db_path.stat()
        except OSError:
            return None
        return (st.st_size, st.st_mtime_ns)

    def _get_recall_index(self) -> _RecallIndex:
        """Geçerli indeksi döndürür; imza değiştiyse yeniden kurar."""
        engine = LocalEmbeddingEngine.get_instance()
        active_model = engine.model_name or "hash-fallback"

        # Hızlı yol: dosya hiç değişmediyse toplam sorgusu bile çalıştırılmaz.
        # Süreç içi yazmalar zaten _invalidate_recall_index() ile önbelleği düşürür.
        stat_sig = self._db_stat_signature()
        with self._recall_lock:
            idx = self._recall_index
            if (
                idx is not None
                and idx.model == active_model
                and stat_sig is not None
                and stat_sig == self._recall_stat_sig
            ):
                return idx

        signature = self._recall_signature()
        with self._recall_lock:
            idx = self._recall_index
            if idx is not None and idx.signature == signature and idx.model == active_model:
                self._recall_stat_sig = stat_sig
                return idx
            idx = self._build_recall_index(engine, active_model, signature)
            self._recall_index = idx
            # İndeks kurulurken eksik gömmeler geri yazılmış olabilir; imza
            # kurulumdan SONRA alınır ki hemen bayatlamış sayılmasın.
            self._recall_stat_sig = self._db_stat_signature()
            return idx

    def _build_recall_index(self, engine, active_model: str, signature: tuple) -> _RecallIndex:
        idx = _RecallIndex(signature, active_model)
        with sqlite3.connect(self.db_path) as conn:
            # Arşivlenmiş düğümler indekse girmez: ölçülü unutma silme değil,
            # geri çağırma kapsamından çıkarmadır (rate-distortion, §4.4 adım 5).
            rows = conn.execute(
                f"SELECT {_RECALL_COLUMNS} FROM cognitive_nodes "
                "WHERE COALESCE(archived, 0) = 0"
            ).fetchall()

        backfill: List[tuple] = []
        postings: Dict[str, List[tuple]] = {}
        doc_lens: List[float] = []
        vectors: List[Optional[List[float]]] = []

        for i, row in enumerate(rows):
            idx.ids.append(row[0])
            idx.categories.append(row[1])
            content = row[2] or ""
            idx.contents.append(row[2])
            idx.importances.append(row[3])
            idx.created_ats.append(row[4])
            idx.last_accesseds.append(row[5])
            idx.access_counts.append(row[6])
            idx.metadata_jsons.append(row[7])

            embedding = json.loads(row[8]) if row[8] else None
            row_model = row[9]
            # Başka bir modelin vektörü farklı bir uzaydadır; kosinüsü sessizce
            # yanlış çıkar. Eksik ya da modeli uyuşmayan gömmeler burada bir kez
            # üretilir ve veritabanına geri yazılır (eski davranışın aynısı).
            if not embedding or row_model != active_model:
                embedding = engine.embed_text(content)
                backfill.append((json.dumps(embedding), active_model, row[0]))
            vectors.append(embedding)

            tokens = re_tokenize(content)
            doc_lens.append(float(len(tokens)))
            for tok, cnt in Counter(tokens).items():
                postings.setdefault(tok, []).append((i, cnt))

        n = len(rows)
        idx.size = n
        idx.embeddings = vectors

        matrix = _np.zeros((n, EMBEDDING_DIM), dtype=_np.float64)
        for i, vec in enumerate(vectors):
            if not vec or len(vec) != EMBEDDING_DIM:
                continue  # boyutu tutmayan vektör: eski kodda benzerlik 0 dönerdi
            arr = _np.asarray(vec, dtype=_np.float64)
            norm = math.sqrt(float(arr @ arr))
            if norm > 0.0:
                matrix[i] = arr / norm
        idx.matrix = matrix

        idx.imp_arr = _np.asarray(idx.importances, dtype=_np.float64) if n else _np.zeros(0)
        idx.acc_arr = _np.asarray(idx.access_counts, dtype=_np.float64) if n else _np.zeros(0)
        idx.last_arr = _np.asarray(idx.last_accesseds, dtype=_np.float64) if n else _np.zeros(0)
        idx.doc_lens = _np.asarray(doc_lens, dtype=_np.float64) if n else _np.zeros(0)
        idx.postings = {
            tok: (_np.asarray([p[0] for p in plist], dtype=_np.intp),
                  _np.asarray([p[1] for p in plist], dtype=_np.float64))
            for tok, plist in postings.items()
        }

        if backfill:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.executemany(
                        "UPDATE cognitive_nodes SET embedding_json = ?, embedding_model = ? WHERE id = ?",
                        backfill,
                    )
                    conn.commit()
            except Exception as exc:
                self._record_error(
                    "_build_recall_index", f"{len(backfill)} eksik gomme geri yazilamadi", exc
                )
        return idx

    def _hybrid_recall_indexed(
        self, query: str, top_k: int, min_threshold: float,
        scope: Optional[Tuple[str, ...]] = None,
    ) -> List[Tuple[CognitiveMemoryNode, float]]:
        idx = self._get_recall_index()
        if idx.size == 0:
            return []

        now = time.time()
        engine = LocalEmbeddingEngine.get_instance()
        query_vector = engine.embed_text(query)
        query_tokens = re_tokenize(query)

        # 1. Yoğun vektör kosinüs benzerliği (ağırlık 0.40)
        qarr = _np.asarray(query_vector or [], dtype=_np.float64)
        qnorm = math.sqrt(float(qarr @ qarr)) if qarr.size == EMBEDDING_DIM else 0.0
        if qnorm > 0.0:
            raw_sim = _np.clip(idx.matrix @ (qarr / qnorm), 0.0, 1.0)
        else:
            raw_sim = _np.zeros(idx.size, dtype=_np.float64)
        vec_sim = _np.clip((raw_sim - 0.50) / 0.50, 0.0, 1.0)

        # 2. Seyrek sözcüksel BM25 (ağırlık 0.20) — ters indeks üzerinden
        bm25 = _np.zeros(idx.size, dtype=_np.float64)
        if query_tokens:
            for tok in query_tokens:
                posting = idx.postings.get(tok)
                if posting is None:
                    continue
                positions, counts = posting
                lengths = idx.doc_lens[positions]
                denom = counts + BM25_K1 * (
                    1 - BM25_B + BM25_B * (lengths / max(1.0, BM25_AVG_DOC_LEN))
                )
                bm25[positions] += (counts * (BM25_K1 + 1)) / denom
            bm25 = _np.minimum(1.0, bm25 / max(1.0, len(query_tokens) * 1.5))

        # 3. Ebbinghaus unutma eğrisi (ağırlık 0.25)
        days = _np.maximum(0.0, (now - idx.last_arr) / 86400.0)
        stability = 1.0 + _np.log(idx.acc_arr + 1.0)
        ebbinghaus = _np.clip(idx.imp_arr * _np.exp(-(0.05 * days) / stability), 0.0, 1.0)

        # 4. Tazelik üstel sönümü (ağırlık 0.15)
        recency = _np.exp(-0.05 * days)

        final = (0.40 * vec_sim) + (0.20 * bm25) + (0.25 * ebbinghaus) + (0.15 * recency)

        # T2.3: hem sözcüksel hem anlamsal alaka düşükse tazelik sızıntısı bastırılır
        suppress = (bm25 == 0.0) & (vec_sim < 0.35)
        if suppress.any():
            final = _np.where(suppress, final * (vec_sim / 0.35), final)

        # Faz 11.10: kapsam süzgeci. Kapsam dışı katmanlar skorlanır ama
        # sıralamaya girmez; böylece iki geri çağırma yolu aynı sayıyı üretir.
        if scope:
            allowed = _np.asarray(
                [cat in scope for cat in idx.categories], dtype=bool
            )
            final = _np.where(allowed, final, -1.0)

        keep = _np.flatnonzero(final >= min_threshold)
        if keep.size == 0:
            return []
        # Kararlı sıralama: eşit skorlarda satır sırası korunur (eski kod da
        # kararlı list.sort kullanıyordu).
        order = keep[_np.argsort(-final[keep], kind="stable")][:max(0, top_k)]
        return [(idx.node_at(int(i)), float(final[i])) for i in order]

    # -- geri çağırma: eski satır satır tarama (numpy yoksa) ---------------

    def _hybrid_recall_scalar(
        self, query: str, top_k: int, min_threshold: float,
        scope: Optional[Tuple[str, ...]] = None,
    ) -> List[Tuple[CognitiveMemoryNode, float]]:
        now = time.time()
        engine = LocalEmbeddingEngine.get_instance()
        active_model = engine.model_name or "hash-fallback"
        query_vector = engine.embed_text(query)
        query_tokens = re_tokenize(query)
        results = []

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, category, content, importance, created_at, last_accessed,"
                " access_count, metadata_json, embedding_json, embedding_model"
                " FROM cognitive_nodes WHERE COALESCE(archived, 0) = 0"
            )
            rows = cursor.fetchall()

        nodes_to_update = []

        for row in rows:
            # Faz 11.10 kapsam suzgeci: indeksli yolla ayni sonuc kumesi.
            if scope and row[1] not in scope:
                continue
            embedding = json.loads(row[8]) if (len(row) > 8 and row[8]) else None
            row_model = row[9] if len(row) > 9 else None
            node = CognitiveMemoryNode(
                id=row[0],
                category=row[1],
                content=row[2],
                importance=row[3],
                created_at=row[4],
                last_accessed=row[5],
                access_count=row[6],
                metadata=json.loads(row[7] or "{}"),
                embedding=embedding
            )

            # 1. Dense Vector Cosine Similarity (Weight: 0.40)
            # Başka bir modelle üretilmiş vektör farklı bir uzaydadır; onunla
            # kosinüs benzerliği hesaplamak sessizce yanlış sonuç verir. Bu yüzden
            # eksik VEYA modeli uyuşmayan gömmeler burada yeniden üretilir.
            if not node.embedding or row_model != active_model:
                node.embedding = engine.embed_text(node.content)
                nodes_to_update.append((json.dumps(node.embedding), active_model, node.id))
            raw_sim = cosine_similarity(query_vector, node.embedding)
            # Rescale cosine similarity to [0, 1] removing typical dense embedding anisotropy baseline (~0.50)
            vec_sim = max(0.0, min(1.0, (raw_sim - 0.50) / 0.50))

            # 2. Sparse Lexical BM25 Score (Weight: 0.20)
            node_tokens = re_tokenize(node.content)
            bm25_sim = compute_bm25_score(query_tokens, node_tokens)

            # 3. Ebbinghaus Forgetting Curve Retention (Weight: 0.25)
            ebbinghaus_strength = node.calculate_ebbinghaus_strength(current_time=now)

            # 4. Recency Exponential Decay (Weight: 0.15)
            days_ago = max(0.0, (now - node.last_accessed) / 86400.0)
            recency = math.exp(-0.05 * days_ago)

            # Multi-criteria hybrid score formula (T2.2)
            final_score = (
                (0.40 * vec_sim) +
                (0.20 * bm25_sim) +
                (0.25 * ebbinghaus_strength) +
                (0.15 * recency)
            )

            # T2.3: Noise pruning: If both lexical and semantic relevance are low, suppress recency leakage
            if bm25_sim == 0.0 and vec_sim < 0.35:
                final_score *= (vec_sim / 0.35)

            # T2.3: Noise pruning threshold
            if final_score >= min_threshold:
                results.append((node, final_score))

        # Lazy backfill embeddings into SQLite if any were missing
        if nodes_to_update:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.executemany(
                        "UPDATE cognitive_nodes SET embedding_json = ?, embedding_model = ? WHERE id = ?",
                        nodes_to_update,
                    )
                    conn.commit()
            except Exception as exc:
                self._record_error(
                    "_hybrid_recall_scalar", f"{len(nodes_to_update)} gomme geri yazilamadi", exc
                )

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def store_node(
        self,
        category: str,
        content: str,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
        provenance: str = "",
    ) -> Tuple[CognitiveMemoryNode, bool]:
        """
        Yedi uretim cagri noktasinin kullandigi ad. `record_memory` ile ayni
        kapidan gecer; ayri bir yazma yolu DEGILDIR.
        """
        return self.record_memory(category, content, importance, metadata, provenance)

    def recall(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Convenience alias returning list of dicts for hybrid_recall."""
        results = self.hybrid_recall(query, top_k=limit)
        return [
            {
                "id": node.id,
                "category": node.category,
                "content": node.content,
                "importance": node.importance,
                "score": score
            }
            for node, score in results
        ]

    def dream_and_consolidate(self) -> "DreamResult":
        """
        Layer 6: Dreaming / Clustering Consolidation (T3.1 & T3.2).
        Gathers episodic memories from the past 24-48 hours, aggregates themes,
        saves consolidated semantic facts, and appends architectural decisions to Obsidian MEMORY.md.
        """
        now = time.time()
        two_days_ago = now - (2 * 86400.0)
        # DreamResult bir list'tir: eski cagiranlar (main.py, tasks_widget.py)
        # degismeden calisir, ama artik `.errors` ve `.report` ile kismi
        # basarisizlik gorunur. Onceden uc adim sessizce atlanip islev yine
        # "basarili" donuyordu (teshis notu SS A.4).
        synthesized_rules = DreamResult()
        errors = synthesized_rules.errors
        report = synthesized_rules.report

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, metadata_json, importance FROM cognitive_nodes WHERE category = 'episodic' AND created_at >= ?",
                (two_days_ago,)
            )
            rows = cursor.fetchall()

        # Eski sürümün bıraktığı içeriksiz "N etkileşimden damıtıldı" etiketleri
        # temizlenir: 0.85 önemle kaydedildikleri için recall'da gerçek bilgiyi
        # bastırıyorlardı.
        self.purge_placeholder_consolidations()

        if len(rows) >= 2:
            date_str = time.strftime('%Y-%m-%d')
            # Gerçek içerik: son bölümsel anıların gövdeleri, tekrarlar atılarak.
            # Önceki sürüm yalnızca bir etiket ("N etkileşimden damıtıldı") yazıyordu;
            # etiket bilgi taşımaz, recall'a girince yer kaplar ve hiçbir soruyu
            # cevaplamaz. Asıl sentez (AGY ile) zamanlayıcı görevinde yapılır;
            # bu düğüm o sentez gelmediğinde bile işe yarar bir özettir.
            seen, items = set(), []
            for content, _meta, _imp in sorted(rows, key=lambda r: r[2] or 0.0, reverse=True):
                head = " ".join((content or "").split())[:220]
                key = head[:60].lower()
                if head and key not in seen:
                    seen.add(key)
                    items.append(head)
                if len(items) >= 6:
                    break
            summary = f"Günlük bilişsel özet ({date_str}), {len(rows)} etkileşim:\n" + "\n".join(f"- {i}" for i in items)

            self.record_memory(
                category="semantic",
                content=summary,
                importance=0.6,
                metadata={"source": "dream_consolidation", "items_clustered": len(rows), "date": date_str},
                # Konsolidasyon düğümünün kaynağı YAPISAL alanda durur; gövdeye
                # gömülü kalırsa kapı onu kaynaksız sayıp reddeder ve "duyum"
                # kesin olguya dönüşür (Manufactured Confidence, arXiv:2606.29279).
                provenance=f"dream_consolidation:{date_str}:{len(rows)} epizodik düğüm",
            )
            synthesized_rules.append(summary)

            # T3.2: Export to Obsidian MEMORY.md if available
            try:
                from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
                ovm = ObsidianVaultManager()
                ovm.append_to_global_memory("Otonom Bilişsel Konsolidasyon (Rüya)", summary)
            except Exception as exc:
                errors.append(self._record_error(
                    "dream:obsidian_export", "Konsolidasyon ozeti kasaya yazilamadi", exc))

        # Also run pruning during dream cycle
        try:
            self.prune_decayed_memories()
        except Exception as exc:
            errors.append(self._record_error(
                "dream:prune", "Sonmus ani budama basarisiz", exc))

        # Faz 10-A: gecikmis/bayat gommeler burada tamamlanir. reembed_stale
        # uretimde HIC cagrilmiyordu; model degisirse eski dugumler sonsuza dek
        # eski vektor uzayinda kaliyordu.
        try:
            report["reembed"] = self.reembed_stale(batch_limit=REEMBED_DREAM_BATCH)
        except Exception as exc:
            errors.append(self._record_error(
                "dream:reembed", "Bayat gommeler yenilenemedi", exc))

        # Faz 10-A: iki depo arasindaki sapma ruya dongusunde de kapatilir
        # (yazma yolu artik senkron yaziyor; bu, dis araclarla olusan sapma icin).
        try:
            report["reconcile"] = self.reconcile_stores()
        except Exception as exc:
            errors.append(self._record_error(
                "dream:reconcile", "Depo uzlastirma basarisiz", exc))

        # Faz 5: graf katmanı konsolidasyonu (LLM'siz, kota harcamaz). Graf
        # katmanı yoksa veya şema kurulamazsa rüya döngüsü bozulmamalıdır.
        try:
            from entropy.memory.graph_store import GraphStore
            GraphStore(memory=self).consolidate()
        except Exception as exc:
            errors.append(self._record_error(
                "dream:graph_consolidate", "Graf konsolidasyonu atlandi", exc))

        # Faz 7: Desk ofis belleğinin Entropy grafına akışı da rüya döngüsünde
        # tetiklenir (modelsiz, kota harcamaz). Ayrı bir kullanıcı komutu yok;
        # başarısız olursa rüya döngüsü etkilenmez.
        try:
            from entropy.memory.graph_store import GraphStore
            from entropy.memory.office_graph import schedule_office_ingest

            # Depo bu bellek örneğine bağlanır: testlerdeki geçici veritabanı
            # yerine üretim grafına yazılmasın.
            schedule_office_ingest(store=GraphStore(memory=self), background=False)
        except Exception as exc:
            errors.append(self._record_error(
                "dream:office_ingest", "Ofis bellegi grafina akis atlandi", exc))

        if errors:
            logger.warning("Ruya dongusu %s adimda kismi basarisizlikla bitti", len(errors))
        return synthesized_rules

    _PLACEHOLDER_RE = re.compile(r"^Konsolide Bilişsel Özet \(\d{4}-\d{2}-\d{2}\): \d+ bölümsel etkileşimden damıtıldı\.?$")

    def purge_placeholder_consolidations(self) -> int:
        """Eski konsolidasyonun ürettiği, içerik taşımayan etiket düğümlerini siler."""
        removed = 0
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, content FROM cognitive_nodes WHERE metadata_json LIKE '%dream_consolidation%'")
                junk = [nid for nid, content in cursor.fetchall() if self._PLACEHOLDER_RE.match((content or "").strip())]
                if junk:
                    cursor.executemany("DELETE FROM cognitive_nodes WHERE id = ?", [(j,) for j in junk])
                    conn.commit()
                    removed = len(junk)
        except Exception as exc:
            self._record_error(
                "purge_placeholder_consolidations", "Yer tutucu dugumler temizlenemedi", exc)
        if removed:
            self._invalidate_recall_index()
        return removed

    def build_consolidation_prompt(self, hours: float = 48.0, max_items: int = 30) -> Optional[str]:
        """
        Son bölümsel anılardan AGY ile gerçek bir sentez çıkarmak için prompt üretir.

        None dönerse sentezlenecek yeterli anı yoktur. Çıktı store_consolidation()
        ile semantic düğüm olarak kaydedilir.
        """
        since = time.time() - hours * 3600.0
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content FROM cognitive_nodes WHERE category = 'episodic' AND created_at >= ? "
                "ORDER BY importance DESC, created_at DESC LIMIT ?",
                (since, max_items),
            )
            rows = [r[0] for r in cursor.fetchall() if r[0]]
        if len(rows) < 2:
            return None
        body = "\n".join(f"- {' '.join(r.split())[:400]}" for r in rows)
        return (
            "[GÖREV: BİLİŞSEL KONSOLİDASYON]\n\n"
            f"Aşağıda son {int(hours)} saatin {len(rows)} bölümsel anısı var. Bunlardan kalıcı, "
            "yeniden kullanılabilir bilgi çıkar: hangi kararlar alındı, hangi tercihler ve kurallar "
            "ortaya çıktı, neler öğrenildi. Tek seferlik ayrıntıları ve günlük gürültüyü alma.\n"
            "En fazla 1200 karakter, madde madde, yalnızca gövde metni.\n\n"
            f"{body}\n"
        )

    def store_consolidation(self, text: str) -> Optional[CognitiveMemoryNode]:
        """AGY'den dönen sentezi semantic düğüm olarak kaydeder."""
        text = (text or "").strip()
        if len(text) < 40:
            return None
        node, _ = self.record_memory(
            category="semantic",
            content=f"Konsolide öğrenimler ({time.strftime('%Y-%m-%d')}):\n{text[:1600]}",
            importance=0.8,
            metadata={"source": "dream_consolidation_agy", "date": time.strftime('%Y-%m-%d')},
            provenance=f"dream_consolidation_agy:{time.strftime('%Y-%m-%d')}",
        )
        return node

    def prune_decayed_memories(self, min_strength: float = 0.10, days_dormant: float = 30.0) -> int:
        """
        Layer 5 & T3.3: Prune decayed low-importance episodic memories.
        Prunes nodes where:
        - category is 'episodic'
        - initial importance < 0.35
        - days since last access >= days_dormant
        - calculated Ebbinghaus retention strength < min_strength
        Never prunes 'ego', 'semantic', or 'procedural' memories.
        """
        now = time.time()
        dormant_cutoff = now - (days_dormant * 86400.0)
        pruned_ids = []

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, category, content, importance, created_at, last_accessed, access_count"
                " FROM cognitive_nodes WHERE category = 'episodic'"
                " AND COALESCE(is_identity, 0) = 0"
                " AND last_accessed <= ? AND importance < 0.35",
                (dormant_cutoff,)
            )
            rows = cursor.fetchall()

            for r in rows:
                node = CognitiveMemoryNode(
                    id=r[0],
                    category=r[1],
                    content=r[2],
                    importance=r[3],
                    created_at=r[4],
                    last_accessed=r[5],
                    access_count=r[6]
                )
                if node.calculate_ebbinghaus_strength(current_time=now) < min_strength:
                    pruned_ids.append(node.id)

            if pruned_ids:
                cursor.executemany("DELETE FROM cognitive_nodes WHERE id = ?", [(pid,) for pid in pruned_ids])
                conn.commit()

        if pruned_ids:
            self._invalidate_recall_index()
        return len(pruned_ids)

def re_tokenize(text: str) -> List[str]:
    """Simple alphanumeric tokenizer."""
    return [w.lower() for w in re.findall(r"\w+", text)]
