# PhotoRoom + Vendoo Automation

**AI-powered product image processing and listing automation for e-commerce resellers.**

## Overview

This application automates the complete product listing workflow:

1. **User gives one instruction** (natural language)
2. **AI interprets** the instruction
3. **Image processing** — PhotoRoom removes backgrounds / enhances images
4. **Listing generation** — AI generates title, description, tags, category
5. **Vendoo integration** — Creates / imports listing
6. **Cross-listing** — Distributes across marketplaces
7. **Verification** — Confirms everything completed

## Current Status

**Phase A — Build Everything (Mock Mode)**

The application is being built with mock implementations for all external services.
Real API credentials will be integrated in Phase B.

## Quick Start

### Prerequisites

- Python 3.11+
- pip

### Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd Photoroom-vendoo-Automation

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your settings (mock mode works without real keys)

# 5. Run the application
python -m app.main

# 6. Run tests
pytest
```

## Project Structure

```
├── app/
│   ├── main.py              # Application entry point
│   ├── config/              # Settings and constants
│   ├── logging/             # Structured logging
│   ├── ui/                  # Desktop UI (PySide6)
│   ├── ai/                  # AI command interpretation
│   ├── workflow/            # Workflow orchestration
│   ├── images/              # Image validation & processing
│   ├── photoroom/           # PhotoRoom API client
│   ├── vendoo/              # Vendoo connector
│   ├── listings/            # Listing data models
│   ├── database/            # SQLite job tracking
│   └── storage/             # File management
├── tests/                   # Test suite
├── data/                    # Runtime data (db, output)
├── .env.example             # Environment template
├── requirements.txt         # Dependencies
└── pyproject.toml           # Project configuration
```

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.13 |
| HTTP | httpx |
| Images | Pillow |
| Database | SQLite |
| Desktop UI | PySide6 |
| Configuration | python-dotenv |
| Validation | Pydantic |
| Testing | pytest |
| Packaging | PyInstaller |

## Configuration

Copy `.env.example` to `.env` and configure:

- `APP_MODE` — `mock` (default) or `production`
- `PHOTOROOM_API_KEY` — Your PhotoRoom API key (provided later)
- `LLM_PROVIDER` — `mock`, `openai`, or `google`
- `LOG_LEVEL` — `DEBUG`, `INFO`, `WARNING`, `ERROR`

**Never commit `.env` to version control.**

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=app

# Run the application
python -m app.main
```

## Security

- API keys are loaded from environment variables only
- `.env` is gitignored
- `repr()` never exposes secrets
- Logs never contain credentials

## License

MIT
