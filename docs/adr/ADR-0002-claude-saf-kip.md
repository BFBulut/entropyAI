# ADR-0002 — Entropy Saf Kip: Claude köprüsü izole koşar, kök `CLAUDE.md` oluşturulmaz

- Durum: **kabul edildi** (Faz 9.2'de uygulandı; `CLAUDE.md` yasağı Faz 11-A'da eklendi)
- Tarih: 2026-09-10
- Kaynak: `2026-09-10_Faz11_Arastirma_B_Depo_Denetimi.md` §3.2–3.3,
  `src/entropy/core/claude_bridge.py:123, 460, 769–780, 826–850, 1411–1460, 1552`

## Bağlam

Entropy hiçbir API anahtarı kullanmaz; yalnızca kullanıcının abonelik oturumuyla koşan iki CLI
üzerinden çalışır. Bu, kullanıcının kendi kurulumunu (sistem istemi, `CLAUDE.md`, MCP
sunucuları, otomatik hafıza, keşfedilen alt ajanlar) sürecin içine çekme riskini doğurur.
Kullanıcının açık isteği: **Entropy tek başına Claude üzerinde çalışabilmeli ve çalışırken
çıplak bir CLI terminali gibi değil, kendi kimliğiyle davranmalı.**

Yerel `--help` çıktısıyla doğrulanan gerçek: varsayılan kipte yüklenenler arasında hooks, LSP,
eklenti eşitlemesi, atıf, otomatik hafıza ve **`CLAUDE.md` otomatik keşfi** vardır; bağlam
yalnızca `--system-prompt[-file]`, `--append-system-prompt[-file]`, `--add-dir`,
`--mcp-config`, `--settings`, `--agents`, `--plugin-dir` ile açıkça verilebilir.

## Karar

1. Sistem istemi **eklenmez, değiştirilir**: `--system-prompt-file`.
2. Ayar kaynakları kapatılır: `--setting-sources ""` (kullanıcı/proje/yerel ayarlar ve
   keşfedilen ajanlar yüklenmez).
3. MCP yalnızca Entropy'nin verdikleri: `--strict-mcp-config` + `--mcp-config`.
4. Kadro açıkça enjekte edilir: `--agents <json>`.
5. Profil izole edilir: `CLAUDE_CONFIG_DIR` yeniden yazılır.
6. Çalışma dizini **git deposunun dışındadır** (`~/.entropy/workspace`) — CLI proje kimliğini
   literal cwd'den değil git kökünden çözdüğü için depo içi bir alt klasör izolasyon sağlamaz.
   Tek istisna: kart bir worktree'ye bağlıysa cwd o worktree'dir.
7. `--bare` **kullanılmaz**: abonelik OAuth'unu okumaz, API anahtarı ister.
8. **Depo kökünde `CLAUDE.md` oluşturulmaz.**

## Gerekçe

8. madde ölçüme dayanır: `--setting-sources ""` ayar kaynaklarını kapatır ama `CLAUDE.md`
otomatik keşfi **ayrı bir mekanizmadır** (yalnızca `--bare` kapatır) ve `--add-dir` ile verilen
kökler de CLAUDE.md dizini sayılır. Entropy her koşuya kasa + workspace, kart koşusunda ayrıca
proje dizinini ekler. Bugün sızıntı olmamasının **tek nedeni depoda böyle bir dosyanın
bulunmamasıdır**. Dosyayı yaratmak, ölçülmemiş bir kanaldan kullanıcının proje talimatlarını
Entropy'nin kimliğinin üstüne bindirirdi.

7. madde de bir ödünleşimdir: `--bare` en temiz izolasyonu verirdi ama abonelik kimliğini
kırdığı için ürünün temel kısıtıyla (API anahtarı yok) çelişir.

## Sonuçlar

- Kök markdown dosyaları: `AGENTS.md` (kısa yönlendirme) ve `GEMINI.md` (proje sözleşmesi,
  `pyproject.toml`'un `readme`'si) kalır; `CLAUDE.md` **yoktur** ve eklenmeden önce
  `--add-dir`/CLAUDE.md sızıntısı ayrı bir kartla ölçülmelidir.
- agy köprüsünde karşılık gelen bayraklar **yoktur** (`--setting-sources`,
  `--strict-mcp-config` yok) ve süreç proje dizininde koşar; bu, kapatılabilir bir açık değil
  **kayıt altına alınmış bir sınırdır**.
- Zorlayıcı test: `tests/contracts/test_phase9_claude_isolation_and_models.py`.
