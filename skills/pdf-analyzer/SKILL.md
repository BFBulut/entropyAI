---
name: pdf-analyzer
description: >-
  PDF belgelerini, finansal dökümleri, kurumsal raporları ve tabloları analiz eder, metin ve tabloları yapılandırılmış biçimde çıkarır.
tags: pdf, analysis, document, tables
version: 1.0.0
---

# PDF Analyzer & Document Extractor Skill

Bu yetenek, sisteme yüklenen veya yerel dosya yolunda bulunan PDF belgelerini derinlemesine incelemenizi, metinlerini ve tablolarını ayrıştırmanızı sağlar.

## Çalıştırılabilir Araçlar

Belgeden metin ve özet çıkarmak için:
```bash
python skills/pdf-analyzer/scripts/extract_pdf.py --file <pdf_dosya_yolu>
```

## Kullanım Yönergeleri
1. Kullanıcı bir PDF belgesi sunduğunda veya analiz talep ettiğinde bu aracı kullanın.
2. Belge içerisindeki bölümleri, başlıkları ve tabloları ayrıştırın.
3. Finansal tabloları (Bilanço, Gelir Tablosu) satır ve sütun bazında yapılandırın.
4. Elde edilen bulguları özetleyerek teknik bir araştırma raporuna dönüştürün.
