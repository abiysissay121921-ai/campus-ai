import os
import requests
from flask import Flask, render_template_string, request, jsonify
from dotenv import load_dotenv
import chromadb

load_dotenv()

app = Flask(__name__)

# Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6LuLM6fJtFv5H_sGNGGO845moH4L5-eMoTo3BJkte0Ntg")
GEMINI_MODEL = "gemini-3.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

# Initialize ChromaDB
chroma_client = chromadb.PersistentClient(path="./chroma_db")
try:
    collection = chroma_client.get_collection(name="campus_kb")
except Exception:
    collection = chroma_client.get_or_create_collection(name="campus_kb")

# Curriculum (as before)
CURRICULUM = {
    "General Psychology": {
        "modules": ["Introduction & Research Methods", "Biological Bases of Behavior", "Sensation & Perception", "Learning & Memory"],
        "description": "Fundamental principles of human behavior and mental processes."
    },
    "Chemistry": {
        "modules": ["Atomic Structure", "Chemical Bonding", "Stoichiometry", "Thermodynamics"],
        "description": "Core university-level general chemistry principles."
    },
    "History": {
        "modules": ["World Civilizations", "The Industrial Revolution", "Modern Global Conflicts", "Contemporary History"],
        "description": "Major historical eras, movements, and global transformations."
    },
    "Geography": {
        "modules": ["Physical Geography", "Human & Cultural Geography", "Geographic Information Systems (GIS)", "Global Urbanization"],
        "description": "Study of earth landscapes, environments, and human societies."
    }
}

# Frontend HTML (same as before – using Tailwind CSS)
INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CAMPUS AI - University Platform</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen flex flex-col">
    <header class="bg-slate-800 border-b border-slate-700 p-4 shadow-md flex justify-between items-center">
        <h1 class="text-xl font-bold text-cyan-400 tracking-wide">CAMPUS AI <span class="text-xs bg-cyan-900 text-cyan-200 px-2 py-1 rounded ml-2">Gemini 3.5 Flash</span></h1>
        <span class="text-sm text-slate-400">Local RAG & Education Hub</span>
    </header>

    <main class="flex-1 flex flex-col md:flex-row p-4 gap-4 max-w-7xl mx-auto w-full">
        <aside class="w-full md:w-1/4 bg-slate-800 p-4 rounded-xl border border-slate-700 flex flex-col gap-4">
            <h2 class="font-semibold text-slate-200 border-b border-slate-700 pb-2">Curriculum Subjects</h2>
            <div class="flex flex-col gap-2">
                {% for subject, details in curriculum.items() %}
                <div class="bg-slate-900/50 p-3 rounded-lg border border-slate-700/60">
                    <h3 class="font-bold text-cyan-300 text-sm">{{ subject }}</h3>
                    <p class="text-xs text-slate-400 mt-1">{{ details.description }}</p>
                </div>
                {% endfor %}
            </div>
        </aside>

        <section class="flex-1 bg-slate-800 rounded-xl border border-slate-700 flex flex-col h-[70vh] md:h-auto overflow-hidden">
            <div id="chat-history" class="flex-1 p-4 overflow-y-auto space-y-4 flex flex-col">
                <div class="bg-slate-700/50 p-3 rounded-lg max-w-[80%] self-start text-sm">
                    Hello! I'm your CAMPUS AI assistant powered by Gemini 3.5 Flash. Ask me anything about your university coursework, subjects, or study guides!
                </div>
            </div>
            <div class="p-3 bg-slate-800 border-t border-slate-700 flex gap-2">
                <input type="text" id="user-input" placeholder="Type your academic query..." 
                    class="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-100 focus:outline-none focus:border-cyan-500">
                <button onclick="sendMessage()" class="bg-cyan-600 hover:bg-cyan-500 text-white px-5 py-2 rounded-lg text-sm font-medium transition">Send</button>
            </div>
        </section>
    </main>

    <script>
        async function sendMessage() {
            const inputField = document.getElementById('user-input');
            const chatHistory = document.getElementById('chat-history');
            const message = inputField.value.trim();
            if (!message) return;

            chatHistory.innerHTML += `<div class="bg-cyan-900/40 border border-cyan-700/50 p-3 rounded-lg max-w-[80%] self-end text-sm">${message}</div>`;
            inputField.value = '';
            chatHistory.scrollTop = chatHistory.scrollHeight;

            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: message })
                });
                const data = await res.json();
                chatHistory.innerHTML += `<div class="bg-slate-700/50 border border-slate-600/50 p-3 rounded-lg max-w-[80%] self-start text-sm">${data.response || data.error}</div>`;
            } catch (err) {
                chatHistory.innerHTML += `<div class="bg-red-900/50 p-3 rounded-lg max-w-[80%] self-start text-sm text-red-200">Error communicating with server.</div>`;
            }
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }

        document.getElementById('user-input').addEventListener('keypress', function (e) {
            if (e.key === 'Enter') { sendMessage(); }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(INDEX_HTML, curriculum=CURRICULUM)

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message', '')
        if not user_message:
            return jsonify({'error': 'Empty message'}), 400

        # Optional RAG context from ChromaDB
        context_text = ""
        try:
            results = collection.query(query_texts=[user_message], n_results=2)
            if results and results.get('documents') and results['documents'][0]:
                context_text = "\n".join(results['documents'][0])
        except Exception:
            pass

        # Build prompt
        prompt = f"Context from study materials:\n{context_text}\n\nUser Question: {user_message}" if context_text else user_message

        # Call Gemini API using requests (the exact working curl command)
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        headers = {"Content-Type": "application/json"}
        response = requests.post(GEMINI_URL, json=payload, headers=headers)

        if response.status_code == 200:
            result = response.json()
            ai_response = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "No response")
            return jsonify({'response': ai_response})
        else:
            return jsonify({'error': f'Gemini API error: {response.text}'}), response.status_code

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
