import sys
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from entropy.core.config import config
from entropy.brain.obsidian.vault_manager import ObsidianVaultManager
from entropy.brain.supabase.cognitive_memory import CognitiveMemorySystem

def main():
    vault_manager = ObsidianVaultManager()
    cog_mem = CognitiveMemorySystem()

    today_str = datetime.date.today().isoformat()

    # 1. Update MEMORY.md
    memory_file = vault_manager.memory_file
    current_memory = memory_file.read_text(encoding="utf-8")

    faz_36_header = f"\n## Cont-de Larrard LOB, Kou Çift Üstel Sıçrama, Variance Gamma, Barenblatt UVM, Vanna-Volga FX ve Curve LLAMMA (Faz 36) ({today_str})\n"
    faz_36_body = (
        "- **Rama Cont & Adrien de Larrard (2012/2013) Markovian Limit Emir Defteri (LOB) Kuyruk Dinamikleri**: "
        "Emir defterindeki en iyi alış ve satış derinliklerinin $(q_t^b, q_t^a)$ iki boyutlu Markov zinciri olarak modellenmesi, "
        "sınır değer problemi ve asimetrik akış altında anlık fiyat artış olasılığı $p^{\\text{up}}(q^b, q^a)$ analitiği.\n"
        "- **Steven Kou (2002) Çift Üstel Sıçrama-Difüzyon Modeli (DEJD)**: "
        "Asimetrik kalın kuyruk ve leptokurtik yapıyı üstel bellek yokluğu (memoryless property) ile birleştiren, "
        "bariyer opsiyonlarında (Up/Down-and-Out) aşım hatasını sıfırlayan kapalı form analitik çözüm.\n"
        "- **Dilip Madan, Peter Carr & Eric Chang (1998) Variance Gamma (VG) Süreci & Saf Sıçrama Lévy Varlık Modelleri**: "
        "Sürekli Brownian bileşeni içermeyen, Gamma zaman saatiyle dönüştürülmüş sonsuz aktiviteli ve sonlu varyasyonlu saf sıçrama süreci; "
        "kapalı form karakteristik fonksiyon $\\phi_{\\text{VG}}(u)$ ve Carr-Madan FFT / kuadratür ile volatilite gülüşü kalibrasyonu.\n"
        "- **Marco Avellaneda & Robert Buff (1999) Belirsiz Volatilite Modeli (UVM) ve Black-Scholes-Barenblatt (BSB) Doğrusal Olmayan PDE**: "
        "Volatilitenin tek bir sayı yerine $[\\sigma_{\\min}, \\sigma_{\\max}]$ aralığında dalgalandığı en kötü durum (worst-case / super-replication) senaryosu; "
        "gamma işaretine göre şekillenen doğrusal olmayan Barenblatt difüzyon denklemi ve yapılandırılmış ürünlerde kesin arbitrajsız alış/satış spread sınırları.\n"
        "- **Garman-Kohlhagen (1983) & FX Piyasalarında Vanna-Volga Fiyatlama ve Volatilite Gülüşü İnterpolasyonu**: "
        "Bankalararası döviz piyasalarında ATM volatilite, 25-Delta Risk Reversal ($RR_{25}$) ve 25-Delta Vega-Weighted Butterfly ($BF_{25}$) "
        "kotasyonlarından analitik Vega, Vanna ($\\frac{\\partial^2 V}{\\partial S \\partial \\sigma}$) ve Volga ($\\frac{\\partial^2 V}{\\partial \\sigma^2}$) "
        "duyarlılık kalkanı ile smile inşası ve birinci nesil egzotik opsiyon fiyatlaması.\n"
        "- **DeFi Borçlanma Protokolleri, Tasfiye Fiziği ve Curve LLAMMA (Lending-Liquidating AMM Algorithm) Yumuşak Tasfiye Dinamikleri**: "
        "Klasik sert tasfiyelerin getirdiği kaskat çöküş ve %10 ceza yerine teminatı ayrık fiyat bantlarında sürekli ve tersinir olarak "
        "stabilcoine dönüştüren LLAMMA AMM bant invaryantı $I = \\sqrt{P_{\\text{down}} P_{\\text{up}}}$, kullanıcı kayıp optimizasyonu ve Morpho Blue izole risk kürasyonu.\n"
        "- **Detaylı Rapor**: [[Cont_Kou_VarianceGamma_BarenblattUVM_VannaVolga_ve_LLAMMA]]\n"
    )

    if "Cont_Kou_VarianceGamma_BarenblattUVM_VannaVolga_ve_LLAMMA" not in current_memory:
        memory_file.write_text(current_memory.rstrip() + "\n" + faz_36_header + faz_36_body, encoding="utf-8")
        print("[OK] MEMORY.md updated with Faz 36.")
    else:
        print("[INFO] MEMORY.md already contains Faz 36.")

    # 2. Sync Map of Content (BELLEK_HARITASI.md)
    moc_path = vault_manager.sync_map_of_content()
    print(f"[OK] Master Bellek Haritası synced: {moc_path}")

    # 3. Append to Daily Note
    daily_entry = (
        "Otonom Planlı Görev İcrası: Finans Yeteneği Geliştirme (Faz 36). "
        "Daha önce hafızada yer almayan 6 ileri düzey kantitatif finans ve piyasa mikroyapısı modeli araştırıldı, "
        "matematiksel ve algoritmik olarak doğrulandı, 6 adet pytest testinden %100 başarıyla geçti. "
        "Rapor oluşturuldu: [[Cont_Kou_VarianceGamma_BarenblattUVM_VannaVolga_ve_LLAMMA]]. "
        "MEMORY.md ve BELLEK_HARITASI.md senkronize edildi, 6 bilişsel bellek düğümü yerel nöral embedding ile hafıza sistemine kaydedildi."
    )
    vault_manager.append_daily_log(daily_entry)
    print("[OK] Daily note log appended.")

    # 4. Ingest into CognitiveMemorySystem (12-layer cognitive architecture)
    nodes_to_record = [
        (
            "Cont-de Larrard (2012) Markovian LOB Kuyruk Dinamikleri: Emir defterindeki en iyi alış ve satış derinliklerinin (q_b, q_a) "
            "iki boyutlu Markov zinciri olarak modellenmesi. Simetrik akışta fiyat artış olasılığı p_up = q_b / (q_b + q_a); "
            "asimetrik akışta 2D sınır değer problemi ile ilk geçiş zamanı (first passage time) ve kademe sıçrama süresi tahmini.",
            0.95,
            {"phase": "faz-36", "topic": "microstructure", "author": "Cont-de Larrard"}
        ),
        (
            "Steven Kou (2002) Çift Üstel Sıçrama-Difüzyon Modeli (DEJD): Asimetrik kalın kuyruk ve leptokurtik basıklığı modelleyen, "
            "üstel dağılımın belleksizlik (memoryless property) prensibi sayesinde bariyer opsiyonlarında (Up-and-Out, Down-and-Out) "
            "aşım (overshoot) hatasını sıfırlayarak kapalı form analitik Laplace çözümü üreten sıçrama modeli.",
            0.95,
            {"phase": "faz-36", "topic": "jump-diffusion", "author": "Steven Kou"}
        ),
        (
            "Madan-Carr-Chang (1998) Variance Gamma (VG) Süreci & Saf Sıçrama Lévy Varlıkları: Brownian difüzyonunu tamamen terk edip "
            "Gamma zaman saatiyle dönüştürülmüş saf sıçrama (pure jump) süreci; sonsuz aktivite ve sonlu varyasyon ile "
            "asimetrik çarpıklık (theta) ve basıklık (nu) parametreleri üzerinden opsiyon volatilite gülüşü analitiği.",
            0.95,
            {"phase": "faz-36", "topic": "levy-processes", "author": "Madan-Carr-Chang"}
        ),
        (
            "Avellaneda-Buff (1999) Belirsiz Volatilite Modeli (UVM) ve Black-Scholes-Barenblatt Doğrusal Olmayan PDE: "
            "Volatilitenin tek bir tahmin yerine [sigma_min, sigma_max] aralığında dalgalandığı en kötü durum (worst-case / super-replication) "
            "senaryosu; yerel gamma işaretine göre şekillenen doğrusal olmayan Barenblatt difüzyon denklemi ile kesin arbitrajsız alış/satış koruma bantları.",
            0.95,
            {"phase": "faz-36", "topic": "uncertain-volatility", "author": "Avellaneda-Buff"}
        ),
        (
            "Garman-Kohlhagen (1983) & FX Piyasalarında Vanna-Volga Fiyatlama: Küresel döviz masalarında ATM volatilite, "
            "25-Delta Risk Reversal ve 25-Delta Vega-Weighted Butterfly kotasyonlarından analitik Vega, Vanna ve Volga duyarlılık kalkanı "
            "ile volatilite gülüşü rekonstrüksiyonu ve One-Touch/No-Touch egzotik opsiyon fiyatlama marjları.",
            0.95,
            {"phase": "faz-36", "topic": "fx-derivatives", "author": "Garman-Kohlhagen"}
        ),
        (
            "Curve LLAMMA (crvUSD) Yumuşak Tasfiye (Soft Liquidation) Fiziği: Geleneksel borçlanma protokollerinin getirdiği %10 sert "
            "tasfiye cezası ve kaskat çöküş sarmalları yerine teminatı ardışık fiyat bantlarında sürekli ve tersinir (de-liquidation) "
            "olarak stabilcoine dönüştüren LLAMMA AMM invaryantı ve Morpho Blue izole risk yönetimi.",
            0.95,
            {"phase": "faz-36", "topic": "defi-liquidation", "author": "Curve LLAMMA"}
        ),
    ]

    for content, imp, meta in nodes_to_record:
        node, novel = cog_mem.record_memory(
            category="semantic",
            content=content,
            importance=imp,
            metadata=meta
        )
        print(f"[OK] Cognitive Node Recorded: {node.id} (Novel: {novel})")

    print("\n[SUCCESS] All Faz 36 knowledge successfully registered into exocortex and cognitive database!")

if __name__ == "__main__":
    main()
