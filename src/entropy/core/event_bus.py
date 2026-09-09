"""Central Qt Typed Event Bus for Entropy AI."""

from PySide6.QtCore import QObject, QThread, Signal, Slot


class EntropyEventBus(QObject):
    """Global singleton event bus for cross-component signaling."""

    # UI Mode Transitions
    mode_requested = Signal(str)  # "zen", "floating", "chat"
    mode_changed = Signal(str)

    # Core Visual Activity
    core_pulse_triggered = Signal(float)  # intensity (0.0 - 1.0)
    core_state_changed = Signal(str)     # "idle", "thinking", "executing", "error"

    # AGY CLI Streaming & Lifecycle
    model_detected = Signal(str)         # dynamic model string e.g. "gemini-2.5-flash"
    token_chunk_received = Signal(str)   # streaming text chunk
    terminal_output_received = Signal(str) # stdout/stderr line
    token_usage_updated = Signal(int)    # total tokens consumed
    # Token kaleminin AYRIŞTIRILMIŞ hâli (Faz 9 / Ek-1). Anahtarlar:
    # session (oturum ham toplamı), turn (YALNIZCA son tur), cache_read
    # (önbellek okumasının oturum toplamı), cost_weighted (cache_read 0,1×
    # sayılan maliyet toplamı). Tek `int` sinyali "77k (+77k)" gibi yanıltıcı
    # bir rozet üretiyordu; ayrıştırma köprüde yapılır, arayüz yalnızca basar.
    token_usage_detail = Signal(dict)
    agent_turn_started = Signal(str)     # prompt
    agent_turn_completed = Signal(str)   # final response

    # Ajan akışı (Faz 10-B): piksel ajan sahnesinin tek beslemesi. Eski
    # sinyaller (token_chunk_received, terminal_output_received) OLDUĞU GİBİ
    # kalır ve yayılmaya devam eder; bu sinyal onların yerine değil, yanına
    # gelir. Fark: yük ajan/ofis/kart etiketini taşır, böylece aynı anda koşan
    # birden çok gizli terminal sahnede ayrı avatarlara düşer — eski tek tampon
    # (stream_panel) bunu ayırt edemiyordu.
    #
    # Yük (bkz. entropy.core.provider.build_agent_stream_event):
    #   task_id, card_id, office, agent, provider, model,
    #   kind:  "text" | "thinking" | "tool_call" | "tool_result" | "status"
    #          | "result" | "error"
    #   text:  balon metni (≤ 280 karakter, kırpıldıysa "…" ile biter)
    #   full_text: yalnızca kırpma olduysa; tam metin
    #   tool:  {"name", "input_summary"} veya None
    #   state: "thinking" | "working" | "idle" | "error"  (sahne animasyonu)
    #   ts:    time.time()
    agent_stream = Signal(dict)

    # Project Context
    project_changed = Signal(str)        # absolute project directory path

    # Bağlam doluluğu: köprü, sağlayıcının bağlam penceresinin ne kadarının
    # dolduğunu her turdan sonra ölçer ve eşiği (%60) ilk aşışta bir kez yayar.
    # Arayüz bunu uyarı/rozet olarak gösterir, bellek katmanı aktarım sayfası
    # yazar. Her turda yayılsaydı uzun oturumda sürekli uyarı olurdu.
    context_pressure = Signal(float)     # 0.0-1.0+ doluluk oranı

    # Sohbet geçmişi: tek kaynak diskteki dosya. Bir tur kaydedildiğinde ya da
    # sohbet arşivlenip sıfırlandığında tüm pencereler (Zen, Chat) aynı içeriği
    # gösterebilsin diye haber verilir. Alıcılar QObject slotudur; lambda değil.
    chat_history_updated = Signal()      # diske yeni tur yazıldı
    chat_history_cleared = Signal()      # sohbet arşivlendi, ekranlar temizlensin

    # Tool Execution & Permissions
    tool_approval_requested = Signal(str, str, str)  # tool_name, args_summary, tool_id
    tool_approval_responded = Signal(str, bool)     # tool_id, approved

    # Task Scheduler
    task_triggered = Signal(str, str)    # task_id, task_name
    task_completed = Signal(str, bool)   # task_id, success
    task_notification = Signal(str, str, str) # task_id, task_name, report_path_or_summary

    # Knowledge & Reports
    report_created = Signal(str)         # report_path
    node_selected = Signal(str)          # node_id
    knowledge_graph_updated = Signal()   # reload knowledge graph signal
    cognitive_memory_updated = Signal()  # memory nodes updated
    skills_updated = Signal()            # skills catalog updated
    # Bir mesaj için yetenek kararı verildi: yetenek adı ("" = yetenek yok) ve
    # kararın güven puanı (0–1). Arayüz rozeti kararın ne kadar sağlam olduğunu
    # gösterebilsin diye ayrı sinyal: karar zaten metin akışından önce belli olur.
    skill_detected = Signal(str, float)  # skill_name veya "", confidence 0.0-1.0
    mcp_servers_updated = Signal()       # mcp_config.json değişti (ekle/düzenle/kaldır/aç-kapa)
    playbook_updated = Signal(str)       # skill_name: damıtılmış yordam kaydedildi/yenilendi
    # Kasaya yeni rapor düştü ya da rapor-yetenek indeksi artımlı güncellendi.
    # Argüman etkilenen yetenek adı ("" = bilinmiyor/çok sayıda). Yetenek kartının
    # damıtma sayacı, uygulamayı yeniden başlatmadan artabilsin diye ayrı sinyal:
    # playbook_updated "yordam yazıldı" demektir, bu ise "kaynak değişti".
    reports_updated = Signal(str)        # skill_name veya ""
    distill_progress = Signal(str, int, int)  # skill_name, işlenen rapor, toplam rapor

    # Rapor Merkezi "Gelen" şeridi (Faz 4): son 24 saatteki okunmamış rapor
    # sayısı. Rozeti Zen üst çubuğu ve Chat başlığı ayrı ayrı gösterdiği için
    # sayaç şeritten doğrudan değil, bu sinyalle dağıtılır; pencerelerden biri
    # kapalıyken de açılışta doğru değeri okur.
    report_inbox_unread = Signal(int)    # okunmamış rapor sayısı

    # Ajanlar ve görev kartları: kaynak dosyalar kasada (Entropy/Agents,
    # Entropy/Tasks) ve onları Entropy, kullanıcı (Obsidian) ve harici CLI'lar
    # birlikte yazıyor. Panellerin diski yoklamak yerine haber alması için
    # değişimde bu sinyaller yayılır; argüman etkilenen ajan adı / kart kimliği
    # ("" = birden çok ya da bilinmiyor).
    agents_updated = Signal(str)         # ajan tanımı eklendi/değişti/silindi
    task_cards_updated = Signal(str)     # görev kartı eklendi/değişti/silindi

    # Ofisler (Agent Desk): ofis tanımı değişti ve ofis zincirinin aşaması.
    # Aşama ayrı bir sinyal çünkü task_cards_updated kart başına yayılıyor ve
    # sahne "bu ofis şu an planlıyor mu, koşuyor mu" bilgisini kart akışından
    # güvenilir biçimde çıkaramıyordu.
    offices_updated = Signal(str)        # ofis adı ("" = birden çok/bilinmiyor)
    office_progress = Signal(str, str, str)  # ofis, üst kart id, aşama

    # Posta kutusu (Faz 5): bir ofis/ajan/Entropy gelen kutusuna mesaj düştü ya
    # da bir mesaj okundu/onaylandı işaretlendi. Argümanlar sahip türü
    # ("office"|"agent"|"entropy") ve sahip adı. Kutunun kendisi diskte; sinyal
    # yalnızca "bak" der, içerik taşımaz — mesajı iki taraf da dosyadan okur ve
    # tek gerçek kaynak korunur.
    mailbox_updated = Signal(str, str)   # owner_kind, owner_name

    # Harness / bellek katmanının Faz 10 sinyalleri. Burada yalnızca TANIMLI;
    # yayım sahipleri ayrı: kuralları bellek katmanı (rules_updated,
    # memory_error), kontrol noktası ve kanıt kaydını ofis harness'ı yayar.
    # Tanımın burada durması zorunlu — bus tek sözleşme noktasıdır ve iki ekip
    # aynı adı iki farklı imzayla icat etmesin diye.
    rules_updated = Signal(str, int)     # (ofis adı; "" = genel), eklenen kural sayısı
    memory_error = Signal(dict)          # {"where", "message", "ts"}
    checkpoint_written = Signal(dict)    # {"office", "card_id", "path"}
    proof_recorded = Signal(dict)        # {"office", "card_id", "ok", "command"}

    # Sağlayıcı kimlik/durum katmanı (Faz 5): giriş var mı, hangi hesap, kota
    # ipucu, son hata. Sözlük olarak taşınır çünkü alanlar sağlayıcıya göre
    # değişiyor ve her yeni alan için sinyal imzası değiştirilemez.
    provider_status_updated = Signal(str, dict)  # provider, ProviderStatus.to_dict()

    # İşçi iş parçacıklarından ana iş parçacığına iş taşır. Alıcı bir QObject slotu
    # olduğu için bağlantı kuyruklu olur; lambda alıcı olsaydı doğrudan işçide
    # koşar ve Qt nesnelerine oradan dokunulurdu.
    call_on_main = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.call_on_main.connect(self._run_on_main)

    @Slot(object)
    def _run_on_main(self, fn):
        fn()

    def invoke_on_main(self, fn) -> None:
        """fn'i ana (bus'ın) iş parçacığında çalıştırır; zaten oradaysa hemen."""
        if QThread.currentThread() is self.thread():
            fn()
        else:
            self.call_on_main.emit(fn)

# Global Event Bus Instance
bus = EntropyEventBus()
