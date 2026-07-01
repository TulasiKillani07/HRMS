"""
Embedding Service
Uses BAAI/bge-base-en-v1.5 for semantic embeddings
Model loaded globally once for low latency
"""

from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from typing import List


class EmbeddingService:
    """Manages embedding generation and semantic similarity computation"""

    _instance = None
    _model = None

    def __new__(cls, model_name: str = "BAAI/bge-base-en-v1.5"):
        """Singleton pattern - load model only once"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._model = None
        return cls._instance

    def __init__(self, model_name: str = "BAAI/bge-base-en-v1.5"):
        if self._model is None:
            print(f"Loading embedding model: {model_name}...")
            self._model = SentenceTransformer(model_name)
            print("Embedding model loaded successfully.")

    def encode(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for a list of texts.
        Uses batch encoding for efficiency.
        """
        if not texts:
            return np.array([])

        # BGE models recommend prepending "Represent this sentence:" for better results
        # but for retrieval tasks, we use the text as-is for documents
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=32
        )
        return embeddings

    def encode_single(self, text: str) -> np.ndarray:
        """Generate embedding for a single text"""
        if not text:
            return np.zeros(768)  # bge-base-en-v1.5 dimension
        embedding = self._model.encode(
            [text],
            normalize_embeddings=True,
            show_progress_bar=False
        )
        return embedding[0]

    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings"""
        if embedding1.size == 0 or embedding2.size == 0:
            return 0.0

        # Reshape for sklearn
        e1 = embedding1.reshape(1, -1)
        e2 = embedding2.reshape(1, -1)

        similarity = cosine_similarity(e1, e2)[0][0]
        return float(max(0.0, min(1.0, similarity)))

    def compute_batch_similarity(self, query_embedding: np.ndarray, doc_embeddings: np.ndarray) -> List[float]:
        """Compute similarity between one query and multiple documents"""
        if query_embedding.size == 0 or doc_embeddings.size == 0:
            return [0.0] * len(doc_embeddings)

        query = query_embedding.reshape(1, -1)
        similarities = cosine_similarity(query, doc_embeddings)[0]
        return [float(max(0.0, min(1.0, s))) for s in similarities]

    def get_multi_aspect_similarity(self, jd_text: str, resume_text: str,
                                     resume_sections: dict) -> dict:
        """
        Compute multi-aspect semantic similarity.
        Generates embeddings for different aspects of the resume vs JD.
        """
        jd_embedding = self.encode_single(jd_text)

        # Full resume similarity
        resume_embedding = self.encode_single(resume_text)
        full_similarity = self.compute_similarity(jd_embedding, resume_embedding)

        # Skills section similarity
        skills_text = resume_sections.get("skills", "")
        skills_similarity = 0.0
        if skills_text:
            skills_embedding = self.encode_single(skills_text)
            skills_similarity = self.compute_similarity(jd_embedding, skills_embedding)

        # Experience section similarity
        exp_text = resume_sections.get("experience", "")
        exp_similarity = 0.0
        if exp_text:
            exp_embedding = self.encode_single(exp_text)
            exp_similarity = self.compute_similarity(jd_embedding, exp_embedding)

        # Projects section similarity
        proj_text = resume_sections.get("projects", "")
        proj_similarity = 0.0
        if proj_text:
            proj_embedding = self.encode_single(proj_text)
            proj_similarity = self.compute_similarity(jd_embedding, proj_embedding)

        return {
            "full_similarity": full_similarity,
            "skills_similarity": skills_similarity,
            "experience_similarity": exp_similarity,
            "project_similarity": proj_similarity,
        }
