---
name: google-flow
version: "1.0.0"
description: >-
  Automates Google Flow (labs.google/fx/tools/flow) for AI video generation using Veo and Omni Flash models,
  and image generation using Imagen and Nano Banana. Supports automated session management, real-Chrome passive capture auth,
  empty project creation, prompt engineering, video parameter tuning (aspect, duration up to 10s), and MCP tool orchestration.
tags: video-generation, google-flow, veo, omni-flash, imagen, mcp, automation, ai-video
---

# Google Flow Video & Image Automation Skill

Google Flow (`https://labs.google/fx/tools/flow`) is Google's flagship generative media studio combining **Veo** (state-of-the-art cinematic video generation) and **Imagen / Nano Banana** (high-fidelity image generation).

This skill enables coding agents and desktop autonomous systems to orchestrate Google Flow programmatically from the terminal, Python scripts, or MCP (Model Context Protocol).

---

## 1. Supported Models & Specifications

### Video Models (Veo & Omni Flash)
| Model Name | CLI Alias | Max Duration | Ref Image Cap | Primary Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **Omni Flash** | `omni-flash` | **10s** | **7** | **High-speed, multi-reference video generation (Recommended)** |
| **Veo 3.1 Lite** | `veo-lite` | 8s | 3 | Fast iteration, storyboard drafts |
| **Veo 3.1 Fast** | `veo-fast` | 8s | 3 | Balanced speed and motion coherence |
| **Veo 3.1 Quality** | `veo-quality` | 8s | 0 | Maximum visual fidelity (single-shot) |
| **Veo 3.1 Lite LP** | `veo-lite-lp` | 8s | 3 | Low priority / economical rendering |

### Image Models
| Model Name | CLI Alias | Ref Cap | Aspect Ratios |
| :--- | :--- | :--- | :--- |
| **NARWHAL** | `nano2` | 10 | `9:16`, `16:9`, `1:1`, `4:3`, `3:4` |
| **GEM_PIX_2** | `nano-pro` | 10 | `9:16`, `16:9`, `1:1`, `4:3`, `3:4` |
| **IMAGEN_3_5** | `image4`, `imagen4` | 3 | `9:16`, `16:9`, `1:1`, `4:3`, `3:4` |

---

## 2. Authentication Architecture (Passive Capture Pattern)

Google Flow does not offer public API keys and blocks automated headless browsers with Google Bot Detection (G12).
Authentication uses the **Passive Capture Pattern**:
1. Run `gflow auth login` (or programmatic wrapper).
2. It launches the system's real Google Chrome (`chrome.exe`) without automation flags.
3. The user signs in or confirms the Google session on `labs.google/fx/tools/flow`.
4. Upon closing Chrome, the session cookies (NextAuth session token & SAPISID) are verified and encrypted in the local profile root (`%LOCALAPPDATA%\ffroliva\gflow-cli\profile_default`).
5. All future generations, batch queues, and MCP calls run **fully autonomously in the background**.

### Verifying Auth Status:
```bash
gflow auth status
```
Programmatically via Python:
```python
import subprocess
result = subprocess.run(["gflow", "auth", "status"], capture_output=True, text=True)
is_authenticated = "verified" in result.stdout.lower() or result.returncode == 0
```

---

## 3. Project Management (Empty Project Creation)

To generate in a dedicated empty project instead of cluttering default scratch spaces:

### CLI:
```bash
# Create a fresh empty project
gflow project create --title "Studio Omni Flash Empty"

# Or generate directly with a project title (auto-creates if non-existent)
gflow video t2v "Cinematic aerial shot of Tokyo at sunrise, 4k photorealistic" \
  --model omni-flash \
  --project-title "Studio Omni Flash Empty" \
  --duration 10 \
  --aspect 16:9 \
  -o ./output/tokyo_sunrise.mp4
```

---

## 4. Video Generation Commands

### Text-to-Video (T2V) with Omni Flash:
```bash
gflow video t2v "Cyberpunk drone flying through neon-lit futuristic alleyways, cinematic lighting, 8k resolution" \
  --model omni-flash \
  --aspect 16:9 \
  --duration 10 \
  --project-title "Omni Studio" \
  -o ./videos/cyberpunk_drone.mp4
```

### Image-to-Video (I2V):
```bash
gflow video i2v "Camera slowly pushes in while snow falls gently" \
  --initial-frame ./assets/winter_cabin.png \
  --model omni-flash \
  --aspect 16:9 \
  --duration 8 \
  -o ./videos/winter_cabin_motion.mp4
```

---

## 4.1. Audio, Dialogue & Multilingual (Turkish) Prompt Engineering Formula

Veo 3.1 and Omni Flash synthesize **video and synchronized audio in a single multimodal pass**. 

### Neden Varsayılan Promptlar Türkçe Konuşmaz?
1. **İçerik Dili:** Promptta konuşma metni verilmediğinde model rastgele Amerikan İngilizcesi fonemleri veya mırıltı üretir.
2. **Tırnak İntizamı:** Veo, diyalog metinlerini **kesinlikle çift tırnak (`"..."`)** içinde arar. Tırnaksız "talking" betimlemeleri konuşma üretmez.
3. **Dil Direktifi:** Modele açıkça `speaks in Turkish` direktifi verilmelidir.

### Garantili Türkçe Konuşma ve Dudak Senkronu Formülü:
```text
[Cinematic Visual Scene in English: lighting, camera angle, macro details, character appearance]
The character speaks fluent Turkish with expressive comedic facial expressions and synced lip movements.
Dialogue: "Buraya 1-2 cümlelik kısa ve vurucu Türkçe diyalog."
Audio SFX: [Contextual sound effects, e.g. footsteps, wing flutter]
Audio Ambient: [Room tone, quiet night ambiance]
```

### Örnek Komut (9:16 Dikey Türkçe Konuşan Karakter):
```bash
gflow video t2v "Vertical 9:16 macro cinematic video. A funny anthropomorphic cockroach stands on its hind legs on a shiny kitchen countertop at night, gesturing passionately at the camera under the refrigerator light. The cockroach speaks fluent Turkish with expressive lip-sync. Dialogue: 'Kardeşim gecenin üçünde dolabı niye çat diye açıyorsun? İki dakika kırıntı kovalayacaktık kör olduk!' Audio SFX: light countertop taps. Audio Ambient: refrigerator hum." \
  --model omni-flash \
  --aspect 9:16 \
  --duration 10 \
  -o ./output/turkce_hamambocek.mp4
```

### Kritik İpuçları:
- **Diyalog Uzunluğu:** 10 saniyelik bir klip için diyalog 4-7 saniyelik (12-20 kelime) olmalıdır. Çok uzun cümleler dudak senkronizasyonunu bozar.
- **İki Katmanlı Güvence (Dual-Track):** Veo'nun yerleşik konuşma sentezine ek olarak, prodüksiyon kalitesinde yayın için her zaman yerel nöral TTS (`edge-tts` / `tr-TR-AhmetNeural`) ve FFmpeg muxing boru hattı hazır tutulmalıdır.

---

## 4.2. Gerçek Ürün Tutarlılığı (Product Fidelity) ve İleri Düzey I2V İş Akışı

### Neden T2V (Text-to-Video) Ürün Reklamlarında Başarısız Olur?
Text-to-Video modunda bir ürün adı (`Canivo Joint Plus 15 kg`) yazıldığında, yapay zeka modelinin eğitim verisinde o spesifik marka ve ambalaj bulunmadığı için model ambalajı **tahmin eder (halüsinasyon üretir)**. Sonuçta ortaya çıkan ürün gerçeğinden farklı logo, renk ve form taşır.

### Çözüm: 3 Aşamalı I2V (Image-to-Video) Ürün Çıpalama Protokolü
1. **Adım 1: Gerçek Ürün Görselinin Elde Edilmesi (Packshot Acquisition):**
   * Ürünün web sitesinden (örn. `canivopets.com`) veya ürün kataloğundan yüksek çözünürlüklü, temiz stüdyo görseli temin edilir (`./assets/canivo_joint_plus.png`).
2. **Adım 2: Başlangıç Karesi Kilitleme (`--initial-frame`):**
   * Video sıfırdan metinle değil, doğrudan gerçek ürün görseliyle başlatılır:
   ```bash
   gflow video i2v --initial-frame ./assets/canivo_joint_plus.png \
     "Cinematic slow zoom-in on the product packshot in a bright modern sunlit apartment, golden light beams, happy golden retriever runs into frame joyfully" \
     --model omni-flash \
     --aspect 9:16 \
     --duration 10 \
     -o ./output/canivo_i2v_ad.mp4
   ```
3. **Adım 3: Çift Kare İnterpolasyonu (`--initial-frame` + `--end-frame`):**
   * Açılışta ürünün yakından görünümü (`start.png`), kapanışta ise ürünün logo/kutu tasarımı (`end.png`) verilerek Omni Flash ile geçiş hareketinin mükemmel enterpole edilmesi sağlanır.
4. **Adım 4: Promptun Sadece Harekete Odaklanması:**
   * I2V kullanıldığında promptta ürünün fiziksel detaylarını ("blue bag, white letters") tekrar tarif etmek modeli şaşırtır. Prompt sadece kamera açısına, ışıklandırmaya ve harekete ("slow pan, sunlight glistening, dog wagging tail") odaklanmalıdır.

---

## 4.3. Google Flow Saf Doğal Ses Mimarisi ve Merkezi Depolama Protokolü

### 1. Saf Doğal Multimodal Ses (Pure Native Audio - Sıfır Harici TTS/FFmpeg)
* **Kural:** Google Flow kullanırken KESİNLİKLE harici bir TTS motoru (`edge-tts`, gTTS) ile ses üretilmez ve FFmpeg ile harici ses miksi yapılmaz. Harici ses bindirmek video ile dudak ve hareket senkronizasyonunu bozar.
* **Flow Yerleşik Ses Yeteneği:** Google Veo ve Omni Flash tek aşamada hem videoyu hem de sesi multimodal olarak üretir.
* **Ses Direktiflerinin Doğru Tanımlanması:**
  ```text
  Dialogue: "Dostunuzun eklem sağlığı ve enerjisi için Canivo Joint Plus!"
  Audio SFX: crunchy kibbles pouring into stainless bowl, joyful dog tail wagging.
  Audio Ambient: peaceful sunlit modern room ambiance, soft commercial tone.
  ```
* Flow'un indirdiği MP4 dosyası içindeki doğal ses, tek ve nihai teslim varlığıdır.

### 2. Merkezi Dosya Düzeni (`C:\EntropiAI\google_flow_files\`)
* Google Flow ile üretilen tüm varlıklar (başlangıç görselleri, ara kareler, çıktılar) dağınık klasörlere değil; merkezi olarak `C:\EntropiAI\google_flow_files\<proje_adi>\` altına kaydedilir.
* Örnek: `google_flow_files/canivopets_joint_plus/`, `google_flow_files/canivopets_meta_ad/`, `google_flow_files/talking_bugs_project/`.

### 3. Ürün Hedefi Sürekliliği (Product Target Continuity)
* Kullanıcı ile bir ürün üzerinde mutabık kalındığında (örn. Canivo Joint Plus), arka plandaki algoritmalar başka bir ürünü (örn. Canivo Hunter) öne çıkarsa bile kullanıcıya sorulmadan sessizce hedef değiştirilemez. Hedeflenen ürünün packshot'ı doğrudan ilgili alt sayfadan temin edilir.

---


## 5. Model Context Protocol (MCP) Integration

The `google-flow` MCP server allows AI agents (Antigravity, Claude Code, Cursor) to drive Flow via standard JSON-RPC tools.

### Starting MCP Stdio Server:
```bash
gflow mcp run
```

### Configured in `C:\Users\batu_\.gemini\settings.json`:
```json
"mcpServers": {
  "google-flow": {
    "command": "gflow",
    "args": ["mcp", "run"]
  }
}
```

### Available MCP Tools:
- `gflow_auth_status()`: Checks whether an active Google Flow session is verified.
- `gflow_list_projects()`: Lists all projects in Google Flow.
- `gflow_generate_video(prompt, model='omni-flash', project_name='...', duration=10, aspect='16:9', output='...')`: Generates video.
- `gflow_generate_image(prompt, model='nano2', aspect='1:1', output='...')`: Generates image.
- `gflow_get_credits()`: Returns active Flow credit balance.
- `gflow_character_list(project)`: Lists consistent characters in a project.

---

## 6. Python Automation Script

Use `scripts/flow_video_generator.py` for automated orchestration with pre-flight checks, model validation, and video generation.
