---
name: skill-creator
description: >-
  Yapay zekanın elinde olmayan yeni bir yetenek veya araç gerektiğinde kendi dosyaları içerisinde sıfırdan yeni bir skill ve Python scripti oluşturmasını sağlar.
tags: meta, tool-creation, self-synthesis, skills
version: 1.0.0
---

# Skill & Tool Creator Meta-Skill

Bu meta-yetenek, Entropy AI'ın kendi kendini geliştirmesi ve yeni uzmanlık alanlarını sisteme kalıcı olarak eklemesi için kullanılır.

## Yeni Bir Yetenek Nasıl Oluşturulur?

Bir kullanıcı sizden daha önce yeteneğiniz olmayan bir görev istediğinde (örn: ses işleme, kod optimizasyonu, e-ticaret analizi vb.):

1. `skills/<yetenek_adi>/` dizini oluşturun.
2. `skills/<yetenek_adi>/SKILL.md` dosyasını geçerli YAML frontmatter (`name`, `description`, `tags`) ve detaylı kullanım yönergeleriyle yazın.
3. Gerekiyorsa `skills/<yetenek_adi>/scripts/<arac_adi>.py` dosyasını oluşturun ve test edin.
4. Veya doğrudan yerleşik scripti çağırın:
```bash
python skills/skill-creator/scripts/create_new_skill.py --name "yetenek-adi" --desc "Açıklama" --instructions "Talimatlar"
```

## Önemli Prensipler
- Kodlar kesinlikle proje dizini içinde (`skills/`) yer almalıdır.
- Araçlar temiz argüman işleme (`argparse`) ve JSON formatında çıktı vermelidir.
- Oluşturulan araç anında Zen Mod arayüzündeki Yetenekler sekmesinde ve Chat Modundaki seçim kutusunda görünür hale gelir.
