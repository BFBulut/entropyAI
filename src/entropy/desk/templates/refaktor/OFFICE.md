---
name: refaktor
title: Refaktör
purpose: Var olan kodu davranisini bozmadan sadelestirir ve testle korur.
orchestrator: orkestrator
evaluator: degerlendirici
members: [mimar, uygulayici, test-yazari, degerlendirici]
default_provider: 
default_model: 
models: {claude: claude-sonnet-5, agy: gemini-3.8-flash-high}
default_effort: medium
max_parallel: 2
budget_tokens: 120000
---

# Refaktör

Bu ofis refaktor yapar. Davranis degismez; testler once yesil olmali, sonra yesil kalmalidir.
