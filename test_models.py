import google.generativeai as genai

genai.configure(api_key="AIzaSyAh8zCJamRexFoE4DVarrD-NQ-aFe_80L8")

for m in genai.list_models():
    print(m.name, m.supported_generation_methods)