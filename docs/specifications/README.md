# `docs/specifications/` — arşivlendi (Faz 12-E)

Bu klasördeki beş özellik belgesi (`AGY_CLI_INTEGRATION`, `MEMORY_RAG_SPECIFICATION`,
`SYSTEM_ARCHITECTURE`, `UI_SPECIFICATION`, `TASK_SCHEDULER_SPECIFICATION`) **2026-09-03**
tarihliydi; dördü bugünkü mimariyle çelişiyordu (tek sağlayıcı varsayımı, Supabase/Mem0,
sabit hex paleti, Desk/pano/beyin katmanlarının hiç olmaması).

Hepsi `docs/_archive/prototype/` altına taşındı. **Tek geçerli kaynak:**

- Mimari ve sözleşmeler → [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
- Güncel durum / imzalar → [`../STATE.md`](../STATE.md)
- Kararlar → [`../adr/`](../adr/)

`TASK_SCHEDULER_SPECIFICATION.md`'nin hâlâ geçerli olan özü `ARCHITECTURE.md` §8'e alındı.
Aynı commit'te kökteki çürük `EntropyAI_OneFile.spec` de
`docs/_archive/prototype/EntropyAI_OneFile.spec.txt` olarak arşivlendi
(hiç çağrılmıyordu, 32/127 hiddenimports, makineye çakılı `pathex`).
