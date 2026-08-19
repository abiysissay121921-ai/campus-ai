import os
import uuid
from flask import Flask, request, jsonify, render_template, session, send_file
import chromadb
import json
from dotenv import load_dotenv
from google import genai

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "campus_ai_secure_fallback_key")

UPLOAD_FOLDER = 'uploads'
PRELOAD_FOLDER = 'knowledge_base'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
MAX_CHAT_LIMIT = 10

# --- GEMINI CONFIG ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not set in environment.")

client = genai.Client(api_key=GEMINI_API_KEY)

# ChromaDB
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="freshman_knowledge_base")

# Curriculum (keep your full CURRICULUM dictionary here – I've truncated for brevity)
CURRICULUM = {
    "Chat with me": ["General Chat"],
    "Communicative English Language Skills I": ["English I Study Notes", "English I Mid Questions", "English I Final Questions"],
    # ... (add all your subjects here, copy from your existing code)
}

# Ensure directories, preload, routes – all unchanged except /chat
# ... (all other functions: extract_text, process_and_store, preload, /, /get_curriculum, /get_questions, /view_file)

@app.route('/chat', methods=['POST'])
def chat():
    if 'chat_count' not in session:
        session['chat_count'] = 0
    if session['chat_count'] >= MAX_CHAT_LIMIT:
        return jsonify({
            "response": f"⚠️ **Daily Session Limit Reached:** You have used your {MAX_CHAT_LIMIT} complimentary AI queries."
        }), 403

    data = request.json
    user_message = data.get("message", "")
    active_subject = data.get("subject", "")
    active_subtopic = data.get("subtopic", "")

    try:
        # Retrieve RAG context
        results = collection.get(where={"$and": [{"subject": active_subject}, {"subtopic": active_subtopic}]})
        documents = results.get("documents", [])
        context_string = documents[0] if documents else ""

        if active_subject != "Chat with me" and context_string:
            prompt = f"""You are Campus AI. Assist the student by answering their question using the reference text provided below.

Reference Document Context:
{context_string}

Student's Question: {user_message}
Answer:"""
        else:
            prompt = f"""You are Campus AI, a supportive university assistant. Answer the student's question clearly.

Question: {user_message}
Answer:"""

        # --- New SDK Call ---
        response = client.models.generate_content(
            model='gemini-1.5-flash',   # or 'gemini-1.5-pro' if needed
            contents=prompt
        )
        ai_response = response.text if response.text else "I couldn't generate a response."

        session['chat_count'] += 1
        return jsonify({"response": ai_response})

    except Exception as e:
        print(f"ERROR: {e}")
        error_msg = str(e)
        if "API key" in error_msg or "apikey" in error_msg.lower():
            error_msg = "Invalid or missing API key. Please check your .env file."
        return jsonify({"response": f"Error: {error_msg}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
