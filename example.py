import os
from dotenv import load_dotenv

import google.generativeai as genai

# Load environment variables from .env file
load_dotenv()

# Configure with API key from .env
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))

# 1. Procesar contexto largo con Gemini 1.5 Pro
long_context_model = genai.GenerativeModel(
    'models/gemini-2.0-flash-lite-preview-02-05',
    generation_config={'temperature': 0.3}  # Default temperature
)
response = long_context_model.generate_content(
    f"""Aquí va tu contexto largo (hasta 2M tokens). 
    Ejemplo: metadatos de 100,000 registros en formato JSON: """
)
print("Respuesta generada:", response.text)