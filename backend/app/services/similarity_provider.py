"""
Text Similarity Provider Abstraction (Embedding-Ready Architecture).
Defines the interface for computing text similarity matrices and pairwise scores,
allowing seamless transition from TF-IDF to semantic embedding models.
"""
from abc import ABC, abstractmethod
from typing import List
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class TextSimilarityProvider(ABC):
    """
    Abstract interface for news text similarity computation.
    Decouples the clustering algorithm from specific vectorization backends.
    """

    @abstractmethod
    def compute_similarity_matrix(self, texts: List[str]) -> np.ndarray:
        """
        Computes an NxN pairwise similarity matrix for a collection of texts.
        Returns a symmetric matrix where M[i, j] in [0.0, 1.0].
        """
        pass

    @abstractmethod
    def compute_pairwise(self, text_a: str, text_b: str) -> float:
        """
        Computes similarity score between two individual text strings.
        """
        pass


class TFIDFSimilarityProvider(TextSimilarityProvider):
    """
    Deterministic TF-IDF similarity provider using sublinear term-frequency scaling
    and custom tokenization for technology identifiers and version codes.
    """

    def __init__(
        self,
        stop_words: str = "english",
        token_pattern: str = r"(?u)\b\w+\b",
        ngram_range: tuple = (1, 1)
    ):
        self.stop_words = stop_words
        self.token_pattern = token_pattern
        self.ngram_range = ngram_range

    def _get_vectorizer(self) -> TfidfVectorizer:
        return TfidfVectorizer(
            stop_words=self.stop_words,
            token_pattern=self.token_pattern,
            ngram_range=self.ngram_range,
            sublinear_tf=True
        )

    def compute_similarity_matrix(self, texts: List[str]) -> np.ndarray:
        n = len(texts)
        if n == 0:
            return np.zeros((0, 0))
        if n == 1:
            return np.ones((1, 1))

        vectorizer = self._get_vectorizer()
        tfidf_matrix = vectorizer.fit_transform(texts)
        return cosine_similarity(tfidf_matrix)

    def compute_pairwise(self, text_a: str, text_b: str) -> float:
        if not text_a or not text_b:
            return 0.0
        matrix = self.compute_similarity_matrix([text_a, text_b])
        return float(matrix[0, 1])


# Placeholder for future vector embedding integration:
# class EmbeddingSimilarityProvider(TextSimilarityProvider):
#     def __init__(self, model_name: str = "text-embedding-3-small"):
#         self.model_name = model_name
#     ...
