---
name: arastirma
title: Araştırma
purpose: Bir konuyu kaynaklariyla arastirip karar verilebilir bir nota indirger.
orchestrator: orkestrator
evaluator: degerlendirici
members: [arastirmaci, analist, yazar, degerlendirici]
default_provider: 
default_model: 
models: {claude: claude-sonnet-5, agy: gemini-3.8-flash-high}
default_effort: medium
max_parallel: 2
budget_tokens: 120000
---

# Araştırma

Bu ofis arastirma yapar. Cikti her zaman kaynakli, olculebilir ve kisa bir nottur.
Yazma yetkisi yalnizca yazar ajanindadir; digerleri okur ve analiz eder.
