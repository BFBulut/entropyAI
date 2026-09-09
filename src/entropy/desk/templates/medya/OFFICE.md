---
name: medya
title: Medya
purpose: Bir konuyu arastirip senaryoya ve gorsel yonergeye cevirir.
orchestrator: orkestrator
evaluator: degerlendirici
members: [arastirmaci, senarist, gorsel-yonetmen, degerlendirici]
default_provider: 
default_model: 
models: {claude: claude-sonnet-5, agy: gemini-3.8-flash-high}
default_effort: medium
max_parallel: 2
budget_tokens: 120000
---

# Medya

Bu ofis medya uretir. Once kaynak, sonra senaryo, en sonda gorsel yonerge gelir.
