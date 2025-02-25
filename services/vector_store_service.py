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
                # Load FAISS index
                self.index = faiss.read_index(self.index_file)
                
                # Load metadata
                with open(self.metadata_file, 'rb') as f:
                    self.metadata = pickle.load(f)
                
                print(f"Loaded index with {self.index.ntotal} vectors")
            else:
                print("No existing index found, creating a new one")
                self._create_empty_index()
        except Exception as e:
            print(f"Error loading index: {e}")
            self._create_empty_index()
    
    def _create_empty_index(self):
        """Create an empty FAISS index"""
        # Using L2 distance for cosine similarity (after normalization)
        dimension = 768  # Dimension for mpnet model
        self.index = faiss.IndexFlatIP(dimension)
        self.metadata = []
    
    def _save_index(self):
        """Save the index and metadata to disk"""
        try:
            # Save FAISS index
            faiss.write_index(self.index, self.index_file)
            
            # Save metadata
            with open(self.metadata_file, 'wb') as f:
                pickle.dump(self.metadata, f)
            
            print(f"Saved index with {self.index.ntotal} vectors")
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
        
        # Add to FAISS index (embeddings are already normalized by the service)
        self.index.add(np.array(embeddings).astype('float32'))
        
        # Add metadata with exact page tracking
        start_idx = len(self.metadata)
        for i, chunk in enumerate(chunks):
            chunk_metadata = {
                'text': chunk['text'],
                'page': chunk['page'],
                'book': chunk['book'],
                'index': start_idx + i,
                'chunk_start': chunk.get('chunk_start', 0),  # Add position tracking
                'chunk_end': chunk.get('chunk_end', 0)
            }
            self.metadata.append(chunk_metadata)
        
        self._save_index()
        return len(chunks)
    
    def search(self, query, top_k=5, similarity_threshold=0.4):
        """Search for relevant chunks using the query"""
        if not self.metadata or self.index.ntotal == 0:
            return []
        
        # Get query embedding (already normalized by the service)
        query_embedding = self.embedding_service.get_embedding(query)
        if query_embedding is None:
            print("Could not generate embedding for query")
            return []
        
        # Search with normalized query - get more results initially
        query_embedding = np.array([query_embedding]).astype('float32')
        k = min(top_k * 2, self.index.ntotal)  # Get more results initially for filtering
        distances, indices = self.index.search(query_embedding, k)
        
        # Get corresponding metadata and filter by similarity threshold
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.metadata):
                score = float(distances[0][i])
                if score > similarity_threshold:  # Only keep relevant results
                    result = self.metadata[idx].copy()
                    result['score'] = score
                    results.append(result)
        
        # Sort by score and limit to top_k
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]

    def remove_document(self, filename):
        """Remove a document from the index by filename"""
        if not self.metadata or self.index.ntotal == 0:
            return 0
        
        # Find indices to remove
        indices_to_remove = []
        remaining_metadata = []
        
        for i, item in enumerate(self.metadata):
            if item['book'] == filename:
                indices_to_remove.append(i)
            else:
                remaining_metadata.append(item)
        
        if not indices_to_remove:
            return 0
            
        # Create a new index without the removed document
        self._create_empty_index()
        
        # Get embeddings to add back
        if remaining_metadata:
            texts = [item['text'] for item in remaining_metadata]
            embeddings = self.embedding_service.get_embeddings(texts)
            
            # Normalize embeddings
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            normalized_embeddings = embeddings / norms
            
            # Add back to index
            self.index.add(np.array(normalized_embeddings).astype('float32'))
            self.metadata = remaining_metadata
            
            # Update index
            self._save_index()
        
        return len(indices_to_remove)

    def reindex_all_documents(self):
        """Rebuild the index from all documents in the books directory"""
        # Create empty index
        self._create_empty_index()
        
        # Get all documents
        document_service = DocumentService()
        all_books = document_service.get_all_books()
        
        count = 0
        for book_path in all_books:
            try:
                num_chunks = self.add_document(book_path)
                count += num_chunks
            except Exception as e:
                print(f"Error reindexing {book_path}: {e}")
        
        return count
