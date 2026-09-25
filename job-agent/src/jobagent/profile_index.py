"""Chroma retrieval index over profile.json entries (roles, bullets, projects, skills).

Uses Chroma's bundled local embedding model (no extra API key -- Anthropic doesn't
offer an embeddings endpoint) so this works offline once the model is cached.
"""

import json
from pathlib import Path

from jobagent.config import PROFILE_DIR, ROOT

PROFILE_PATH = PROFILE_DIR / "profile.json"
CHROMA_DIR = ROOT / "data" / "chroma"
COLLECTION_NAME = "profile"


def _load_profile_entries(profile_path: Path | None = None) -> list[dict]:
    profile_path = profile_path or PROFILE_PATH
    if not profile_path.exists():
        raise FileNotFoundError(
            f"{profile_path} doesn't exist yet. Fill it in (see profile/profile.schema.json) "
            "before the index can be built."
        )
    with open(profile_path) as f:
        data = json.load(f)

    entries = []
    for role in data.get("roles", []):
        for bullet in role.get("bullets", []):
            entries.append(
                {"id": bullet["id"], "text": bullet["text"], "tags": bullet.get("tags", [])}
            )
    for project in data.get("projects", []):
        entries.append(
            {
                "id": project["id"],
                "text": f"{project['name']}: {project['description']}",
                "tags": project.get("tags", []),
            }
        )
    for skill in data.get("skills", []):
        entries.append(
            {"id": skill["id"], "text": skill["name"], "tags": [skill.get("category", "")]}
        )
    return entries


def _get_client(persist_dir: Path | None = None):
    import chromadb

    persist_dir = persist_dir or CHROMA_DIR
    persist_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(persist_dir))


def build_index(profile_path: Path | None = None, persist_dir: Path | None = None) -> int:
    """(Re)build the index from profile.json. Returns the number of entries indexed."""
    entries = _load_profile_entries(profile_path)
    client = _get_client(persist_dir)
    client.delete_collection(COLLECTION_NAME) if COLLECTION_NAME in {
        c.name for c in client.list_collections()
    } else None
    collection = client.create_collection(COLLECTION_NAME)
    if entries:
        collection.add(
            ids=[e["id"] for e in entries],
            documents=[e["text"] for e in entries],
            metadatas=[{"tags": ",".join(e["tags"])} for e in entries],
        )
    return len(entries)


def retrieve(query: str, k: int = 8, persist_dir: Path | None = None) -> list[str]:
    """Return the k profile facts most relevant to the query (a job description)."""
    client = _get_client(persist_dir)
    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception as exc:
        raise RuntimeError(
            "Profile index not built yet. Run build_index() first (needs profile/profile.json)."
        ) from exc

    results = collection.query(query_texts=[query], n_results=k)
    documents = results.get("documents") or [[]]
    return documents[0]
