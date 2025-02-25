import os
import pickle
from collections import defaultdict

import faiss
import numpy as np

from .document_service import DocumentService
from .embedding_service import EmbeddingService


class VectorStoreService:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.index_file = os.path.join(self.base_dir, 'data', 'faiss_index.pkl')
        self.metadata_file = os.path.join(self.base_dir, 'data', 'metadata.pkl')
        
        # Create data directory if it doesn't exist
        os.makedirs(os.path.join(self.base_dir, 'data'), exist_ok=True)
        
        # Initialize services
        self.document_service = DocumentService()
        self.embedding_service = EmbeddingService()
        
        # Initialize index and metadata
        self.index = None
        self.metadata = []
        
        # Load existing index and metadata if available
        self._load_index()
    
    def _load_index(self):
        """Load existing index and metadata if available"""
        try:
            if os.path.exists(self.index_file) and os.path.exists(self.metadata_file):
                with open(self.index_file, 'rb') as f:
                    self.index = pickle.load(f)
                with open(self.metadata_file, 'rb') as f:
                    self.metadata = pickle.load(f)
                print(f"Loaded index with {self.index.ntotal} vectors and {len(self.metadata)} metadata entries")
            else:
                print("No existing index found. Creating a new one.")
                self._create_empty_index()
        except Exception as e:
            print(f"Error loading index: {e}")
            self._create_empty_index()
    
    def _create_empty_index(self):
        """Create an empty FAISS index"""
        # Using L2 distance for cosine similarity (after normalization)
        dimension = 384  # Default for multilingual-MiniLM model
        self.index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity
        self.metadata = []
    
    def _save_index(self):
        """Save the index and metadata to disk"""
        try:
            with open(self.index_file, 'wb') as f:
                pickle.dump(self.index, f)
            with open(self.metadata_file, 'wb') as f:
                pickle.dump(self.metadata, f)
            print(f"Saved index with {self.index.ntotal} vectors and {len(self.metadata)} metadata entries")
        except Exception as e:
            print(f"Error saving index: {e}")
    
    def add_document(self, file_path):
        """Process a document and add its chunks to the index"""
        # Extract chunks with metadata
        chunks = self.document_service.extract_text_with_metadata(file_path)
        
        if not chunks:
            print(f"No text extracted from {file_path}")
            return 0
        
        # Get embeddings for all chunks
        texts = [chunk['text'] for chunk in chunks]
        embeddings = self.embedding_service.get_embeddings(texts)
        
        # Normalize embeddings for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized_embeddings = embeddings / norms
        
        # Add to FAISS index
        self.index.add(np.array(normalized_embeddings).astype('float32'))
        
        # Add metadata
        start_idx = len(self.metadata)
        for i, chunk in enumerate(chunks):
            chunk['id'] = start_idx + i
            chunk['clean_book_name'] = chunk['book'].split('_')[0]  # Remove UUID part
            self.metadata.append(chunk)
        
        # Save updated index
        self._save_index()
        
        return len(chunks)
    
    def search(self, query, top_k=5):
        """Search for relevant chunks using the query"""
        if not self.metadata or self.index.ntotal == 0:
            print("No documents in the index yet")
            return []
        
        # Get query embedding
        query_embedding = self.embedding_service.get_embedding(query)
        if query_embedding is None:
            print("Could not generate embedding for query")
            return []
        
        # Normalize for cosine similarity
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        query_embedding = np.array([query_embedding]).astype('float32')
        
        # Search
        distances, indices = self.index.search(query_embedding, top_k)
        
        # Get corresponding metadata
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1 and idx < len(self.metadata):  # -1 indicates no match found
                result = self.metadata[idx].copy()
                result['score'] = float(distances[0][i])
                results.append(result)
        
        return results


    def reindex_all_documents(self):
        """Rebuild the index from all documents in the books directory"""
        # Clear existing index
        self._create_empty_index()
        
        # Get all books
        all_books = self.document_service.get_all_books()
        total_chunks = 0
        
        for book_path in all_books:
            chunks_added = self.add_document(book_path)
            total_chunks += chunks_added
            print(f"Added {chunks_added} chunks from {os.path.basename(book_path)}")
        
        print(f"Reindexing complete. Total chunks: {total_chunks}")
        return total_chunks
