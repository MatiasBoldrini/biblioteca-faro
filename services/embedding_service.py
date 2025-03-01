import os

import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingService:
    def __init__(self, model_name='multi-qa-mpnet-base-dot-v1'):
        """Initialize the embedding service with the specified model"""
        try:
            self.model = SentenceTransformer(model_name)
            print(f"Loaded embedding model: {model_name}")
        except Exception as e:
            print(f"Error loading embedding model: {e}")
            raise
    
    def get_embedding(self, text):
        """Get embedding for a single text"""
        if not text or not text.strip():
            return None
        
        try:
            # Normalize text
            text = text.strip().replace('\n', ' ')
            # Generate embedding
            embedding = self.model.encode(text, normalize_embeddings=True)
            return embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return None
    
    def get_embeddings(self, texts):
        """Get embeddings for a list of texts"""
        if not texts:
            return []
        
        # Filter out empty texts and normalize
        valid_texts = [t.strip().replace('\n', ' ') for t in texts if t and t.strip()]
        if not valid_texts:
            return []
        
        try:
            # Generate embeddings in batch with normalization
            embeddings = self.model.encode(valid_texts, normalize_embeddings=True)
            return embeddings
        except Exception as e:
            print(f"Error generating embeddings: {e}")
            return []
    
    def compute_similarity(self, embedding1, embedding2):
        """Compute cosine similarity between two embeddings"""
        if embedding1 is None or embedding2 is None:
            return 0.0
        
        # Normalize embeddings for cosine similarity
        embedding1 = embedding1 / np.linalg.norm(embedding1)
        embedding2 = embedding2 / np.linalg.norm(embedding2)
        
        # Compute similarity
        similarity = np.dot(embedding1, embedding2)
        return float(similarity)
