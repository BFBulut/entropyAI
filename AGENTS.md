# AGENTS.md — Bu depoda ajanlar nasıl tanımlanır

> **Bu dosya bir kadro listesi DEĞİLDİR ve olmamalıdır.**
> Önceki sürümü 5 ajanlık uydurma bir kadro ilan ediyor ve var olmayan
> `Agents/*/persona.md` yollarına atıf yapıyordu. Ölçülmüş zararı `EntropyAI.spec`
> içindeki yorumda kayıtlı: dosya `.exe`'nin yanına `_internal/AGENTS.md` olarak
> düştüğünde Entropy kendi kadrosunu oradan "öğreniyor" ve **var olmayan ajanları
> sayıyordu**. Bu yüzden `AGENTS.md` paketlenmez ve gerçek kadro burada tutulmaz.
>
> Gerçek kadro kasadadır. Mimari: `docs/ARCHITECTURE.md` · Durum: `docs/STATE.md`

---

## 1. Gerçek ajanlar nerede

| Kim | Kaynak (tek doğruluk) | Okuyan kod |
|---|---|---|
| **Entropy AI'nin kendi ajanları** | `<kasa>/Entropy/Agents/<ad>/AGENT.md` | `entropy.agents.registry` |
| **Agent Desk ofis ajanları** (orkestratör + altları) | `<kasa>/Desk/Offices/<ofis>/agents/**` | `entropy.agents.desk_registry` |
| **Kullanıcının geliştirme alt ajanları** | `.claude/agents/*.md` (bu depoda, elle yazılır) | Claude Code CLI |
| **agy damıtıcı ajanı** | `.agents/agents/distiller/agent.md` | agy CLI |

Kullanıcı ajanlarını **Obsidian'da** düzenler; uygulama bunları iki sağlayıcı biçimine
**derler** (`entropy.agents.compile`):

```python
AGENT_DEFINITION_LAYOUT = {
    "agy":    (".agents/agents", "agent.md"),
    "claude": (".claude/agents", None),
}
```

Derleme çıktısı **türetilmiştir**: sürüm denetimine girmez, elle düzenlenmez, silinirse
yeniden üretilir. Derleme kökleri (Faz 11-A'dan beri): proje kökü + ayarlardaki etkin proje +
nötr Claude çalışma dizini. `APP_ROOT` **listede değildir** — kaynaktan koşarken deponun
kendisi olduğu için Entropy'nin kadrosu buradaki `.claude/agents/` klasörüne düşüyor ve
kullanıcının kendi alt ajanlarıyla karışıyordu.

---

## 2. `.claude/agents/` — bu klasör kimin

Bu klasördeki dosyalar **kullanıcının kendi Claude Code oturumları içindir**; Entropy'nin
çalışma zamanıyla ilgileri yoktur (Entropy Saf Kip `--setting-sources ""` ile bu klasörü
zaten yüklemez, kadrosunu `--agents <json>` ile açıkça enjekte eder).

Bugün altı geliştirme alt ajanı var: `memory-rag-engineer`, `ui-engineer`,
`agy-integration-engineer`, `qa-build-engineer`, `repo-curator`, `research-scout`.

Kurallar:

- Entropy'nin ürettiği kadro (`analist`, `arastirmaci`, `degerlendirici`, `orkestrator`,
  `yazar`) buraya **karışmaz**; ada göre `.gitignore`'dadır.
- Yeni bir geliştirme ajanı eklerken: kapsamı dar tut, dosya alanlarını diğerleriyle
  çakıştırma, "işe başlamadan `docs/STATE.md` + son faz raporunu oku" satırını koy.

---

## 3. Ajanların uyduğu değişmezler

1. **Orkestratör kod yazmaz.** Araştırır, planlar, kendi alt ajanlarını oluşturur/düzenler,
   raporlar; araç politikası salt okunurdur.
2. **Kanıtla kapat.** Bir işçi, testleri koşup yeşil sonucu raporuna iliştirmeden kartı
   `done` yapamaz.
3. **Denetim noktası disiplini.** İş modüllere bölünür; her modülden sonra kısa durum özeti
   diske yazılır. Çökme sonrası uzun sohbet günlüğünden değil bu özetten devam edilir.
4. **Ajanlar hafızaya hata ve günlük yazmaz.** Bir kural keşfedilirse uygulama kullanıcıya
   sorar; yalnızca "kalıcı yap" denince kural o ajanın sistem istemine enjekte edilir.
5. **Paylaşılan çalışma alanı dosyadır.** Ajanlar gizli API'lerle değil, ofis kökündeki
   `BOARD.md` / `ARCHITECTURE.md` / `RULES.md` üzerinden konuşur; doğuş talimatının ilk
   maddesi "başlamadan panoyu ve mimariyi oku"dur.
6. **Bilgi ve görev akışı tek yönlüdür:** Entropy → Desk. Desk Entropy'yi bilmez ve
   Entropy'nin panosuna kart itemez (`docs/adr/ADR-0001-desk-ayrimi.md`).
7. **Git güvenliği:** `git stash`, `git checkout --`, `git reset --hard` yasaktır.

---

## 4. Olaylar

Ajan yaşam döngüsü arayüze `entropy.core.event_bus` üzerinden görünür:
`agent_turn_started`, `agent_stream`, `agent_turn_completed`, `task_triggered`,
`task_completed`, `task_notification`, `checkpoint_written`, `proof_recorded`,
`office_progress`, `mailbox_updated`, `rules_updated`.
Tam sözleşme: `docs/ARCHITECTURE.md` §7.
