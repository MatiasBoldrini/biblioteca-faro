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
        # Configure the Gemini API
        genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
        
        # Get available models
        try:
            self.model = genai.GenerativeModel(
                'models/gemini-2.0-flash-lite-preview-02-05',
                generation_config={'temperature': 0.3}  # Default temperature
            )
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
            # Reformatear el contexto para resaltar mejor las fuentes y páginas
            formatted_sources = []
            for i, source in enumerate(sources):
                book_name = source["book"].split("_")[0]  # Quitar el UUID
                page_num = source["page"]
                text = source["text"]
                # Aquí es donde explícitamente incluimos el número de página en el contexto
                formatted_sources.append(f"[FUENTE {i+1}] {book_name}, página {page_num}\n{text}")
            
            formatted_context = "\n\n".join(formatted_sources)
            
            # Create a prompt with the context and query, including explicit instructions
            prompt = f"""
            Tu tarea es responder a la pregunta del usuario basándote ÚNICAMENTE en la información proporcionada.
            Si la información para responder no está en el contexto, indica que no tienes suficiente información.
            
            CONTEXTO:
            {formatted_context}
            
            PREGUNTA:
            {query}
            
            INSTRUCCIONES IMPORTANTES:
            - Responde en español de manera clara y concisa.
            - CADA VEZ que uses información del contexto, debes citar la fuente exacta usando el formato [FUENTE X] donde X es el número de la fuente.
            - Asegúrate de mencionar el número de página exacto como aparece en el contexto (por ejemplo: "página 1-22", "página 4-32").
            - Al final de tu respuesta, incluye una sección de "Fuentes:" con la lista completa de fuentes utilizadas:
              
              Fuentes:
              [1] Nombre del libro, página X-X
              [2] Nombre del libro, página X-X
              
            - NO INVENTES información ni números de página que no estén en el contexto.
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
