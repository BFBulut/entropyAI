#!/usr/bin/env python3
"""CLI utility to generate a structured media agency audit scaffold."""

import argparse
import json
import urllib.parse

def generate_audit(url: str, brand: str) -> dict:
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc or url

    return {
        "brand_name": brand or domain.split(".")[0].capitalize(),
        "domain": domain,
        "audit_categories": [
            {"category": "Marka Kimliği", "status": "İncelendi", "priority": "Yüksek"},
            {"category": "Rakip Karşılaştırması", "status": "Hazır", "priority": "Yüksek"},
            {"category": "SEO & İçerik Kümesi", "status": "Bekliyor", "priority": "Orta"},
            {"category": "Sosyal Medya ve Dağıtım", "status": "Bekliyor", "priority": "Orta"}
        ],
        "recommended_funnel": {
            "tofu": "Eğitici blog içerikleri & video rehberler",
            "mofu": "Vaka analizleri (case studies) ve karşılaştırma sayfaları",
            "bofu": "Ücretsiz deneme / demo ve müşteri referansları"
        }
    }

def main():
    parser = argparse.ArgumentParser(description="Generate media agency brand audit")
    parser.add_argument("--url", default="https://example.com")
    parser.add_argument("--brand", default="Brand")
    args = parser.parse_args()

    res = generate_audit(args.url, args.brand)
    print(json.dumps(res, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
