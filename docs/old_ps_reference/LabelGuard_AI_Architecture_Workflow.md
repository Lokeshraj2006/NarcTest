# LabelGuard AI — Architecture & Workflow
### SIH 26034 | Team Reference Document

---

## 1. Overview

LabelGuard AI is an on-device / edge AI pipeline that scans a product package photo and checks it against India's Legal Metrology labeling requirements — MRP, net quantity, mfg/expiry dates, FSSAI number, manufacturer address, minimum font size, and tampering — returning a green/yellow/red verdict with cited evidence.

---

## 2. System Architecture

The system is organized into three layers.

```
┌──────────────────────────────────────────────┐
│              LabelGuard AI system              │
│                (SIH 26034 pipeline)             │
│                                                  │
│  ┌────────────────────────────────────────┐    │
│  │              Client app                 │    │
│  │   Capture photo, on-device quality      │    │
│  │   check (rejects blurry/dark shots)     │    │
│  └────────────────────────────────────────┘    │
│                                                  │
│  ┌────────────────────────────────────────┐    │
│  │            AI model layer               │    │
│  │  OCR • Layout • Field extraction • NER  │    │
│  │  Symbol detection • Font measurement    │    │
│  │  Tamper detection • Legal-reasoning LLM │    │
│  └────────────────────────────────────────┘    │
│                                                  │
│  ┌────────────────────────────────────────┐    │
│  │        Compliance & output layer        │    │
│  │   Rule engine → verdict → PDF report    │    │
│  │   → GIS violation map                   │    │
│  └────────────────────────────────────────┘    │
│                                                  │
└──────────────────────────────────────────────┘
        ▲                              │
   Package photo              PDF report / Violation map
```

### Layer 1 — Client app
Runs on the scanning device (phone/tablet). Captures the package photo and runs a lightweight on-device quality check before anything goes to the model layer — this avoids wasting compute on unusable images.

| Component | Model | Job |
|---|---|---|
| Image quality check | TOPIQ v0.1 | Scores blur/lighting (0–1); prompts "hold steady" or "too blurry" before proceeding |

### Layer 2 — AI model layer
Does all the reading, extracting, and reasoning. Runs as backend services (edge server or cloud), fed the captured image.

| Task | Model | Role |
|---|---|---|
| OCR | PaddleOCR v4 | Reads all text on the label (12+ Indian languages) |
| Layout analysis | PP-DocLayout_plus-L / PP-DocLayoutV2 | Locates MRP zone, ingredients list, manufacturer block, nutrition table, barcode area (fine-tuned on package photos) |
| Field extraction | Donut v1 | Fast OCR-free image → JSON field extraction |
| Indian-language NER | IndicBERT v2 | Deep understanding of code-mixed Hindi-English text; classifies MRP, dates, address, FSSAI number |
| Symbol/logo detection | RT-DETR v2 | Detects veg/non-veg mark, FSSAI logo, ISI mark, barcode |
| Font size measurement | DocTR v0.9 | Measures character height in mm for Rule 7 compliance |
| Tamper detection | PatchCore v1.0 | Flags MRP overprinting, stickers, reprints as visual anomalies |
| Legal reasoning | Gemma 3 27B (RAG over Legal Metrology Rules) | Explains edge cases in plain language with rule citations |
| Multimodal fallback | Qwen 2.5 VL 7B | Cross-checks the pipeline's output when confidence is low |

### Layer 3 — Compliance & output layer
Consumes the model layer's outputs, applies the rule engine, and produces the final artifacts.

| Component | Job |
|---|---|
| Rule engine (Python) | Checks all 15 mandatory Legal Metrology fields against extracted data |
| Verdict | Green (compliant) / Yellow (warning) / Red (violation) |
| PDF report | Evidence-backed compliance report per scan |
| GIS dashboard | Leaflet.js + OpenStreetMap — plots inspection locations and violation heatmaps |

---

## 3. End-to-End Workflow

1. **Capture & quality check** — camera photo is scored by TOPIQ; poor-quality shots are rejected before processing.
2. **Text & layout extraction** — PaddleOCR reads all text; PP-DocLayout, Donut, and IndicBERT run in parallel to locate label zones, extract structured fields, and deeply parse Indian-language/code-mixed text.
3. **Symbol & font checks** — RT-DETR detects mandatory symbols and logos; DocTR measures character heights against the Rule 7 minimum.
4. **Rule engine** — cross-checks all extracted fields and measurements against the 15 mandatory Legal Metrology requirements.
5. **Tamper & legal reasoning** — PatchCore flags visual tampering (e.g. MRP overprinting); Gemma 3 27B (RAG over the Legal Metrology Rules PDFs) reasons through any ambiguous edge cases with rule citations.
6. **Compliance verdict** — the rule engine's checks plus the tamper/legal reasoning results are merged into a green/yellow/red verdict.
7. **Report & dashboard** — a PDF evidence report is generated per scan, and the violation (if any) is plotted on the GIS violation-heatmap dashboard.

---

## 4. Demo Script Suggestion

Scan three prepared samples live:
- **Compliant product** — verdict: green.
- **Missing/incomplete field** (e.g. no FSSAI number) — verdict: red, with the specific missing field cited.
- **Tampered MRP sticker** — verdict: red, flagged by PatchCore's anomaly score with the region highlighted.

This demonstrates detection breadth (missing-data violations vs. physical tampering) in under a minute.

---

*Prepared for SIH 26034 — LabelGuard AI team*
