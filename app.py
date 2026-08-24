import os
import uuid
from flask import Flask, request, jsonify, render_template, session, send_file
import json
import chromadb

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "campus_ai_secure_fallback_key")

PRELOAD_FOLDER = 'knowledge_base'

# Initialize ChromaDB (not used for AI now, but kept for future)
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="freshman_knowledge_base")

# Curriculum Blueprint Map
CURRICULUM = {
    "General Psychology": ["Introduction & Research Methods", "Biological Bases of Behavior", "Sensation & Perception", "Learning & Memory"],
    "Chemistry": ["Atomic Structure", "Chemical Bonding", "Stoichiometry", "Thermodynamics"],
    "History": ["World Civilizations", "The Industrial Revolution", "Modern Global Conflicts", "Contemporary History"],
    "Geography": ["Physical Geography", "Human & Cultural Geography", "Geographic Information Systems (GIS)", "Global Urbanization"]
}

# Ensure folders exist
for subject, subtopics in CURRICULUM.items():
    safe_subject = subject.replace(" ", "_").replace("(", "").replace(")", "")
    for subtopic in subtopics:
        folder_path = os.path.join(PRELOAD_FOLDER, safe_subject, subtopic.replace(" ", "_"))
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
    subtopic = data.get("subtopic", "")

    safe_subject = subject.replace(" ", "_").replace("(", "").replace(")", "")
    safe_subtopic = subtopic.replace(" ", "_")
    folder_path = os.path.join(PRELOAD_FOLDER, safe_subject, safe_subtopic)

    if not os.path.exists(folder_path):
        return jsonify({
            "found": False,
            "content": f"### No resource found\n\nPlace your files in:\n`knowledge_base/{safe_subject}/{safe_subtopic}/`"
        })

    # If the subtopic has "Questions" in name, try to load JSON quiz
    if "Questions" in subtopic:
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
                print(f"Error loading quiz: {e}")

    # Otherwise, look for documents
    files = [f for f in os.listdir(folder_path) if f.split('.')[-1].lower() in ['pdf', 'docx', 'txt'] and not f.startswith('.')]
    if files:
        target = files[0]
        file_url = f"/view_file?subject={safe_subject}&subtopic={safe_subtopic}&filename={target}"
        return jsonify({
            "found": True,
            "type": "document",
            "file_url": file_url,
            "filename": target
        })
    else:
        return jsonify({
            "found": False,
            "content": f"### No files found\n\nPlace a PDF, DOCX, TXT, or JSON in:\n`knowledge_base/{safe_subject}/{safe_subtopic}/`"
        })

@app.route('/view_file', methods=['GET'])
def view_file():
    subject = request.args.get('subject')
    subtopic = request.args.get('subtopic')
    filename = request.args.get('filename')
    filepath = os.path.join(PRELOAD_FOLDER, subject, subtopic, filename)
    if os.path.exists(filepath):
        return send_file(filepath)
    return "File not found", 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
