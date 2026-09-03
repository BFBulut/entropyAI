---
name: financial-auditor
description: >-
  Şirket bilançolarını, gelir tablolarını, nakit akımını, EBITDA, likidite, kârlılık ve borçluluk rasyolarını denetler ve finansal analiz raporu sunar.
tags: finance, accounting, ratios, balance-sheet, ebitda
version: 1.0.0
---

# Financial Auditor Skill

Bu yetenek, finansal tabloları (Bilanço, Gelir Tablosu, Nakit Akım Tablosu) profesyonel yatırım analizi standartlarında incelemenizi sağlar.

## Çalıştırılabilir Rasyo Hesaplayıcı

Temel finansal rasyoları hesaplamak için:
```bash
python skills/financial-auditor/scripts/financial_ratios.py --current-assets 500000 --current-liab 250000 --net-income 80000 --revenue 1000000 --equity 400000
```

## Analiz Metodolojisi
1. **Likidite Analizi**: Cari Oran ($Dönen Varlıklar / Kısa Vadeli Yükümlülükler$), Asit-Test Oranı.
2. **Kârlılık Analizi**: Brüt Kâr Marjı, FAVÖK (EBITDA) Marjı, Net Kâr Marjı, Özkaynak Kârlılığı (ROE).
3. **Kaldıraç ve Borçluluk**: Borç / Özkaynak Oranı, Net Borç / FAVÖK.
4. **Nakit Akışı**: Faaliyetlerden sağlanan net nakit akışı ve serbest nakit akımı (FCF).
5. **Raporlama**: Bulguları Obsidian Kasasına veya Araştırma sekmesine Markdown tablosu olarak kaydedin.
