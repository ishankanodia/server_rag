from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import os
import json
import pickle

# PDF
import fitz  # PyMuPDF

# OCR for images
from PIL import Image
import pytesseract

import logging

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        try:
            _model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            logger.error("Failed to load embedding model: %s", e)
            raise RuntimeError(
                "Could not load the embedding model. Check your internet connection for first-time download."
            ) from e
    return _model

# Persistence paths
DATA_DIR = os.getenv("RAG_DATA_DIR", os.path.expanduser("~/.filewhisper/rag_data"))
INDEX_PATH = os.path.join(DATA_DIR, "index.faiss")
DOCS_PATH = os.path.join(DATA_DIR, "documents.pkl")
SOURCES_PATH = os.path.join(DATA_DIR, "sources.json")

os.makedirs(DATA_DIR, exist_ok=True)

# In-memory state
documents = []
doc_sources = []  # parallel list: one source path per chunk
sources = []      # unique list of ingested file paths
index = None


def _save():
    global index, documents, doc_sources, sources
    if index is not None:
        faiss.write_index(index, INDEX_PATH)
    with open(DOCS_PATH, "wb") as f:
        pickle.dump((documents, doc_sources), f)
    with open(SOURCES_PATH, "w") as f:
        json.dump(sources, f)


def _load():
    global index, documents, doc_sources, sources
    if os.path.exists(INDEX_PATH) and os.path.exists(DOCS_PATH):
        index = faiss.read_index(INDEX_PATH)
        with open(DOCS_PATH, "rb") as f:
            loaded = pickle.load(f)
            if isinstance(loaded, tuple):
                documents, doc_sources = loaded
            else:
                # backward compat: old format was just a list
                documents = loaded
                doc_sources = ["unknown"] * len(documents)
    if os.path.exists(SOURCES_PATH):
        with open(SOURCES_PATH, "r") as f:
            sources = json.load(f)


# Load on startup
_load()


def split_text(text, chunk_size=150):
    words = text.split()
    return [
        " ".join(words[i:i + chunk_size])
        for i in range(0, len(words), chunk_size)
        if words[i:i + chunk_size]
    ]


def extract_text_from_file(filepath: str) -> str:
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".txt" or ext == ".md":
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    elif ext == ".pdf":
        text = ""
        try:
            doc = fitz.open(filepath)
            reader = None
            
            def is_gibberish(txt: str) -> bool:
                cleaned_txt = txt.strip()
                if not cleaned_txt:
                    return True
                words = cleaned_txt.split()
                if not words:
                    return True
                gibberish_words = 0
                for w in words:
                    if w.isdigit():
                        continue
                    clean = w.strip(".,;:?!'\"()[]{}|•")
                    if not clean:
                        continue
                    if not clean.isalnum():
                        gibberish_words += 1
                        continue
                    # Check if it contains a weird mixed alphanumeric structure
                    has_letters = any(c.isalpha() for c in clean)
                    has_digits = any(c.isdigit() for c in clean)
                    if has_letters and has_digits:
                        if len(clean) != 10:  # Allow 10-char PAN numbers
                            gibberish_words += 1
                
                ratio_gibberish = gibberish_words / len(words)
                return ratio_gibberish > 0.15

            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                
                # Check if page text is empty or has a very low ratio of normal alphanumeric characters
                cleaned = page_text.strip()
                if len(cleaned) > 0:
                    alnum_count = sum(1 for c in cleaned if c.isalnum() or c.isspace())
                    ratio = alnum_count / len(cleaned)
                else:
                    ratio = 0
                
                # Fallback to EasyOCR if the text layer is too short, mostly garbage, or detected as gibberish
                if len(cleaned) < 60 or ratio < 0.65 or is_gibberish(page_text):
                    try:
                        if reader is None:
                            import easyocr
                            import logging
                            # Suppress excessive easyocr logs
                            logging.getLogger('easyocr').setLevel(logging.WARNING)
                            reader = easyocr.Reader(['en'], verbose=False)
                            
                        pix = page.get_pixmap(dpi=150)
                        img_data = pix.tobytes("png")
                        ocr_results = reader.readtext(img_data, detail=0)
                        ocr_page_text = " ".join(ocr_results)
                        if ocr_page_text.strip():
                            page_text = ocr_page_text
                    except Exception as ocr_err:
                        logger.warning(f"EasyOCR fallback failed on page {page_num} of {filepath}: {ocr_err}")
                
                text += page_text + "\n"
        except Exception as e:
            text = f"[Error reading PDF: {e}]"
        return text

    elif ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]:
        try:
            import easyocr
            import logging
            logging.getLogger('easyocr').setLevel(logging.WARNING)
            reader = easyocr.Reader(['en'], verbose=False)
            ocr_results = reader.readtext(filepath, detail=0)
            return " ".join(ocr_results)
        except Exception as e:
            return f"[Error reading image: {e}]"

    else:
        return ""


def add_chunks(chunks: list, source_path: str):
    global index, documents, doc_sources, sources

    if not chunks:
        return 0

    embeddings = _get_model().encode(chunks)
    dimension = embeddings.shape[1]

    if index is None:
        index = faiss.IndexFlatL2(dimension)

    index.add(np.array(embeddings))
    documents.extend(chunks)
    doc_sources.extend([source_path] * len(chunks))  # track source per chunk

    if source_path not in sources:
        sources.append(source_path)

    _save()
    return len(chunks)


def ingest_path(path: str) -> dict:
    """Ingest a file or entire folder recursively."""
    results = []

    SUPPORTED = {".txt", ".md", ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}

    if os.path.isfile(path):
        files = [path]
    elif os.path.isdir(path):
        files = []
        for root, _, fnames in os.walk(path):
            for fname in fnames:
                if os.path.splitext(fname)[1].lower() in SUPPORTED:
                    files.append(os.path.join(root, fname))
    else:
        return {"error": "Invalid path"}

    for filepath in files:
        if filepath in sources:
            results.append({"file": filepath, "status": "skipped", "chunks": 0, "reason": "already indexed"})
            continue
        text = extract_text_from_file(filepath)
        if not text.strip():
            results.append({"file": filepath, "status": "skipped", "chunks": 0})
            continue
        chunks = split_text(text)
        n = add_chunks(chunks, filepath)
        results.append({"file": filepath, "status": "indexed", "chunks": n})

    return {
        "status": "done",
        "files_processed": len(files),
        "details": results
    }


def retrieve(query: str, k: int = 5) -> list:
    """Returns list of (chunk_text, source_filepath) tuples."""
    global index, documents, doc_sources

    if index is None or len(documents) == 0:
        return []

    query_embedding = _get_model().encode([query])
    distances, indices = index.search(np.array(query_embedding), k)
    return [
        (documents[i], doc_sources[i])
        for i in indices[0] if i < len(documents)
    ]


def get_indexed_sources() -> list:
    return sources


def clear_index():
    global index, documents, doc_sources, sources
    index = None
    documents = []
    doc_sources = []
    sources = []
    for path in [INDEX_PATH, DOCS_PATH, SOURCES_PATH]:
        if os.path.exists(path):
            os.remove(path)
