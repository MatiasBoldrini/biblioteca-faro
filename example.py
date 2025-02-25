import os
from dotenv import load_dotenv

import google.generativeai as genai

# Load environment variables from .env file
load_dotenv()

# Configure with API key from .env
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))

# 1. Procesar contexto largo con Gemini 1.5 Pro
long_context_model = genai.GenerativeModel(
    'models/gemini-1.5-pro-latest',
    generation_config={'temperature': 0.8}  # Default temperature
)
response = long_context_model.generate_content(
    f"""Aquí va tu contexto largo (hasta 2M tokens). 
    Ejemplo: metadatos de 100,000 registros en formato JSON: """
)
print("Respuesta generada:", response.text)