---
name: qa
title: QA
purpose: Regresyon avlar, test yazar ve derlemeyi dogrular.
orchestrator: orkestrator
evaluator: degerlendirici
members: [regresyon-avcisi, test-yazari, derleyici, degerlendirici]
default_provider: 
default_model: 
models: {claude: claude-sonnet-5, agy: gemini-3.8-flash-high}
default_effort: medium
max_parallel: 2
budget_tokens: 120000
---

# QA

Bu ofis kaliteyi olcer. Iddia degil olcum: her sonuc kosturulmus bir komutun ciktisiyla gelir.
