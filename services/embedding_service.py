import os

import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingService:
    def __init__(self, model_name="paraphrase-multilingual-MiniLM-L12-v2"):
        """
        Initialize the embedding service with a multilingual model by default
        
        Args:
            model_name (str): Name of the sentence-transformer model to use
        """
        self.model = SentenceTransformer(model_name)
    
    def get_embeddings(self, texts):
        """
        Generate embeddings for a list of texts
        
        Args:
            texts (list): List of strings to generate embeddings for
            
        Returns:
            list: List of embeddings as numpy arrays
        """
        if not texts:
            return []
            
        # Generate embeddings
        embeddings = self.model.encode(texts, show_progress_bar=False)
        return embeddings
    
    def get_embedding(self, text):
        """
        Generate embedding for a single text
        
        Args:
            text (str): Text to generate embedding for
            
        Returns:
            numpy.ndarray: Embedding vector
        """
        if not text:
            return None
            
        return self.model.encode(text, show_progress_bar=False)
