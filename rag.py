"""ChromaDB-backed store for approved interview answers."""

from pathlib import Path

import chromadb

DB_PATH = Path(__file__).parent / "memory" / "chroma_db"


def _collection():
    client = chromadb.PersistentClient(path=str(DB_PATH))
    return client.get_or_create_collection("interview_answers")


def store_answer(job_name: str, question: str, approved_answer: str) -> None:
    col = _collection()
    doc_id = f"{job_name}::{hash(question) & 0xFFFFFFFF}"
    col.upsert(
        documents=[approved_answer],
        metadatas=[{"job_name": job_name, "question": question}],
        ids=[doc_id],
    )


def retrieve_similar(question: str, n_results: int = 3) -> list:
    col = _collection()
    count = col.count()
    if count == 0:
        return []
    results = col.query(
        query_texts=[question],
        n_results=min(n_results, count),
    )
    return [
        {"answer": doc, "job": meta["job_name"], "question": meta["question"]}
        for doc, meta in zip(results["documents"][0], results["metadatas"][0])
    ]


def list_answers() -> list:
    """All approved answers ever stored, for browsing/management."""
    col = _collection()
    if col.count() == 0:
        return []
    data = col.get()
    return [
        {"id": id_, "job": meta["job_name"], "question": meta["question"], "answer": doc}
        for id_, doc, meta in zip(data["ids"], data["documents"], data["metadatas"])
    ]


def delete_answer(doc_id: str) -> None:
    _collection().delete(ids=[doc_id])
