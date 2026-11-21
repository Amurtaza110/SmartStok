"""
ai_assistant/services/semantic_search.py
==========================================
Semantic product search using Sentence-Transformers with keyword fallback.
Allows natural language queries like "fever medicine" → Paracetamol.

Model: all-MiniLM-L6-v2 (runs offline if installed).
Embeddings are pre-computed and stored in Product.embedding_json.
Falls back cleanly to Django Q-lookup when sentence-transformers is not installed.
"""

import logging
import math
from django.db.models import Q
from inventory.models import Product

logger = logging.getLogger(__name__)

_model = None
_model_attempted = False


def get_model():
    """Load (and cache) the sentence transformer model if available."""
    global _model, _model_attempted
    if _model_attempted:
        return _model

    _model_attempted = True
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("SentenceTransformer model loaded successfully.")
    except Exception as exc:
        logger.info(f"SentenceTransformer not available ({exc}); using keyword search fallback.")
        _model = None
    return _model


def cosine_similarity(vec_a, vec_b):
    """Compute cosine similarity between two vectors."""
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def embed_text(text):
    """
    Encode a text string to a vector embedding.
    Returns list of floats or None on failure.
    """
    model = get_model()
    if model is None or not text:
        return None
    try:
        embedding = model.encode(text)
        if hasattr(embedding, 'tolist'):
            return embedding.tolist()
        return list(embedding)
    except Exception as exc:
        logger.warning(f"embed_text error: {exc}")
        return None


def embed_product(product):
    """
    Generate and save embedding for a single product.
    Returns True on success.
    """
    vector = embed_text(product.get_searchable_text())
    if vector:
        product.set_embedding(vector)
        product.save(update_fields=['embedding_json'])
        return True
    return False


def reindex_all_products():
    """
    Re-generate embeddings for ALL active products.
    Returns count of successfully indexed products.
    """
    model = get_model()
    products = Product.objects.filter(is_active=True)
    if model is None:
        return products.count()

    count = 0
    for product in products:
        if embed_product(product):
            count += 1
    return count


def keyword_fallback(query, top_k=10):
    """Simple keyword fallback when semantic search is unavailable or returns no hits."""
    terms = query.strip().split()
    if not terms:
        return []

    q_filter = Q()
    for term in terms:
        q_filter |= (
            Q(name__icontains=term) |
            Q(generic_name__icontains=term) |
            Q(description__icontains=term) |
            Q(tags__icontains=term) |
            Q(category__name__icontains=term)
        )

    results = list(
        Product.objects.filter(is_active=True)
        .filter(q_filter)
        .select_related('category')
        .distinct()[:top_k]
    )

    for p in results:
        p.similarity_score = None

    return results


def semantic_search(query, top_k=10, threshold=0.2):
    """
    Search products by semantic meaning with automatic fallback.

    Args:
        query:     Natural language query (e.g. "fever medicine")
        top_k:     Max number of results to return
        threshold: Minimum similarity score (0.0 - 1.0)

    Returns:
        List of Product objects sorted by relevance.
    """
    query = (query or '').strip()
    if not query:
        return []

    model = get_model()
    if model is None:
        return keyword_fallback(query, top_k=top_k)

    query_vec = embed_text(query)
    if not query_vec:
        return keyword_fallback(query, top_k=top_k)

    active_products = list(Product.objects.filter(is_active=True).select_related('category'))
    scored = []

    for product in active_products:
        embedding = product.get_embedding()
        if embedding:
            sim = cosine_similarity(query_vec, embedding)
            if sim >= threshold:
                product.similarity_score = round(sim * 100, 1)
                scored.append((sim, product))

    if not scored:
        return keyword_fallback(query, top_k=top_k)

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:top_k]]
