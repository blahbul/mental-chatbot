import google.generativeai as genai
import os

# Make sure to replace this with your actual key
api_key = "AIzaSyBu-qLl7kQ8nIR8QpXBh_izew8q2keFZ4Q" 

try:
    print("Attempting to configure API key...")
    genai.configure(api_key=api_key)
    print("API key configured successfully.")

    print("\nFetching available models from Google AI...")
    model_count = 0
    for model in genai.list_models():
        if 'generateContent' in model.supported_generation_methods:
            print(f" - Found model: {model.name}")
            model_count += 1
    
    if model_count > 0:
        print("\n✅ Test successful! Your API key and network connection are working correctly.")
    else:
        print("\n⚠️ Test completed, but no models were found. Check your key's permissions.")

except Exception as e:
    print(f"\n❌ An error occurred: {e}")