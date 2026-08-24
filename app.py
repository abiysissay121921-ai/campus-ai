import os
import uuid
import json
from flask import Flask, request, jsonify, render_template, session, send_file
import chromadb

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "campus_ai_secure_fallback_key")

PRELOAD_FOLDER = 'knowledge_base'

# ChromaDB (kept for possible future use)
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="freshman_knowledge_base")

# --- DYNAMICALLY BUILD CURRICULUM FROM FOLDERS ---
def build_curriculum():
    curriculum = {}
    if not os.path.exists(PRELOAD_FOLDER):
        os.makedirs(PRELOAD_FOLDER)
    for item in os.listdir(PRELOAD_FOLDER):
        folder_path = os.path.join(PRELOAD_FOLDER, item)
        if os.path.isdir(folder_path) and not item.startswith('.'):
            # Each folder becomes a subject
            # We'll use the folder name as subject, and a single dummy subtopic "Content"
            curriculum[item] = ["Content"]
    return curriculum

CURRICULUM = build_curriculum()

# Ensure folders exist (just in case)
for subject in CURRICULUM.keys():
    folder_path = os.path.join(PRELOAD_FOLDER, subject)
    os.makedirs(folder_path, exist_ok=True)

@app.route('/')
def index():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return render_template('index.html')

@app.route('/get_curriculum', methods=['GET'])
def get_curriculum():
    return jsonify(CURRICULUM)

@app.route('/get_questions', methods=['POST'])
def get_questions():
    data = request.json
    subject = data.get("subject", "")
    subtopic = data.get("subtopic", "")  # we ignore subtopic now

    folder_path = os.path.join(PRELOAD_FOLDER, subject)

    if not os.path.exists(folder_path):
        return jsonify({
            "found": False,
            "content": f"Subject folder not found: {subject}"
        })

    # Look for any file in the folder
    all_files = os.listdir(folder_path)
    # Filter out directories and hidden files
    files = [f for f in all_files if os.path.isfile(os.path.join(folder_path, f)) and not f.startswith('.')]

    # First check for JSON (quiz)
    quiz_files = [f for f in files if f.endswith('.json')]
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
            print(f"Error loading quiz: {e}")

    # Then check for documents
    doc_files = [f for f in files if f.split('.')[-1].lower() in ['pdf', 'docx', 'txt']]
    if doc_files:
        target = doc_files[0]
        file_url = f"/view_file?subject={subject}&filename={target}"
        return jsonify({
            "found": True,
            "type": "document",
            "file_url": file_url,
            "filename": target
        })

    # No files found
    return jsonify({
        "found": False,
        "content": f"No study materials found in `{subject}`. Place PDF, DOCX, TXT, or JSON files."
    })

@app.route('/view_file', methods=['GET'])
def view_file():
    subject = request.args.get('subject')
    filename = request.args.get('filename')
    filepath = os.path.join(PRELOAD_FOLDER, subject, filename)
    if os.path.exists(filepath):
        return send_file(filepath)
    return "File not found", 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
