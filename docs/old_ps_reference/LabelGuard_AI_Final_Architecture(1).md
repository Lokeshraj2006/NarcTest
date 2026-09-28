# LabelGuard AI — Final AI Architecture & Model Sheet
### SIH 26034 | Packaged Commodity Compliance System | September 2026

---

## Architecture Overview

```
                        USER SCANS PRODUCT
                               |
                               v
                    ┌─────────────────┐
                    │   TOPIQ v0.1    │  Step 1: Image Quality Gate
                    │  (Quality OK?)  │  Blur / Lighting / Completeness
                    └────────┬────────┘
                             | PASS
                             v
                    ┌─────────────────┐
                    │ Google ML Kit   │  Step 2: Read all text
                    │ Text Recognition│  On-device, Latin + Devanagari
                    │ v2 (On-device)  │  Cloud API for Tamil/Telugu/Bengali
                    └────────┬────────┘
                             |
               ┌─────────────┼─────────────┐
               v                           v
     ┌──────────────────┐          ┌───────────────┐
     │ ML Kit Bounding  │          │ GLiNER-small  │  Step 3: Extract
     │ Boxes + Python   │          │ v2.5 (90M)    │  structured fields
     │ Spatial Clustering│          │ (Zero-shot NER│  from ML Kit output
     │ (Label regions)  │          │  from OCR text)│
     └────────┬─────────┘          └──────┬────────┘
              └─────────────┬─────────────┘
                            |
                   [If Hindi-English mixed text
                    recall is weak on GLiNER-small]
                            |
                    ┌───────v────────┐
                    │ IndicBERT v2   │  Step 3b: Conditional fallback
                    │ (Fine-tuned    │  Only activated if GLiNER-small
                    │  Indian NER)   │  underperforms on real labels
                    └───────┬────────┘
                            |
                            v
                 ┌──────────────────┐
                 │Grounding DINO 1.5│  Step 4: Detect symbols
                 │ (Zero-shot:      │  "FSSAI logo", "veg dot",
                 │  text prompt →   │  "barcode", "ISI mark"
                 │  visual detect)  │  No training needed
                 └────────┬─────────┘
                          v
                 ┌─────────────────┐
                 │   DocTR v0.9    │  Step 5: Measure font heights
                 │  (Font size →   │  Compare against Rule 7
                 │   Rule 7 check) │
                 └────────┬────────┘
                          v
                 ┌─────────────────┐
                 │  RULE ENGINE    │  Step 6: Deterministic checks
                 │  (Python logic) │  15 mandatory fields, dates,
                 │                 │  metric units, MRP format
                 └────────┬────────┘
                          |
               ┌──────────┼──────────┐
               v                     v
      ┌──────────────────┐  ┌────────────────────┐
      │ PatchCore        │  │ Phi-4-mini 3.8B    │  Step 7: Deep
      │ (EfficientNet-B0 │  │ (local, 4GB VRAM)  │  analysis
      │  5M backbone)    │  │       OR           │
      │ Tamper detection │  │ Gemini API (cloud) │
      └──────┬───────────┘  │       OR           │
             │              │ Gemma 3 27B (GCP)  │
             │              │ Legal LLM + RAG    │
             │              └──────┬─────────────┘
             └──────────┬──────────┘
                        v
               ┌─────────────────┐
               │   FINAL VERDICT │  GREEN / YELLOW / RED
               │  + BSA Sec 63   │  + Evidence Package
               │  Evidence Pack  │  + PDF Compliance Report
               └────────┬────────┘
                        v
               ┌─────────────────┐
               │  Leaflet.js +   │  Step 8: Plot on dashboard
               │  OpenStreetMap  │  Violation heatmaps + pins
               └─────────────────┘
```

### Zero-Shot Design Philosophy

The entire extraction stack requires **no custom training data** and works on day one:

```
Text:    Google ML Kit (OCR)  →  GLiNER-small v2.5 (zero-shot NER)  →  Structured fields
Visual:  Camera image         →  Grounding DINO 1.5 (zero-shot)     →  Detected symbols
Layout:  ML Kit bounding boxes →  Python spatial clustering          →  Label regions
Indian:  IndicBERT v2 (fallback only — needs fine-tuning if activated)
```

---

## Model Sheet — Stats, Reasoning & How It Works

### 1. TOPIQ v0.1 — Image Quality Gate

| Stat | Value |
|------|-------|
| **Params** | ~10M |
| **License** | BSD |
| **GPU** | No (runs on CPU/mobile) |
| **Offline** | Yes |

**Why:** OCR on a blurry or dark image wastes compute and gives garbage results. TOPIQ gates the pipeline — only clean images proceed.

**How:** No-reference quality scorer using cross-scale attention. Evaluates sharpness, noise, and exposure at multiple resolutions in one pass. Outputs a 0–1 score. Above 0.7 = proceed. Below 0.4 = prompt user "Hold steady / Move closer / Improve lighting".

---

### 2. Google ML Kit Text Recognition v2 — OCR Engine

| Stat | Value |
|------|-------|
| **Cost** | Free |
| **License** | Google APIs ToS (free for commercial use) |
| **GPU** | No (runs on-device via Neural Network API) |
| **Offline** | Yes (on-device model) |
| **Scripts (On-device)** | Latin + Devanagari (Hindi) |
| **Scripts (Cloud API)** | Latin + Devanagari + Tamil + Telugu + Bengali + Kannada + more |
| **Flutter Plugin** | `google_mlkit_text_recognition` |

**Why:** Native to Android and iOS — no third-party dependency. Runs completely on-device with zero API calls for Latin and Devanagari scripts. Seamless Flutter integration via official plugin. Part of Google ecosystem which aligns well with SIH. Free with no usage limits for on-device processing.

**How:** Uses Google's on-device neural network optimized for mobile processors. The camera feeds frames to ML Kit which detects text blocks, lines, and individual elements. Returns structured output with recognized text, bounding box coordinates, detected language, and confidence score per element.

**On-device vs Cloud:**

| Feature | On-device (free, offline) | Cloud API (free tier: 1000/month) |
|---------|--------------------------|-----------------------------------|
| Latin (English) | Yes | Yes |
| Devanagari (Hindi) | Yes | Yes |
| Tamil | No | Yes |
| Telugu | No | Yes |
| Bengali | No | Yes |
| Speed | ~100ms per frame | ~500ms (network latency) |
| Internet needed | No | Yes |

---

### 3. ML Kit Bounding Boxes + Python Spatial Clustering — Label Region Analysis

| Stat | Value |
|------|-------|
| **Extra model needed** | None — uses ML Kit output already in memory |
| **Extra params** | 0 |
| **GPU** | No |
| **Code** | ~50 lines of Python coordinate logic |

**Why:** ML Kit already returns precise bounding box coordinates for every text block and line. Product labels have consistent spatial structures — MRP is typically top-right, ingredients are bottom, manufacturer address is a distinct block. A simple spatial clustering algorithm groups these coordinates into meaningful regions without loading a separate 25M-param layout model. One fewer model to load, zero extra VRAM, runs on any hardware.

**How:** After ML Kit extracts text blocks with (x, y, width, height) coordinates, a Python module:
1. Groups text blocks by y-coordinate proximity (blocks on the same horizontal band → same region)
2. Checks x-coordinate alignment (left-aligned blocks near each other → same section)
3. Identifies key anchor patterns (e.g., text containing "MRP" anchors the price region, "Ingredients" anchors the ingredients list)
4. Outputs labelled regions: MRP zone, nutrition table, manufacturer block, ingredients list, barcode area

**Why this replaced DocLayout-YOLO:**

| Factor | DocLayout-YOLO (25M) | ML Kit + Spatial Clustering |
|--------|----------------------|-----------------------------|
| Extra model to load | Yes (25M, GPU preferred) | No — uses existing ML Kit output |
| VRAM usage | ~200MB | 0 |
| Storage for weights | ~100MB | 0 |
| Runs on CPU-only laptop | Slow | Instant |
| Accuracy on product labels | High | Good — labels have consistent spatial patterns |

---

### 4. GLiNER-small v2.5 — Zero-Shot NER (Primary Text Extractor)

| Stat | Value |
|------|-------|
| **Params** | 90M |
| **License** | Apache 2.0 |
| **GPU** | Optional (~500MB VRAM if GPU, ~3s on CPU) |
| **Offline** | Yes |
| **Training needed** | None (zero-shot) |

**Why:** The lightweight variant of GLiNER that works on day one with zero training data. You pass a label list like `["MRP", "expiry_date", "FSSAI_number", "manufacturer_address", "net_quantity"]` and it extracts matching entities from ML Kit's OCR output immediately. 3x faster than full GLiNER (300M) on CPU, fits comfortably on 4GB VRAM. Same API — just change the model name in code.

**How:** A bi-directional transformer that jointly encodes the input text and your entity label descriptions. It scores every text span against every label using a matching layer, then outputs the highest-scoring spans as extracted entities. Truly zero-shot — add a new field name anytime without retraining.

**Pipeline with ML Kit:**
```
ML Kit OCR output:
  "Parle-G Gold Glucose Biscuits Net Wt 200g MRP ₹30 inclusive of all taxes
   Mfg by Parle Products Pvt Ltd Vile Parle Mumbai 400057 FSSAI 10012345678901"

→ GLiNER-small v2.5 with labels: ["MRP", "net_quantity", "manufacturer",
                                   "address", "FSSAI_number", "product_name"] →

  "Parle-G Gold Glucose Biscuits" → product_name (0.92)
  "200g"                          → net_quantity (0.97)
  "₹30"                          → MRP (0.99)
  "Parle Products Pvt Ltd"       → manufacturer (0.95)
  "Vile Parle Mumbai 400057"     → address (0.91)
  "10012345678901"               → FSSAI_number (0.98)
```

**Why GLiNER-small over full GLiNER:**

| Factor | GLiNER v2.5 (300M) | GLiNER-small v2.5 (90M) |
|--------|---------------------|--------------------------|
| VRAM needed | ~1.5GB | ~500MB |
| CPU inference | ~5 seconds | ~1.5 seconds |
| Accuracy | Highest | Slightly lower, sufficient for hackathon |
| Same zero-shot | Yes | Yes |
| Same API | Yes | Yes — just change model name |

---

### 5. IndicBERT v2 — Indian Language NER (Conditional Fallback)

| Stat | Value |
|------|-------|
| **Params** | 33M |
| **License** | MIT |
| **GPU** | No (CPU is fine) |
| **Offline** | Yes |
| **Languages** | 24 Indian |
| **Training needed** | Yes (~300-500 annotated examples) |

**Why:** If GLiNER-small's recall drops on real Hindi-English mixed labels (e.g., "MRP ₹45 sabhi karon sahit" or Tamil-English mixed text), IndicBERT is the fallback. Pre-trained on 27 billion tokens of Indian language corpus — nothing else comes close for Indian NER.

**How:** BERT architecture pre-trained on IndicCorp v2 (24 languages). Fine-tune on your annotated Indian product label NER dataset. Tags each token as BRAND_NAME, GENERIC_NAME, MRP, ADDRESS, FSSAI_NUMBER, DATE, etc.

**When to activate:** Only build the fine-tuning pipeline if you test GLiNER-small on 50+ real Indian labels and find entity recall genuinely drops below 80%. Don't build it speculatively — it costs real engineering time.

---

### 6. Grounding DINO 1.5 — Zero-Shot Symbol & Logo Detection

| Stat | Value |
|------|-------|
| **Params** | ~170M |
| **License** | Apache 2.0 |
| **GPU** | Yes (~2.5GB VRAM, fits RTX 3050) |
| **Offline** | Yes |
| **Training needed** | None (zero-shot) |

**Why:** Same zero-shot philosophy as GLiNER — but for visual detection instead of text. Describe what you want to find in plain text (`"FSSAI logo"`, `"green vegetarian dot"`) and it locates it in the image. No annotated training data needed. Want to detect a new symbol next week? Just add the text prompt. Zero retraining.

**How:** A vision-language model that jointly encodes the image (via a Swin Transformer backbone) and your text descriptions (via a BERT text encoder). A cross-modality fusion module aligns visual and text features. The decoder outputs bounding boxes for every region that matches your text prompts.

**How it works for your labels:**
```
Input image: Product label photo

Text prompts:
  "FSSAI logo" . "green vegetarian symbol" . "brown non-vegetarian symbol" .
  "ISI mark" . "barcode" . "recycling symbol" . "AGMARK logo" . "BIS hallmark" .
  "MRP sticker pasted over printed price"

→ Grounding DINO 1.5 →

Output:
  [FSSAI logo:        bbox(120,45,180,90),   confidence: 0.94]
  [Green veg symbol:  bbox(200,50,220,70),   confidence: 0.97]
  [Barcode:           bbox(300,400,450,450),  confidence: 0.99]
  [MRP sticker:       bbox(80,120,160,145),   confidence: 0.82]  ← tampering hint!
```

---

### 7. DocTR v0.9 — Font Size Measurement

| Stat | Value |
|------|-------|
| **Params** | ~30M |
| **License** | Apache 2.0 |
| **GPU** | No |
| **Offline** | Yes |

**Why:** Rule 7 requires minimum character heights (1mm–6mm depending on package area). ML Kit gives bounding boxes per text block/line, but DocTR gives per-character precision needed for accurate height measurement.

**How:** Outputs exact (x, y, width, height) bounding boxes for every detected character. Measure height in pixels, convert to mm using a reference dimension (barcode module width = 0.33mm standard, or known package size). Compare against Rule 7 PDP-area thresholds. Flag PASS / FAIL / INCONCLUSIVE.

---

### 8. PatchCore with EfficientNet-B0 — Tampering & Counterfeit Detection

| Stat | Value |
|------|-------|
| **Params** | 5M (backbone) |
| **License** | Apache 2.0 |
| **GPU** | No (runs on CPU at ~0.8s/image) |
| **Offline** | Yes |

**Why:** Complements Grounding DINO's text-prompted tampering detection with pixel-level anomaly detection. Uses EfficientNet-B0 (5M) instead of the standard WideResNet-50 (25M) — 5x lighter, runs comfortably on CPU without GPU. Still catches subtle visual differences (ink quality, color shift, print resolution) that text prompts can't describe.

**How:** Extracts patch-level features from genuine product images using the lightweight EfficientNet-B0 backbone. Stores features in a memory bank (coreset). At inference, compares new image patches against the memory bank using nearest-neighbour distance. High distance = anomaly. Outputs a per-pixel anomaly heatmap highlighting suspicious regions.

**Grounding DINO + PatchCore together for tampering:**
```
Grounding DINO:  "Is there a sticker pasted over the MRP?"    →  YES/NO (coarse check)
PatchCore:       "Does the MRP area look visually different     →  Anomaly score (fine check)
                  from genuine products?"                          + heatmap
```

**Why EfficientNet-B0 over WideResNet-50:**

| Factor | WideResNet-50 (25M) | EfficientNet-B0 (5M) |
|--------|---------------------|------------------------|
| Size | 25M params | 5M params |
| VRAM | ~1GB | ~200MB |
| CPU speed | ~3s per image | ~0.8s per image |
| Quality | SOTA on MVTec | Sufficient for sticker/overlay detection |
| Runs on CPU laptop | Slow | Comfortable |

---

### 9. Legal Reasoning LLM — Three-Mode Strategy

#### Mode 1 — Local Offline: Phi-4-mini 3.8B (Microsoft, MIT)

| Stat | Value |
|------|-------|
| **Params** | 3.8B |
| **License** | MIT |
| **GPU** | ~2.5GB VRAM (4-bit quantized, fits RTX 3050) |
| **Offline** | Yes |

**Why:** Fits on RTX 3050 (4GB VRAM) using 4-bit quantization via Ollama. Provides legal reasoning for edge cases without internet dependency. Safe for live demo — no cloud risk.

#### Mode 2 — Cloud Production: Google Gemini API (Free Tier)

| Stat | Value |
|------|-------|
| **Cost** | Free tier: 15 RPM, 1M tokens/day |
| **GPU** | None needed (cloud) |
| **Internet** | Required |

**Why:** Works on any laptop including CPU-only Ryzen 5. No GPU needed. Free tier is generous enough for hackathon demo and testing. Use for production requests where internet is available.

#### Mode 3 — Main SIH Round: Gemma 3 27B (Google, Gemma License)

| Stat | Value |
|------|-------|
| **Params** | 27B |
| **License** | Gemma (free) |
| **GPU** | 16GB+ VRAM (GCP with SIH credits) |

**Why:** Strongest reasoning for complex legal edge cases. GCP free credits remove the hardware constraint. Google-made model at a Google-hosted hackathon.

**LLM auto-selection logic:**
```
if GPU available and offline mode:
    use Phi-4-mini 3.8B (local via Ollama)
elif internet available:
    use Gemini API (free tier, cloud)
else:
    skip LLM reasoning, show rule-engine result only
    queue edge case for LLM analysis when connectivity returns
```

**How (all modes):** Use with RAG (LangChain + ChromaDB). The 3 legal PDFs are chunked, embedded, and stored in a vector database. When the rule engine encounters an ambiguous case, the system retrieves the relevant legal section, feeds it to whichever LLM is available, and generates a plain-language explanation with rule citation.

---

### 10. Leaflet.js v1.9 + OpenStreetMap — GIS Mapping

| Stat | Value |
|------|-------|
| **Size** | ~40KB JS library |
| **License** | BSD-2 |
| **Cost** | Free (no API key) |

**Why:** Government dashboards need geographic violation data. Leaflet + OSM is the only fully free, no-API-key mapping solution that's production-ready.

**How:** JavaScript library renders interactive tile maps in the browser. Plot inspection markers with lat/lng from device GPS. Add heatmap.js plugin for violation density visualization. Click any marker for a popup with inspection details.

---

## Full Pipeline — How All Models Connect

```
                    USER SCANS PRODUCT
                           |
                           v
                   ┌──────────────┐
                   │  TOPIQ v0.1  │  Image Quality Check (10M, CPU)
                   └──────┬───────┘
                          | PASS
                          v
                  ┌───────────────┐
                  │ Google ML Kit │  Read ALL text + bounding boxes
                  │ v2 (on-device)│  Hindi + English (100ms, offline)
                  └───────┬───────┘
                          |
            ┌─────────────┼─────────────┐
            v                           v
   ┌────────────────┐           ┌───────────────┐
   │ ML Kit Bbox +  │           │ GLiNER-small  │
   │ Python Spatial │           │ v2.5 (90M)    │
   │ Clustering     │           │ Zero-shot NER │
   │ (0 extra model)│           │               │
   └───────┬────────┘           └──────┬────────┘
           └────────────┬──────────────┘
                        v
               ┌─────────────────┐
               │Grounding DINO   │  Detect symbols & logos
               │1.5 (170M)      │  Zero-shot, text-prompted
               └───────┬─────────┘
                       v
               ┌─────────────────┐
               │  DocTR v0.9     │  Measure font sizes (30M, CPU)
               │  (Font check)   │
               └───────┬─────────┘
                       v
               ┌─────────────────┐
               │ RULE ENGINE     │  Check 15 mandatory fields
               │ (Python)        │  Dates, units, MRP format
               └───────┬─────────┘
                       |
            ┌──────────┼──────────┐
            v                     v
   ┌────────────────┐    ┌────────────────────┐
   │ PatchCore      │    │ Phi-4-mini 3.8B    │
   │ EfficientNet-B0│    │ or Gemini API      │
   │ (5M, CPU)      │    │ or Gemma 3 27B     │
   │ Tamper check   │    │ Legal reasoning    │
   └───────┬────────┘    └───────┬────────────┘
           └──────────┬──────────┘
                      v
             ┌────────────────┐
             │ GREEN / YELLOW │
             │ / RED VERDICT  │
             │ + BSA Evidence │
             │ + PDF Report   │
             └───────┬────────┘
                     v
             ┌────────────────┐
             │ Leaflet.js map │  Violation heatmaps
             └────────────────┘
```

---

## Final Summary Table

| # | Task | Model | Params | License | GPU | Training | Status |
|---|------|-------|--------|---------|-----|----------|--------|
| 1 | Image Quality | TOPIQ v0.1 | 10M | BSD | No | None | Always on |
| 2 | OCR | Google ML Kit v2 | On-device | Free | No | None | Always on |
| 3 | Layout | ML Kit Bbox + Python Clustering | 0 extra | Free | No | None | Always on |
| 4 | NER (Text) | GLiNER-small v2.5 | 90M | Apache 2.0 | Optional | **None (zero-shot)** | Primary |
| 5 | Indian NER | IndicBERT v2 | 33M | MIT | No | Fine-tune | Fallback only |
| 6 | Symbols | Grounding DINO 1.5 | 170M | Apache 2.0 | Yes | **None (zero-shot)** | Always on |
| 7 | Font Size | DocTR v0.9 | 30M | Apache 2.0 | No | None | Always on |
| 8 | Tampering | PatchCore (EfficientNet-B0) | 5M | Apache 2.0 | No | Genuine imgs | Always on |
| 9a | LLM (Local) | Phi-4-mini 3.8B | 3.8B | MIT | 2.5GB | None (RAG) | Offline demo |
| 9b | LLM (Cloud) | Gemini API | Cloud | Free | No | None (RAG) | Production |
| 9c | LLM (SIH) | Gemma 3 27B | 27B | Gemma | 16GB (GCP) | None (RAG) | Main SIH |
| 10 | GIS | Leaflet.js v1.9 | 40KB | BSD-2 | No | None | Always on |

> **Zero-shot count: 7 out of 11 models need NO training data at all.**
> All models are free. No paid API required.
> Every model fits on RTX 3050 (4GB VRAM) — load sequentially for GPU models.
> 8 models run on CPU-only laptop without any GPU.

---

## Hardware Compatibility

| # | Model | RTX 3050 (4GB) | Ryzen 5 (CPU only) |
|---|-------|----------------|---------------------|
| 1 | TOPIQ v0.1 | ✅ | ✅ |
| 2 | Google ML Kit | ✅ (phone) | ✅ (phone) |
| 3 | ML Kit + Clustering | ✅ | ✅ |
| 4 | GLiNER-small v2.5 | ✅ (500MB VRAM) | ✅ (~3s CPU) |
| 5 | IndicBERT v2 | ✅ | ✅ (CPU fine) |
| 6 | Grounding DINO 1.5 | ✅ (2.5GB VRAM) | ⚠️ Slow on CPU |
| 7 | DocTR v0.9 | ✅ | ✅ (CPU fine) |
| 8 | PatchCore (Eff-B0) | ✅ | ✅ (0.8s CPU) |
| 9a | Phi-4-mini 3.8B | ✅ (2.5GB VRAM) | ❌ Use Gemini API |
| 9b | Gemini API | ✅ | ✅ |
| 10 | Leaflet.js | ✅ | ✅ |

---

*Prepared for SIH 26034 — LabelGuard AI | September 2026*
