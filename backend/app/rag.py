"""ChromaDB-backed store for approved interview answers."""

import chromadb

from app.shared_context import MEMORY_DIR

DB_PATH = MEMORY_DIR / "chroma_db"


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
