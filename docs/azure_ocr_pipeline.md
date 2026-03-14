# Azure OCR Pipeline

This repo now includes a local CLI for pushing PDFs to Azure AI Document Intelligence and writing the results back into `tmp/pdfs/azure_ocr/`.

## Why this path

- Use `Azure AI Document Intelligence` first.
- Do not start with a GPU VM.
- Do not start with Azure AI Foundry OCR models.

Reasoning:

- Our corpus is mostly normal PDFs with a few bad OCR cases.
- A local script plus a managed OCR API is the fastest way to get usable text into the project.
- Microsoft documents `500 pages/month` on the `S0` tier and up to `2,000 pages` / `500 MB` per paid PDF request.
- The `F0` tier only processes the first two pages of a PDF, so it is only useful for smoke tests.
- Azure AI Foundry serverless deployments require a subscription with a valid payment method, so they are not the best first move for this repo.

## Credits to plan around

Validated against Microsoft docs on `2026-03-13`.

- `Azure for Students`: `$100` credit, usable within `12 months`.
- Standard Azure free account: `$200` credit for `30 days`.

Treat them as separate subscription budgets unless the Azure portal explicitly shows otherwise.

## Azure resource setup

Create one `Azure AI Document Intelligence` resource:

1. Resource type: `Azure AI Document Intelligence`
2. Pricing tier: `S0`
3. Region: choose one close to you with the service available
4. Add a budget and alert before you run large jobs

Then export these variables locally:

```bash
export AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="https://YOUR_RESOURCE.cognitiveservices.azure.com"
export AZURE_DOCUMENT_INTELLIGENCE_KEY="YOUR_KEY"
```

## Script

Path:

```text
scripts/azure_docint_ocr.py
```

Properties:

- Python stdlib only
- uploads document bytes directly to Azure
- polls until the job completes
- writes raw JSON plus normalized text outputs per file

Output layout:

```text
tmp/pdfs/azure_ocr/<document-slug>/
  request.json
  result.json
  content.md or content.txt
  plain_text.txt
```

## Recommended workflow for this project

Start with the PDFs that currently extract badly:

- `docs/Dnd-ebooks/628552380-Xanathar-s-Guide-to-Everything.pdf`
- `docs/Dnd-ebooks/ilide.info-d-d-starter-set-dragons-of-stormwreck-isle-rulebook-pr_1009aa10aa1536227e9d7bec29f01d02.pdf`
- `docs/Dnd-ebooks/ilide.info-monster-manual-expanded-bestiary-pr_e3c70b3e844e7c21b69b9247facafefa.pdf`

Use `prebuilt-layout` first because we care about headings and structure:

```bash
python3 scripts/azure_docint_ocr.py \
  --model prebuilt-layout \
  docs/Dnd-ebooks/628552380-Xanathar-s-Guide-to-Everything.pdf
```

If you only want plain OCR text:

```bash
python3 scripts/azure_docint_ocr.py \
  --model prebuilt-read \
  --output-format text \
  docs/Dnd-ebooks/628552380-Xanathar-s-Guide-to-Everything.pdf
```

If a large PDF needs chunking:

```bash
python3 scripts/azure_docint_ocr.py \
  --model prebuilt-layout \
  --pages "1-30" \
  "docs/Dnd-ebooks/Player's Handbook.pdf"
```

## Suggested hybrid strategy

- Keep using `pdftotext` for the books that already extract cleanly.
- Use Azure OCR only on the bad books or page ranges.
- Digest the Azure output into project notes after OCR lands locally.

That gives us a cheaper and faster ingestion path than OCRing the entire library up front.
