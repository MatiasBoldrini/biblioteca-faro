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
                'models/gemini-2.0-flash-lite',
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
            # Verificar si hay resultados relevantes
            if not sources or not any(source['score'] > 0.2 for source in sources):
                return "No encontré información suficientemente relevante para responder a tu pregunta específica. ¿Podrías reformularla o ser más específico?"

            # Reformatear el contexto para resaltar mejor las fuentes y páginas
            formatted_sources = []
            for i, source in enumerate(sources):
                if source['score'] > 0.2:  # Solo incluir fuentes relevantes
                    book_name = source["book"].split("_")[0]
                    page_num = source["page"]
                    text = source["text"].strip()
                    formatted_sources.append(f"[FUENTE {i+1}] De '{book_name}', página {page_num}:\n{text}")
            
            formatted_context = "\n\n".join(formatted_sources)
            
            prompt = f"""
            Eres un asistente especializado en responder preguntas basándote en la documentación proporcionada.
            
            CONTEXTO RELEVANTE:
            {formatted_context}
            
            PREGUNTA DEL USUARIO:
            {query}
            
            INSTRUCCIONES IMPORTANTES:
            1. SOLO uses la información proporcionada en el CONTEXTO RELEVANTE.
            2. Si el contexto no contiene información suficiente para responder la pregunta específica, indica claramente qué parte de la pregunta no puedes responder.
            3. Cita SIEMPRE tus fuentes usando el formato [FUENTE X].
            4. Incluye los números de página en las citas.
            5. Al final, lista las fuentes utilizadas.
            
            Responde de manera clara y directa, citando las fuentes específicas para cada parte de tu respuesta.
            Si el contexto contiene información parcial, proporciona la parte que puedas responder e indica qué información falta.
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
