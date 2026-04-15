from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
from processor import get_video_id, fetch_transcript, analyze_with_gemini, get_available_languages

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Load multiple API keys for failover
def load_api_keys():
    """Load all available API keys from environment variables."""
    gemini_keys = []
    groq_keys = []
    
    # Load Gemini keys
    for i in range(1, 10):  # Support up to 9 backup keys
        key = os.environ.get(f"GEMINI_API_KEY_{i}", "") if i > 1 else os.environ.get("GEMINI_API_KEY", "")
        if key and key.strip():
            gemini_keys.append(key.strip())
    
    # Load Groq keys
    for i in range(1, 10):  # Support up to 9 backup keys
        key = os.environ.get(f"GROQ_API_KEY_{i}", "") if i > 1 else os.environ.get("GROQ_API_KEY", "")
        if key and key.strip():
            groq_keys.append(key.strip())
    
    print(f"\nLoaded {len(gemini_keys)} Gemini API key(s)")
    print(f"Loaded {len(groq_keys)} Groq API key(s)")
    
    return gemini_keys, groq_keys

GEMINI_API_KEYS, GROQ_API_KEYS = load_api_keys()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/languages", methods=["POST"])
def get_languages():
    """Get available languages for a video"""
    data = request.get_json(silent=True) or {}
    video_url = data.get("url", "").strip()

    if not video_url:
        return jsonify({"error": "No URL provided"}), 400

    video_id = get_video_id(video_url)
    if not video_id:
        return jsonify({"error": "Invalid YouTube URL"}), 400

    languages = get_available_languages(video_id)
    return jsonify({"languages": languages})


@app.route("/analyze", methods=["POST"])
def analyze_video():
    data = request.get_json(silent=True) or {}
    video_url = data.get("url", "").strip()
    language = data.get("language", "en").strip()  # Default to English

    print(f"\n{'='*60}")
    print(f"Analyze request - URL: {video_url[:50]}..., Language: {language}")
    print(f"{'='*60}")

    if not video_url:
        return jsonify({"error": "No URL provided"}), 400

    video_id = get_video_id(video_url)
    if not video_id:
        return jsonify({"error": "Invalid YouTube URL"}), 400

    # ── 1. Fetch transcript in selected language ─────────────────────────────
    print(f"Fetching transcript in language: {language}")
    transcript_text, transcript_error = fetch_transcript(video_id, language)
    if transcript_error:
        print(f"Transcript error: {transcript_error}")
        return jsonify({"error": transcript_error}), 422
    
    print(f"Transcript fetched successfully ({len(transcript_text)} chars)")

    # ── 2. Analyse with AI in selected language ──────────────────────────────
    print(f"Analyzing with AI in language: {language}")
    result, ai_error = analyze_with_gemini(transcript_text, GEMINI_API_KEYS, GROQ_API_KEYS, language)
    if ai_error:
        print(f"AI error: {ai_error}")
        return jsonify({"error": ai_error}), 502

    print(f"Analysis successful! Model used: {result.get('model_used')}")
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
