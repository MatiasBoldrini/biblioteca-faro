import os

import google.generativeai as genai
from dotenv import load_dotenv

from .vector_store_service import VectorStoreService

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

class GeminiService:
    def __init__(self):
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        genai.configure(api_key=GOOGLE_API_KEY)
        
        # Configure the model
        self.model = genai.GenerativeModel('gemini-pro')
        self.vector_store = VectorStoreService()
        
    def generate_response(self, user_query, context, relevant_chunks):
        """
        Generate a response using Google's Gemini model
        
        Args:
            user_query (str): The user's question
            context (str): Context from relevant document chunks
            relevant_chunks (list): List of document chunks with metadata
        
        Returns:
            str: The generated response
        """
        # Organize chunks by book to detect conflicts
        books_info = {}
        has_multiple_books = False
        
        # Create citations for the sources with page numbers
        citations = []
        for i, chunk in enumerate(relevant_chunks):
            clean_book_name = chunk.get('clean_book_name', chunk['book'])
            page = chunk.get('page', 'N/A')
            
            # Track books for conflict detection
            if clean_book_name not in books_info:
                books_info[clean_book_name] = []
            books_info[clean_book_name].append({
                'page': page,
                'text': chunk['text'],
                'citation_idx': i+1
            })
            
            # Create citation
            if page != 'N/A':
                citation = f"[{i+1}] {clean_book_name}, página {page}"
            else:
                citation = f"[{i+1}] {clean_book_name}"
                
            citations.append(citation)
        
        citations_text = "\n".join(citations)
        has_multiple_books = len(books_info.keys()) > 1
        
        # Determine if we should highlight potential conflicts
        conflict_instruction = ""
        if has_multiple_books:
            conflict_instruction = """
            IMPORTANTE: La información proviene de diferentes libros que podrían contener información contradictoria.
            Si detectas contradicciones entre las fuentes:
            1. Señala explícitamente las diferencias
            2. Presenta ambas perspectivas con sus respectivas citas
            3. No intentes reconciliar información contradictoria, solo presenta las diferentes perspectivas
            """
        
        # Create system prompt with instructions
        system_prompt = f"""
        You are Faro, a helpful librarian assistant. Answer questions in Spanish based ONLY on the provided context.
        
        Guidelines:
        - If you don't know the answer based on the context, say "No tengo suficiente información para responder a esa pregunta"
        - Include citations in your responses using [1], [2], etc. that match the source numbers provided
        - ALWAYS include page numbers in your citations when available
        - For example: "Según el libro X, página Y [Z]..."
        - Keep answers concise and focused on the question
        - Always respond in Spanish
        - Do not make up information not included in the context
        
        {conflict_instruction}
        
        Context:
        {context}
        
        Sources:
        {citations_text}
        """
        
        # Generate response
        try:
            response = self.model.generate_content(
                [system_prompt, user_query],
                generation_config={
                    'temperature': 0.2,
                    'top_p': 0.8,
                    'top_k': 40,
                    'max_output_tokens': 800,
                }
            )
            
            return response.text
            
        except Exception as e:
            print(f"Error generating response: {e}")
            return "Lo siento, ha ocurrido un error al procesar tu pregunta. Por favor, inténtalo de nuevo."
    
    def process_file(self, file_path):
        """Process a newly uploaded file and add it to the vector store"""
        try:
            self.vector_store.add_document(file_path)
            return True
        except Exception as e:
            print(f"Error processing file: {str(e)}")
            return False
