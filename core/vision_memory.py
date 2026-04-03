"""
◑ MiMi Nox – Vision Memory System (HITL)
core/vision_memory.py

Speichert und lädt visuelle Button-Zustände (Crops) in ChromaDB, 
damit der Llama Vision-Agent beim nächsten Aufruf Referenzmaterial erhält.
"""
from __future__ import annotations

import chromadb
import uuid
from pathlib import Path

DEFAULT_CHROMA_PATH = Path.home() / ".mimi-nox" / "memory" / "chroma_db"

def _get_collection():
    """Holt oder erstellt die ChromaDB Collection für UI-Visuals."""
    client = chromadb.PersistentClient(path=str(DEFAULT_CHROMA_PATH))
    return client.get_or_create_collection("vision_rules")

def save_vision_rule(target_description: str, base64_crop: str, x: int, y: int) -> None:
    """
    Speichert eine gelerne UI-Regel in der VectorDB.
    """
    collection = _get_collection()
    doc_id = str(uuid.uuid4())
    doc = f"Aussehen und Position für {target_description} im aktuellen Kontext."
    
    metadata = {
        "base64_crop": base64_crop,
        "last_known_x": x,
        "last_known_y": y,
        "raw_target": target_description
    }
    
    collection.add(
        documents=[doc],
        metadatas=[metadata],
        ids=[doc_id]
    )

def find_vision_rule(target_description: str) -> dict | None:
    """
    Sucht nach einem existierenden Referenz-Bild (Crop) in ChromaDB.
    Returniert das Metadata-Dictionary, wenn vorhanden.
    """
    try:
        collection = _get_collection()
        res = collection.query(
            query_texts=[f"Aussehen und Position für {target_description} im aktuellen Kontext."],
            n_results=1
        )
        
        # Check if we got a document result
        if not res or not res.get("documents") or not res["documents"][0]:
            return None
            
        distances = res.get("distances", [[float('inf')]])
        
        # L2 Distance Check: If it's too high, it might be an unrelated match
        if distances[0][0] > 1.2:  
            return None
            
        return res["metadatas"][0][0]
    except Exception as e:
        import logging
        logging.error(f"Fehler bei Vision-Memory Abfrage: {e}")
        return None
