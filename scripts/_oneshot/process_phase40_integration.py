"""
Integration script for Phase 40:
1. Append Phase 40 to MEMORY.md
2. Record cognitive memory nodes into SQLite via CognitiveMemorySystem
3. Sync Map of Content (BELLEK_HARITASI.md)
4. Append to Daily Notes
"""

import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, r"c:\EntropiAI\src")

from entropy.core.config import config
from entropy.brain.obsidian.vault_manager import ObsidianVaultManager
from entropy.brain.supabase.cognitive_memory import CognitiveMemorySystem

PHASE_40_MEMORY_ENTRY = """
## Hansen-Sargent Sağlam Kontrol, Glasserman-Li Nadir Olay, Bouchaud-Mézard Ekonofizik, Moallemi-Sağlam Kuyruk Dinamiği, Schwartz-Smith Emtia & MEV-Tax AMM (Faz 40) (2026-09-04)
- **Lars Peter Hansen & Thomas J. Sargent (2001/2008) Sağlam Kontrol (Robust Control), Knightian Belirsizlik & Entropik Ceza**: Referans ölçü $\mathbb{P}$'ye mutlak güven duymayan yatırımcının kötü niyetli doğanın seçtiği pertürbe $\mathbb{Q}$ ölçüsüne karşı bağıl entropi kısıtlı ($\mathcal{R}(\mathbb{Q} \parallel \mathbb{P}) \le \eta$) diferansiyel oyunu; robust HJB Isaacs PDE çözümü, en kötü durum sürüklenme bozulması ($h^* = -\\frac{1}{\\theta} \\sigma \\pi W V_W$), efektif riskten kaçınma katsayısı $\\gamma_{\\text{eff}} = \\gamma + \\frac{1}{\\theta}$, hisse senedi prim bulmacasının çözümü ve kriz dönemi aşırı ihtiyatlı nakde kaçış davranışı.
- **Paul Glasserman & Jingyi Li (2005) Nadir Olay Önem Örneklemesi (Importance Sampling for Credit Portfolio & CDO Tails)**: Büyük kredi portföylerinde ve sentetik CDO dilimlerinde %99.9 VaR / Expected Shortfall hesaplamasında standart Monte Carlo'nun sıfır vuruş çıkmazını aşan iki seviyeli simetrik önem örneklemesi; Seviye 1: Sistematik makro faktör $Z$'nin semer noktası (saddlepoint) kaydırması ($\\mu^*$), Seviye 2: Koşullu Bernoulli temerrüt göstergelerine Esscher bükmesi ($p_k(\\theta, z)$); asimptotik optimal varyans verimliliği ve $1,000\\times - 10,000\\times$ hesaplama hızlandırması.
- **Jean-Philippe Bouchaud & Marc Mézard (2000) & Victor Yakovenko Zenginlik Dağılımı Ekonofiziği & Yoğunlaşma Faz Geçişi**: Çok ajanlı Langevin stokastik diferansiyel denklemi ile piyasa servet dağılımının mikroskobik türetimi; Fokker-Planck durağan çözümü ile Pareto üssünün kapalı formu ($\\mu = 1 + \\frac{J}{\\sigma^2}$); piyasa oynaklığı likidite akışını aştığında ($\\sigma^2 \\ge J \\implies \\mu \\le 1$) gerçekleşen Bose-Einstein benzeri Yoğunlaşma Faz Geçişi (Condensation Phase Transition), tüm sistemik servetin tek bir tekelde toplanması ve likidite karadeliği ile ani çöküş (Flash Crash) mekanizması.
- **Ciamac C. Moallemi & Mehmet Sağlam (2013) Limit Emir Defterlerinde Kuyruk Bekleme Süresi Maliyeti (Cost of Queue Wait) & Dinamik İcra**: Pasif limit emri koyup spread kazanmak ile agresif piyasa emri verip anında dolmak arasındaki dinamik kontrol ödünleşimi; kuyruk bekleme gecikmesi, elde tutma maliyeti ($h$), iptal hızı ($\\theta$) ve toksik sıçramalardan kaynaklanan ters seçim ($\\text{AS}$) riskinin Bellman fonksiyonu $V(q)$ ile modellenmesi; optimal kritik kuyruk derinliği eşiği $q^* \\approx \\lfloor \\frac{\\Delta - 2\\text{AS}}{2h/\\lambda_{\\text{fill}}} \\rfloor$ ve Akıllı Emir Yönlendirici (SOR) kuralı.
- **Eduardo Schwartz & James E. Smith (2000) İki Faktörlü Kısa/Uzun Vadeli Emtia Fiyat Dinamiği**: Gibson-Schwartz'ın gözlemlenemeyen kolaylık getirisi (convenience yield) zafiyetini aşan doğrudan log spot fiyat ayrıştırması ($\\ln S_t = \\chi_t + \\xi_t$); kısa vadeli geçici şoklar ($\\chi_t$, Ornstein-Uhlenbeck) ve uzun vadeli yapısal denge trendi ($\\xi_t$, Aritmetik Brown); vadeli işlem eğrisinde Samuelson hipotezinin analitik temsili ($e^{-\\kappa \\tau}$ sönümü), kapalı form Futures fiyatı $\\ln F(T) = e^{-\\kappa T}\\chi_0 + \\xi_0 + A(T)$ ve Kalman filtresi ile anlık durum-uzayı kestirimi.
- **Guillermo Angeris, Alex Evans, Tarun Chitra & Tim Roughgarden (2023-2024) LVR-Hafifletme, Dinamik Ek Vergi & MEV-Tax AMM Mimarisi**: Sabit komisyonlu AMM'lerde LP'leri tüketen LVR (Loss-Versus-Rebalancing) toksik sızıntısını ortadan kaldıran dinamik MEV Vergisi ($\\tau(\\phi)$); blok oluşturucu rüşvetine (priority fee / builder tip $\\phi$) endeksli dinamik ek vergi ile arama botlarının arbitraj fazlasının doğrudan havuza aktarılması; CoW AMM ayrık zamanlı toplu açık artırma (Batch Auction) ve tek fiyat takası ile $\\text{LVR}_{\\text{batch}} \\equiv 0$ teoremi.
- **Detaylı Rapor**: [[HansenSargent_GlassermanLi_BouchaudMezard_MoallemiSaglam_SchwartzSmith_ve_MEVTax]]
"""

COGNITIVE_NODES = [
    {
        "category": "semantic",
        "content": (
            "Hansen-Sargent Sağlam Kontrol (Robust Control): Model yanlış tanımlaması ve Knightian belirsizlik "
            "altında bağıl entropi kısıtlı (Kullback-Leibler) minimax oyunu. Doğanın en kötü durum sürüklenme "
            "bozulması h* = -(1/theta) sigma pi W V_W ve efektif riskten kaçınma gamma_eff = gamma + 1/theta. "
            "Hisse senedi prim bulmacasını ve piyasa şoklarında aşırı temkinli nakde kaçışı açıklar."
        ),
        "importance": 0.98,
        "metadata": {"pillar": 1, "phase": 40, "author": "Hansen & Sargent (2001/2008)"}
    },
    {
        "category": "semantic",
        "content": (
            "Glasserman-Li Kredi Portföyü Nadir Olay Önem Örneklemesi (Two-Level IS): Çok faktörlü Gauss/t-kopula "
            "kredi sepetlerinde ve CDO dilimlerinde %99.9 VaR ve Expected Shortfall için iki seviyeli üstel bükme. "
            "Seviye 1'de sistematik faktör Z saddlepoint mu* ile kaydırılır, Seviye 2'de koşullu Bernoulli temerrüt "
            "göstergelerine Esscher bükmesi pk(theta, z) uygulanır. Standart Monte Carlo'ya göre 1000x-10000x varyans azaltımı."
        ),
        "importance": 0.98,
        "metadata": {"pillar": 2, "phase": 40, "author": "Glasserman & Li (2005)"}
    },
    {
        "category": "semantic",
        "content": (
            "Bouchaud-Mézard Ekonofizik Zenginlik Güç Yasası ve Yoğunlaşma Faz Geçişi: Çarpımsal yatırım getirisi ve "
            "ortalama alan servet yeniden dağılımı Langevin dinamiği. Fokker-Planck durağan çözümünde Pareto üssü "
            "mu = 1 + J/sigma^2. Piyasa oynaklığı likidite akışını aştığında (sigma^2 >= J, mu <= 1) sistemik "
            "Bose-Einstein benzeri yoğunlaşma faz geçişi meydana gelir; servetin makroskopik kesri tek bir tekelde toplanır "
            "ve piyasa derinliği çökerek Flash Crash yaratır."
        ),
        "importance": 0.96,
        "metadata": {"pillar": 3, "phase": 40, "author": "Bouchaud & Mézard (2000)"}
    },
    {
        "category": "semantic",
        "content": (
            "Moallemi-Sağlam Limit Emir Defteri Kuyruk Bekleme Süresi Maliyeti: LOB'da pasif limit emir ile spread "
            "kazanma ve agresif piyasa emri ile anında dolma arasındaki dinamik kontrol ödünleşimi. Kuyruk derinliği q, "
            "elde tutma maliyeti h, iptal hızı theta ve ters seçim AS altındaki Bellman denklemi. Kritik eşik "
            "q* = floor((Delta - 2*AS) / (2*h / lambda_fill)); q <= q* ise pasif limit emir koy, q > q* ise piyasa emri ver."
        ),
        "importance": 0.97,
        "metadata": {"pillar": 4, "phase": 40, "author": "Moallemi & Sağlam (2013)"}
    },
    {
        "category": "semantic",
        "content": (
            "Schwartz-Smith İki Faktörlü Emtia Fiyat Dinamiği: Gözlemlenemeyen kolaylık getirisi yerine doğrudan log spot "
            "fiyat ayrıştırması ln S_t = chi_t + xi_t. chi_t kısa vadeli ortalamaya dönen geçici şoklar (Ornstein-Uhlenbeck), "
            "xi_t uzun vadeli yapısal denge trendi (Aritmetik Brown). Samuelson hipotezini analitik içerir; vadeli işlem "
            "eğrisinde ln F(T) = exp(-kappa*T)*chi_0 + xi_0 + A(T) ve Kalman filtresi ile durum uzayı kestirimi."
        ),
        "importance": 0.97,
        "metadata": {"pillar": 5, "phase": 40, "author": "Schwartz & Smith (2000)"}
    },
    {
        "category": "semantic",
        "content": (
            "Angeris-Roughgarden MEV-Tax ve CoW AMM Mimarisi: Sabit komisyonlu AMM'lerde likidite sağlayıcıları (LP) "
            "tüketen toksik LVR (Loss-Versus-Rebalancing) sızıntısını ortadan kaldıran mekanizma tasarımı. Blok oluşturucu "
            "rüşvetine (priority fee phi) bağlı dinamik MEV Vergisi tau(phi) ile arbitraj rantının LP havuzuna aktarılması "
            "ve CoW AMM ayrık zamanlı toplu açık artırması ile LVR_batch = 0 teoremi."
        ),
        "importance": 0.99,
        "metadata": {"pillar": 6, "phase": 40, "author": "Angeris, Evans, Chitra & Roughgarden (2023-2024)"}
    }
]

def main():
    print("Starting Phase 40 Cognitive Integration...")
    vault_manager = ObsidianVaultManager()

    # 1. Append to MEMORY.md if not already present
    mem_path = vault_manager.memory_file
    mem_text = mem_path.read_text(encoding="utf-8")
    if "Faz 40" not in mem_text:
        print("Appending Phase 40 to MEMORY.md...")
        with open(mem_path, "a", encoding="utf-8") as f:
            f.write(PHASE_40_MEMORY_ENTRY)
        print("MEMORY.md updated successfully.")
    else:
        print("Phase 40 already present in MEMORY.md.")

    # 2. Record to CognitiveMemorySystem (SQLite + 384d Neural Embeddings)
    cog_sys = CognitiveMemorySystem()
    print("Recording cognitive memory nodes into SQLite...")
    for item in COGNITIVE_NODES:
        node, is_novel = cog_sys.record_memory(
            category=item["category"],
            content=item["content"],
            importance=item["importance"],
            metadata=item["metadata"]
        )
        print(f"Recorded node [{node.id[:18]}...] - Novel: {is_novel} - Importance: {node.importance}")

    # 3. Append to Daily Notes
    daily_entry = (
        "🧠 [Otonom Finans Yeteneği Geliştirme - Faz 40]: Hansen-Sargent Sağlam Kontrol, "
        "Glasserman-Li İki Seviyeli Önem Örneklemesi, Bouchaud-Mézard Zenginlik Dağılımı ve Yoğunlaşma Faz Geçişi, "
        "Moallemi-Sağlam Kuyruk Bekleme Maliyeti ve Dinamik LOB İcrası, Schwartz-Smith İki Faktörlü Emtia Dinamiği "
        "ve Angeris-Roughgarden MEV-Tax / LVR-Hafifletme AMM Mimarisi araştırıldı, Obsidian Reports altına kaydedildi "
        "ve bilişsel hafızaya işlendi."
    )
    daily_file = vault_manager.append_daily_log(daily_entry)
    print(f"Daily log appended to: {daily_file}")

    # 4. Sync Map of Content (BELLEK_HARITASI.md)
    print("Syncing Map of Content (BELLEK_HARITASI.md)...")
    moc_file = vault_manager.sync_map_of_content()
    print(f"Map of Content synced at: {moc_file}")

    # 5. Verify Hybrid Recall
    print("\nVerifying Hybrid Recall for Phase 40 topics:")
    queries = [
        "Hansen-Sargent model misspecification robust control worst-case drift",
        "Glasserman-Li two-level importance sampling credit portfolio CDO",
        "Bouchaud-Mezard wealth distribution condensation phase transition",
        "Moallemi-Saglam queue waiting cost limit order book",
        "Schwartz-Smith two-factor commodity short term long term",
        "Angeris Roughgarden MEV Tax AMM LVR batch auction"
    ]
    for q in queries:
        recalled = cog_sys.hybrid_recall(q, top_k=2)
        print(f"\nQuery: '{q[:40]}...'")
        for node, score in recalled:
            print(f"  -> Score: {score:.4f} | Cat: {node.category} | Content: {node.content[:80]}...")

    print("\nPhase 40 Integration Complete!")

if __name__ == "__main__":
    main()
