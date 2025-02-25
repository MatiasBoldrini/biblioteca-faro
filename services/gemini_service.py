import os
import re
from typing import Dict, List

import google.generativeai as genai
from dotenv import load_dotenv

from .vector_store_service import VectorStoreService

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

class GeminiService:
    def __init__(self):
        """Initialize the Gemini service with API key from environment"""
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        
        # Configure the Gemini API
        genai.configure(api_key=api_key)
        
        # Get available models
        try:
            self.model = genai.GenerativeModel('gemini-pro')
            print("Successfully connected to Gemini API")
        except Exception as e:
            print(f"Error connecting to Gemini API: {e}")
            raise
        
        self.vector_store = VectorStoreService()
        
    def generate_response(self, query: str, context: str, sources: List[Dict]) -> str:
        """
        Generate a response using Gemini based on the query and context
        
        Args:
            query: User's question
            context: Text content from relevant chunks
            sources: List of source metadata for citation
        
        Returns:
            Generated response with citations
        """
        try:
            # Create a prompt with the context and query
            prompt = f"""
            Tu tarea es responder a la pregunta del usuario basándote en la información proporcionada.
            Si la información para responder no está en el contexto, indica que no tienes suficiente información.
            Usa solo la información proporcionada en el contexto.
            
            CONTEXTO:
            {context}
            
            PREGUNTA:
            {query}
            
            INSTRUCCIONES IMPORTANTES:
            - Responde en español.
            - Proporciona una respuesta clara y concisa.
            - Si mencionas información del contexto, incluye una referencia al origen usando [número].
            - Al final de tu respuesta, enumera las fuentes utilizadas con el formato:
              Fuentes:
              [1] Nombre del libro, página X
              [2] Nombre del libro, página Y
              etc.
            """
            
            # Generate response
            response = self.model.generate_content(prompt)
            answer = response.text
            
            # Process the answer to add proper citation links
            answer = self._format_citations(answer, sources)
            
            return answer
            
        except Exception as e:
            print(f"Error generating response: {e}")
            return f"Lo siento, ocurrió un error al generar la respuesta: {str(e)}"
    
    def _format_citations(self, text: str, sources: List[Dict]) -> str:
        """Format the citations in the text with proper links to sources"""
        # Replace citation markers with clickable spans
        citation_pattern = r'\[(\d+)\]'
        
        processed_text = text
        
        # Find all citations
        citations = re.findall(citation_pattern, text)
        
        # Create source mapping
        source_map = {}
        for idx, citation_num in enumerate(set(citations)):
            if idx < len(sources):
                source = sources[idx]
                book_name = source["book"].split("_")[0]  # Remove UUID part
                page = source["page"]
                source_map[citation_num] = {
                    "book": book_name,
                    "page": page,
                    "idx": idx
                }
        
        # Replace citations with clickable spans
        for citation_num in set(citations):
            if citation_num in source_map:
                source = source_map[citation_num]
                replacement = f'<span class="citation" data-source-idx="{source["idx"]}">[{citation_num}]</span>'
                processed_text = re.sub(r'\[' + citation_num + r'\]', replacement, processed_text)
        
        return processed_text
    
    def process_file(self, file_path):
        """Process a newly uploaded file and add it to the vector store"""
        try:
            self.vector_store.add_document(file_path)
            return True
        except Exception as e:
            print(f"Error processing file: {str(e)}")
            return False
