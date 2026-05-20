"""
storage.py
----------
Mind map persistence via Supabase — scoped by user_id.

Table: mindmaps (see schema.sql)
  id, user_id, subject, source_file, created_at,
  theme_count, lecture_count, has_warnings, schema_json
"""

import streamlit as st
from db import get_supabase


# ── Core operations ───────────────────────────────────────────────────────────

def save_map(schema: dict, user_id: int) -> str:
    """
    Persist a mind map schema to Supabase.
    Returns map_id.
    """
    map_id = schema.get("id")
    if not map_id:
        raise ValueError("Schema missing 'id' field.")

    supabase = get_supabase()

    row = {
        "id":            map_id,
        "user_id":       user_id,
        "subject":       schema.get("subject", "Unknown Subject"),
        "source_file":   schema.get("source_file", ""),
        "theme_count":   len(schema.get("themes", [])),
        "lecture_count": len(schema.get("lectures", [])),
        "has_warnings":  len(schema.get("warnings", [])) > 0,
        "schema_json":   schema,
    }

    # Upsert — handles re-generation of same map
    supabase.table("mindmaps").upsert(row).execute()
    return map_id


def load_map(map_id: str, user_id: int) -> dict:
    """
    Load a mind map schema by ID — scoped to user_id.
    Raises FileNotFoundError if not found or belongs to another user.
    """
    supabase = get_supabase()
    result = supabase.table("mindmaps") \
        .select("schema_json") \
        .eq("id", map_id) \
        .eq("user_id", user_id) \
        .execute()

    if not result.data:
        raise FileNotFoundError(
            f"Map '{map_id}' not found or you do not have access."
        )

    return result.data[0]["schema_json"]


def list_maps(user_id: int) -> list[dict]:
    """
    Return all maps for a user, newest first.
    Each entry: id, subject, source_file, created_at,
                theme_count, lecture_count, has_warnings
    """
    supabase = get_supabase()
    result = supabase.table("mindmaps") \
        .select("id, subject, source_file, created_at, theme_count, lecture_count, has_warnings") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .execute()

    return result.data or []


def delete_map(map_id: str, user_id: int) -> bool:
    """
    Delete a map — scoped to user_id so users can only delete their own.
    Returns True if deleted.
    """
    supabase = get_supabase()
    result = supabase.table("mindmaps") \
        .delete() \
        .eq("id", map_id) \
        .eq("user_id", user_id) \
        .execute()

    return len(result.data) > 0


def map_exists(map_id: str, user_id: int) -> bool:
    """Check if a map exists for this user."""
    supabase = get_supabase()
    result = supabase.table("mindmaps") \
        .select("id") \
        .eq("id", map_id) \
        .eq("user_id", user_id) \
        .execute()
    return len(result.data) > 0
