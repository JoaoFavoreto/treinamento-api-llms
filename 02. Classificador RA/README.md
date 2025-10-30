# Mercedes-Benz Complaint Classification Pipeline

Automated complaint analysis system for Mercedes-Benz Cars & Vans Brasil on Reclame Aqui. This pipeline collects public complaints, discovers recurring themes using OpenAI API, and classifies complaints into business-actionable categories.

## Overview

This system implements a 4-phase approach:

1. **Phase 1: Data Collection** - Scrape complaints from Reclame Aqui with PII removal
2. **Phase 2: Theme Discovery** - Generate proposed taxonomy using OpenAI API
3. **Phase 3: Human Curation** - Review and finalize taxonomy (manual step)
4. **Phase 4: Classification** - Classify all complaints using curated taxonomy

## Setup

### Prerequisites

- Python 3.8+
- OpenAI API key
- Google Chrome (for Selenium fallback)

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Edit `.env` and add your OpenAI API key:
```
OPENAI_API_KEY=sk-your-key-here
```

## ⚠️ Important: Web Scraping Notes

Reclame Aqui has anti-bot protection (403 Forbidden errors). The scraper includes two methods:

1. **Requests library** (fast, but may be blocked)
2. **Selenium** (slower, bypasses anti-bot protection)

If the requests method fails, the scraper automatically tries Selenium. Selenium will download ChromeDriver automatically on first run.

**Alternative:** For production use, consider:
- Using Reclame Aqui's official API (if available)
- Purchasing complaint data from data providers
- Manual complaint export from Reclame Aqui dashboard
- Using the provided sample data structure to test Phases 2-4

## Usage

### Quick Start with Sample Data

If you want to test Phases 2-4 without scraping:

```bash
# Use provided sample complaints
python use_sample_data.py

# Then run Phase 2
python main.py 2
```

### Run Individual Phases

```bash
# Phase 1: Scrape complaints (requires Selenium if blocked)
python main.py 1

# Phase 2: Discover themes
python main.py 2

# Phase 4: Classify complaints (after Phase 3 curation)
python main.py 4
```

### Run All Phases

```bash
python main.py all
```

### Run Directly

```bash
# Individual phase scripts
python scraper.py
python theme_discovery.py
python classifier.py
```

## Phase Details

### Phase 1: Data Collection

**Script:** `scraper.py`

Collects complaints from Mercedes-Benz page on Reclame Aqui:
- Extracts: title, description, date, status, final evaluation
- Removes PII: names, CPF, phone, email, license plates, chassis numbers
- Assigns unique complaint IDs

**Output:** `data/complaints_raw.json`

### Phase 2: Theme Discovery

**Script:** `theme_discovery.py`

Uses OpenAI API to analyze complaint sample and discover themes:
- Samples 200 complaints (configurable)
- Generates 6-10 business-friendly categories
- Provides descriptions and paraphrased examples

**Output:** `output/proposed_taxonomy.json`

### Agent Configuration (YAML)

Prompt and parameter settings for the OpenAI calls are now stored in `agents/` as YAML files:

```
agents/
├── complaint_classifier.yaml   # System + templates for Phase 4
└── theme_discovery.yaml        # System + template for Phase 2
```

You can edit these files to tweak system prompts, temperature, token limits, or the template placeholders used when formatting the requests. Changes apply automatically to the notebook and CLI commands on the next run.

### Phase 3: Human Curation

**Manual step** - Review and edit taxonomy:

1. Open `output/proposed_taxonomy.json`
2. Merge, rename, or refine categories
3. Save final taxonomy as `output/curated_taxonomy.json`

Example curated taxonomy format:
```json
[
  {
    "category_name": "Warranty Coverage Refused",
    "category_description": "Cases where warranty claim is denied..."
  },
  {
    "category_name": "Vehicle Immobilized Waiting Parts",
    "category_description": "Vehicle stuck at service due to part delays..."
  }
]
```

### Phase 4: Classification

**Script:** `classifier.py`

Classifies all complaints using curated taxonomy:
- Uses OpenAI API with frozen taxonomy
- Assigns exactly ONE category per complaint
- Generates distribution statistics

**Output:** `output/classification_results.json`

## Configuration

Edit `config.py` to customize:

```python
OPENAI_MODEL = "gpt-4o-mini"           # OpenAI model
SAMPLE_SIZE_FOR_DISCOVERY = 200        # Sample size for Phase 2
MIN_CATEGORIES = 6                     # Min categories
MAX_CATEGORIES = 10                    # Max categories
MAX_PAGES = None                       # Limit scraping pages (None = all)
REQUEST_DELAY = 2                      # Delay between requests (seconds)
```

Or use environment variables in `.env`:

```bash
OPENAI_API_KEY=sk-your-key-here

# Show API usage statistics (true/false)
SHOW_API_USAGE=true

# Show detailed call-by-call breakdown (true/false)
SHOW_API_USAGE_DETAILS=false
```

## OpenAI API Usage Tracking

The system automatically tracks OpenAI API usage including:
- Number of API calls
- Input/output tokens
- Estimated costs (USD)
- Execution time

**View usage after running phases:**
```bash
# Summary
python view_usage.py

# Detailed history
python view_usage.py --details
```

**Control display:**
- Set `SHOW_API_USAGE=true` in `.env` to see usage after each phase
- Set `SHOW_API_USAGE_DETAILS=true` to see call-by-call breakdown
- Usage is always logged to `output/openai_usage.json`

**Example output:**
```
OPENAI API USAGE - PHASE 2
Model: gpt-4o-mini
API Calls: 1
Input Tokens: 4,891
Output Tokens: 687
Total Tokens: 5,578
Estimated Cost: $0.0011 USD
```

## Project Structure

```
02. Classificador RA/
├── main.py                    # Main orchestrator
├── scraper.py                 # Phase 1: Data collection
├── theme_discovery.py         # Phase 2: Theme discovery
├── classifier.py              # Phase 4: Classification
├── usage_tracker.py           # OpenAI API usage tracking
├── view_usage.py              # View usage statistics
├── config.py                  # Configuration
├── requirements.txt           # Dependencies
├── .env                       # Environment variables (create from .env.example)
├── data/
│   └── complaints_raw.json    # Scraped complaints (Phase 1 output)
└── output/
    ├── proposed_taxonomy.json        # Proposed categories (Phase 2 output)
    ├── curated_taxonomy.json         # Final taxonomy (Phase 3 input)
    ├── classification_results.json   # Classifications (Phase 4 output)
    └── openai_usage.json             # API usage log (auto-generated)
```

## Privacy & Compliance

- **PII Removal:** All personal data is automatically redacted during scraping
- **No Data Storage:** Only anonymized complaint content is stored
- **Public Data:** Only publicly available complaints are collected

Redacted PII types:
- Names → `[NOME]`
- CPF → `[CPF]`
- Phone → `[TELEFONE]`
- Email → `[EMAIL]`
- License plates → `[PLACA]`
- Chassis numbers → `[CHASSI]`
- Protocol numbers → `[PROTOCOLO]`

## Key Principles

1. **Phase Separation:** Theme discovery (Phase 2) and classification (Phase 4) are separate
2. **Taxonomy Stability:** Once curated, taxonomy is frozen for classification
3. **Business Focus:** Categories represent customer pain points, not technical details
4. **Human Oversight:** Phase 3 ensures business-relevant categories

## Output Files

### complaints_raw.json
```json
[
  {
    "complaint_id": "COMPLAINT_00001",
    "complaint_title": "Title with [NOME] redacted",
    "complaint_text": "Full text with PII removed",
    "opened_at": "2024-01-15",
    "status": "Resolved",
    "public_link": "https://...",
    "final_consideration": "Customer feedback"
  }
]
```

### proposed_taxonomy.json
```json
{
  "sample_size": 200,
  "total_complaints": 1500,
  "status": "AWAITING_HUMAN_CURATION",
  "proposed_categories": [
    {
      "category_name": "Warranty Coverage Refused",
      "category_description": "...",
      "representative_examples": ["...", "...", "..."]
    }
  ]
}
```

### classification_results.json
```json
{
  "taxonomy_used": [...],
  "classification_results": [
    {
      "complaint_id": "COMPLAINT_00001",
      "assigned_category": "Warranty Coverage Refused"
    }
  ],
  "summary": {
    "total_complaints": 1500,
    "category_distribution": [
      {"category": "Warranty Coverage Refused", "count": 450, "percentage": 30.0}
    ]
  }
}
```

## Troubleshooting

**Error: OPENAI_API_KEY not found**
- Create `.env` file with your API key

**Error: Curated taxonomy not found**
- Complete Phase 3 by creating `output/curated_taxonomy.json`

**Error: Complaints file not found**
- Run Phase 1 first: `python main.py 1`

**Scraping issues**
- Check Reclame Aqui site structure hasn't changed
- Adjust `REQUEST_DELAY` if rate-limited
- Use `MAX_PAGES` to limit scraping during testing

## License

Internal use only - Mercedes-Benz CX analysis
