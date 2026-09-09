"""RAG engine: ChromaDB vector store with sentence-transformers embeddings."""
import chromadb
from sentence_transformers import SentenceTransformer
from chatbot.kb_loader import Chunk

_model = None


def _get_model():
    """Lazy-load the multilingual embedding model."""
    global _model
    if _model is None:
        _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _model


def build_index(chunks: list[Chunk], persist_dir: str) -> chromadb.Collection:
    """Build a Chroma collection from chunks. Idempotent (upserts by chunk_id)."""
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_or_create_collection(
        name="portfolio_kb",
        metadata={"hnsw:space": "cosine"},
    )
    if not chunks:
        return collection

    model = _get_model()
    texts = [c.text for c in chunks]
    ids = [c.chunk_id for c in chunks]
    embeddings = model.encode(texts).tolist()

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=[{"source": c.source, "heading": c.heading} for c in chunks],
    )
    return collection


def retrieve(collection: chromadb.Collection, query: str, k: int = 4) -> list[str]:
    """Retrieve top-k document texts for a query. Returns [] on empty query."""
    if not query or not query.strip():
        return []
    model = _get_model()
    query_embedding = model.encode([query]).tolist()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(k, collection.count()),
    )
    return results["documents"][0] if results and results["documents"] else []
