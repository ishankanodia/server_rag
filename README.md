# Server RAG

A local desktop-ready RAG app for indexing files and asking questions over them with retrieval augmented generation.

## What It Does

- Browses local folders from the web UI.
- Indexes `.txt`, `.md`, `.pdf`, and common image files.
- Extracts PDF text with PyMuPDF.
- Extracts image text with Tesseract OCR.
- Stores embeddings in a local FAISS index.
- Answers questions with a configurable LLM provider.
- Can run as a developer server today and is scaffolded for Mac/Windows desktop packaging with Tauri.

## API Keys And Models

Do not ship your personal LLM key in public code. For a consumer desktop app, the cleanest options are:

- Ask advanced users to provide their own key through a private local config flow.
- Route requests through your hosted backend with authentication and usage limits.
- Use a local model runtime such as Ollama/llama.cpp for privacy-first offline mode.

The app supports:

- Groq
- OpenAI
- Anthropic Claude
- Google Gemini
- Any custom OpenAI-compatible provider with a `/chat/completions` endpoint

You can configure the LLM in two ways:

1. Environment variables or deployment secrets for API keys.
2. The in-app `LLM Settings` panel for choosing the provider/model already configured on the server.

In the desktop/local build, users can paste a provider key in `LLM Settings`, or you can preconfigure one in `.env`. Hosted public deployments should use server-side secrets instead of exposing shared keys in the UI.

## How Users Run It

There are three practical ways to ship this app:

1. Packaged desktop app: users download a Mac/Windows app, grant folder access, and ask questions. This best matches local-file RAG.
2. Hosted web app: users upload files to a server, then ask questions. A hosted website cannot directly browse local folders.
3. Local developer app: users clone/download the code, install dependencies, add a `.env`, and run `uvicorn` in a terminal.

For users who do not know about AI/API keys, use the packaged desktop app plus either a hosted backend or a local model mode.

## Option 1: Developer Setup From GitHub

Use this path for technical users who are comfortable with Terminal.

```bash
git clone https://github.com/your-username/server-rag.git
cd server-rag
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python server_launcher.py
```

Open:

```text
http://localhost:8001
```

Developers can either edit `.env` or paste an API key in `LLM Settings`.

For image OCR on macOS:

```bash
brew install tesseract
```

## Option 2: Desktop App For Normal Users

Use this path for non-technical users.

They should not clone the repo or run Terminal commands. They should download a finished app:

- macOS: `.dmg` or `.app`
- Windows: `.exe` or `.msi`

User flow:

1. Download and open the app.
2. Choose provider/model in `LLM Settings`.
3. Paste their API key once.
4. Browse local files/folders.
5. Index selected files.
6. Ask questions.

The API key is saved on their own computer in the local app config, not in the repo.

## Local Server Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and add your API key.

For image OCR, install the Tesseract system binary too:

```bash
brew install tesseract
```

Start the server:

```bash
python server_launcher.py
```

## Desktop App Development

This repo includes a Tauri desktop shell. In development, Tauri opens a native window and starts the Python backend locally.

Install desktop build prerequisites:

```bash
npm install
```

Install Rust from:

```text
https://rustup.rs
```

Run the desktop app in development:

```bash
npm run desktop:dev
```

If Rust is not installed, desktop commands will fail until `rustc` and `cargo` are available.

## Desktop Packaging For Mac And Windows

Desktop packaging has two layers:

1. Package the Python backend into a native executable with PyInstaller.
2. Bundle that executable inside the Tauri desktop app.

Install build dependencies:

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
npm install
```

Build the backend executable on the target OS:

```bash
pyinstaller server-rag-backend.spec
```

Then build the desktop app:

```bash
npm run desktop:build
```

Output locations:

- macOS app/bundles: `src-tauri/target/release/bundle/`
- Windows installers: `src-tauri/target/release/bundle/`

Build Mac artifacts on macOS and Windows artifacts on Windows. Cross-compiling desktop installers is possible but painful; CI with separate Mac and Windows runners is usually cleaner.

## Build With GitHub Actions

This repo includes `.github/workflows/desktop-build.yml`.

Push the repo to GitHub:

```bash
git add .
git commit -m "Prepare desktop RAG app"
git remote add origin https://github.com/your-username/server-rag.git
git push -u origin main
```

If the remote already exists, use:

```bash
git remote set-url origin https://github.com/your-username/server-rag.git
git push -u origin main
```

After pushing, build downloadable Mac and Windows artifacts from the GitHub Actions tab:

1. Push this repo to GitHub.
2. Open the repo on GitHub.
3. Go to `Actions`.
4. Select `Desktop Builds`.
5. Click `Run workflow`.
6. Download the generated artifacts after the workflow completes.

You can also create a tagged release build:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The workflow builds both:

- `macos-latest`
- `windows-latest`

## Environment Variables

Groq:

```bash
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=your_key
```

OpenAI:

```bash
LLM_PROVIDER=openai
LLM_MODEL=gpt-5-mini
OPENAI_API_KEY=your_key
```

Anthropic Claude:

```bash
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=your_key
```

Google Gemini:

```bash
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
GEMINI_API_KEY=your_key
```

Custom OpenAI-compatible provider:

```bash
LLM_PROVIDER=custom
LLM_MODEL=your_model
LLM_BASE_URL=https://your-provider.example/v1
LLM_API_KEY=your_key
```

## Deployment Notes

This app is safest as a single-user local desktop app because it can browse and index files visible to the app process.

Before deploying publicly:

- Add authentication.
- Restrict or remove `/browse` for server filesystem access.
- Do not commit `.env`.
- Do not commit `rag_data/`; it can contain private document text and local file paths.
- Prefer provider API keys in environment variables instead of asking public users to paste keys.

## Simple Hosting Options

### Render, Railway, Fly.io, or Similar

For a hosted web version, replace folder browsing with file upload. A hosted server cannot access a user's local folders.

Use this start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Set environment variables in the platform dashboard, for example:

```bash
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=your_key
```

Persistent indexing requires a persistent disk/volume mounted to the app directory or to `rag_data/`. Without persistent storage, the index may disappear on redeploy or restart.

### Docker

Create an image that installs Python dependencies and the `tesseract-ocr` system package, then run:

```bash
uvicorn main:app --host 0.0.0.0 --port 8001
```

Mount a volume for `rag_data/` if you want indexes to survive container restarts.

## Important Security Choice

If other people will use a hosted version, do not let random users browse your server filesystem. A production multi-user version should add accounts, per-user indexes, upload-based ingestion instead of server browsing, and rate limits.
