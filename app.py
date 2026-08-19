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

# Curriculum (keep your full CURRICULUM – I've included a sample, you should keep yours)
CURRICULUM = {
    "Chat with me": ["General Chat"],
    "Communicative English Language Skills I": ["English I Study Notes", "English I Mid Questions", "English I Final Questions"],
    "Communicative English Language Skills II": ["English II Study Notes", "English II Mid Questions", "English II Final Questions"],
    "Logic and Critical Thinking": ["Logic Study Notes", "Logic Mid Questions", "Logic Final Questions"],
    "Economics": ["Economics Study Notes", "Economics Mid Questions", "Economics Final Questions"],
    "Entrepreneurship": ["Entrepreneurship Study Notes", "Entrepreneurship Mid Questions", "Entrepreneurship Final Questions"],
    "Geography of Ethiopia and the Horn": ["Geography Study Notes", "Geography Mid Questions", "Geography Final Questions"],
    "History of Ethiopia and the Horn": ["History Study Notes", "History Mid Questions", "History Final Questions"],
    "Introduction to Emerging Technologies": ["Emerging Tech Study Notes", "Emerging Tech Mid Questions", "Emerging Tech Final Questions"],
    "General Psychology": ["Psychology Study Notes", "Psychology Mid Questions", "Psychology Final Questions"],
    "Social Anthropology": ["Anthropology Study Notes", "Anthropology Mid Questions", "Anthropology Final Questions"],
    "Global Trends": ["Global Trends Study Notes", "Global Trends Mid Questions", "Global Trends Final Questions"],
    "Civics and Moral Education": ["Civics Study Notes", "Civics Mid Questions", "Civics Final Questions"],
    "Inclusiveness": ["Inclusiveness Study Notes", "Inclusiveness Mid Questions", "Inclusiveness Final Questions"],
    "General Chemistry": ["Chemistry Study Notes", "Chemistry Mid Questions", "Chemistry Final Questions"],
    "General Biology": ["Biology Study Notes", "Biology Mid Questions", "Biology Final Questions"]
}

# Ensure directories exist
for folder in [UPLOAD_FOLDER, PRELOAD_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

for subject, subtopics in CURRICULUM.items():
    safe_subject_name = subject.replace(" ", "_").replace("(", "").replace(")", "")
    for subtopic in subtopics:
        folder_path = os.path.join(PRELOAD_FOLDER, safe_subject_name, subtopic.replace(" ", "_"))
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

def extract_text_from_file(filepath, filename):
    from pypdf import PdfReader
    from docx import Document
    ext = filename.split('.')[-1].lower()
    text = ""
    try:
        if ext == 'txt':
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()
        elif ext == 'pdf':
            reader = PdfReader(filepath)
            for page in reader.pages:
                text += page.extract_text() or ""
        elif ext == 'docx':
            doc = Document(filepath)
            text = "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        print(f"Error reading {filename}: {str(e)}")
    return text

def process_and_store_file(filepath, filename, subject, subtopic):
    raw_text = extract_text_from_file(filepath, filename)
    if not raw_text.strip():
        return False
    collection.add(
        documents=[raw_text],
        ids=[f"{subject}_{subtopic}_{filename}"],
        metadatas=[{
            "source": filename,
            "subject": subject,
            "subtopic": subtopic
        }]
    )
    return True

def preload_system_course_materials():
    print("\n[System] Synchronizing structured freshman course library matrix...")
    try:
        existing_records = collection.get()
        existing_sources = set(meta['source'] for meta in existing_records.get('metadatas', []) if meta)
    except Exception:
        existing_sources = set()

    for subject, subtopics in CURRICULUM.items():
        safe_subject_name = subject.replace(" ", "_").replace("(", "").replace(")", "")
        for subtopic in subtopics:
            subtopic_folder_name = subtopic.replace(" ", "_")
            target_dir = os.path.join(PRELOAD_FOLDER, safe_subject_name, subtopic_folder_name)
            if not os.path.exists(target_dir):
                continue
            files = [f for f in os.listdir(target_dir) if f.split('.')[-1].lower() in ['pdf', 'docx', 'txt']]
            for filename in files:
                if filename in existing_sources:
                    continue
                print(f" ⏳ Indexing [{subject} -> {subtopic}]: '{filename}'")
                filepath = os.path.join(target_dir, filename)
                process_and_store_file(filepath, filename, subject, subtopic)

preload_system_course_materials()

@app.route('/')
def index():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
        session['chat_count'] = 0
    return render_template('index.html')

@app.route('/get_curriculum', methods=['GET'])
def get_curriculum():
    return jsonify(CURRICULUM)

@app.route('/get_questions', methods=['POST'])
def get_questions():
    data = request.json
    subject = data.get("subject", "")
    subtopic = data.get("subtopic", "")
    safe_subject = subject.replace(" ", "_").replace("(", "").replace(")", "")
    safe_subtopic = subtopic.replace(" ", "_")
    folder_path = os.path.join(PRELOAD_FOLDER, safe_subject, safe_subtopic)
    if not os.path.exists(folder_path):
        return jsonify({
            "found": False,
            "content": f"### No resource found\n\nPlease place your official `{safe_subtopic}.json` or PDF inside:\n`knowledge_base/{safe_subject}/{safe_subtopic}/`"
        })
    is_questions_mode = "Questions" in subtopic
    if is_questions_mode:
        quiz_files = [f for f in os.listdir(folder_path) if f.endswith('.json') and not f.startswith('.')]
        if quiz_files:
            try:
                with open(os.path.join(folder_path, quiz_files[0]), 'r', encoding='utf-8') as f:
                    quiz_data = json.load(f)
                return jsonify({
                    "found": True,
                    "type": "quiz",
                    "questions": quiz_data
                })
            except Exception as e:
                print(f"Failed decoding JSON quiz file structure: {str(e)}")
    files = [f for f in os.listdir(folder_path) if f.split('.')[-1].lower() in ['pdf', 'docx', 'txt'] and not f.startswith('.')]
    if files:
        target_filename = files[0]
        file_url = f"/view_file?subject={safe_subject}&subtopic={safe_subtopic}&filename={target_filename}"
        return jsonify({
            "found": True,
            "type": "document",
            "file_url": file_url,
            "filename": target_filename
        })
    else:
        return jsonify({
            "found": False,
            "content": f"### No structural resource assets discovered\n\nPlease place your official `{safe_subtopic}.json` dataset or document sheets within:\n`knowledge_base/{safe_subject}/{safe_subtopic}/`"
        })

@app.route('/view_file', methods=['GET'])
def view_file():
    subject = request.args.get('subject')
    subtopic = request.args.get('subtopic')
    filename = request.args.get('filename')
    exact_filepath = os.path.join(PRELOAD_FOLDER, subject, subtopic, filename)
    if os.path.exists(exact_filepath):
        return send_file(exact_filepath)
    else:
        return "Requested document resource not found on local workspace disk paths.", 404

@app.route('/chat', methods=['POST'])
def chat():
    if 'chat_count' not in session:
        session['chat_count'] = 0
    if session['chat_count'] >= MAX_CHAT_LIMIT:
        return jsonify({
            "response": f"⚠️ **Daily Session Limit Reached:** You have used your {MAX_CHAT_LIMIT} complimentary AI queries. You can still browse all study notes and exam files freely without limits!"
        }), 403

    data = request.json
    user_message = data.get("message", "")
    active_subject = data.get("subject", "")
    active_subtopic = data.get("subtopic", "")

    try:
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

        # --- CORRECT MODEL (gemini-3.5-flash) ---
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt
        )
        ai_response = response.text if response.text else "I couldn't generate a response."

        session['chat_count'] += 1
        return jsonify({"response": ai_response})

    except Exception as e:
        print(f"ERROR in /chat: {e}")
        error_msg = str(e)
        if "API key" in error_msg or "apikey" in error_msg.lower():
            error_msg = "Invalid or missing API key. Please check your .env file."
        return jsonify({"response": f"Error: {error_msg}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
