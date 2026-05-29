"""db — PostgreSQL helpers package. Re-exports all public symbols."""

from db.connection import get_pg_connection
from db.schema import init_db
from db.text_utils import (
    normalize_text,
    clean_string_list,
    is_english_text,
    sanitize_string_field,
    sanitize_string_list,
)
from db.embeddings import (
    get_offering_embedding,
    get_task_embedding,
    find_similar_offering,
)
from db.raw_data import save_raw_to_db
from db.offerings import (
    offering_content_hash,
    prepare_offering_for_storage,
    save_capability_records,
    save_extracted_to_db,
    fetch_capability_records,
    fetch_capability_records_for_offerings,
    fetch_all_offerings,
    fetch_relevant_offerings,
)
from db.recommendations import (
    fetch_cached_by_embedding,
    save_task_recommendations,
)
from db.pricing import (
    save_offering_pricing,
    fetch_pricing_for_offering,
    fetch_pricing_for_offerings,
    CONFIDENCE_CRAWLED,
    CONFIDENCE_LLM_INFERRED,
)

__all__ = [
    "get_pg_connection",
    "init_db",
    "normalize_text",
    "clean_string_list",
    "is_english_text",
    "sanitize_string_field",
    "sanitize_string_list",
    "get_offering_embedding",
    "get_task_embedding",
    "find_similar_offering",
    "save_raw_to_db",
    "offering_content_hash",
    "prepare_offering_for_storage",
    "save_capability_records",
    "save_extracted_to_db",
    "fetch_capability_records",
    "fetch_capability_records_for_offerings",
    "fetch_all_offerings",
    "fetch_relevant_offerings",
    "fetch_cached_by_embedding",
    "save_task_recommendations",
    "save_offering_pricing",
    "fetch_pricing_for_offering",
    "fetch_pricing_for_offerings",
    "CONFIDENCE_CRAWLED",
    "CONFIDENCE_LLM_INFERRED",
]
