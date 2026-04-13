from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore, auth
import google.generativeai as genai
import os
import json

app = Flask(__name__)
CORS(app)

# Firebase setup
cred = credentials.Certificate("izi-firebase-key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Gemini setup
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# ───── SIGNUP ─────
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    try:
        user = auth.create_user(
            email=data["email"],
            password=data["password"]
        )

        db.collection("users").document(user.uid).set({
            "name": data["name"],
            "email": data["email"]
        })

        return jsonify({"status": "created", "uid": user.uid})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ───── LOGIN ─────
@app.route("/login", methods=["POST"])
def login():
    import requests

    data = request.json
    api_key = os.environ.get("FIREBASE_WEB_API_KEY")

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"

    res = requests.post(url, json={
        "email": data["email"],
        "password": data["password"],
        "returnSecureToken": True
    })

    r = res.json()

    if "localId" in r:
        uid = r["localId"]
        user = db.collection("users").document(uid).get().to_dict()

        return jsonify({
            "status": "ok",
            "uid": uid,
            "name": user.get("name", "")
        })

    return jsonify({"error": "Invalid login"}), 401


# ───── SAVE PROFILE ─────
@app.route("/save-profile", methods=["POST"])
def save_profile():
    data = request.json
    uid = data["uid"]

    db.collection("users").document(uid).update({
        "age": data["age"],
        "interests": data["interests"],
        "restrictions": data["restrictions"],
        "looking_for": data["looking_for"]
    })

    return jsonify({"status": "saved"})


# ───── GET OPPORTUNITIES (AI) ─────
@app.route("/get-opportunities", methods=["POST"])
def get_opportunities():
    data = request.json
    uid = data["uid"]

    user = db.collection("users").document(uid).get().to_dict()

    prompt = f"""
You are izi, an app helping first-generation students.

User:
Age: {user.get('age')}
Interests: {', '.join(user.get('interests', []))}
Restrictions: {', '.join(user.get('restrictions', []))}
Looking for: {', '.join(user.get('looking_for', []))}

Return EXACTLY 6 opportunities as JSON array.

Each must include:
- title
- type (scholarship, job, internship, competition, study)
- why_fit (1 sentence, MUST reference user info)
- link (realistic URL)

ONLY RETURN JSON.
"""

    response = model.generate_content(prompt)

    try:
        results = json.loads(response.text)
    except:
        results = []

    return jsonify({"opportunities": results})


if __name__ == "__main__":
    app.run(debug=True)