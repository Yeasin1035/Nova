import os
import tempfile
import uuid
from flask import Flask, request, jsonify, send_file, make_response
from gtts import gTTS
import openai

# Configure
app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")  # set this on Render

UPLOAD_DIR = tempfile.gettempdir()

# --- Helpers ---
def save_uploaded_file(field_name="file", allowed_exts=None):
    """
    Save incoming file from form-data under 'file' (or custom name).
    Return local path or raise ValueError.
    """
    if field_name not in request.files:
        raise ValueError("No file field in request")
    f = request.files[field_name]
    if f.filename == "":
        raise ValueError("Empty filename")
    # Basic extension check (optional)
    filename = f.filename
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if allowed_exts and ext not in allowed_exts:
        raise ValueError(f"Extension not allowed: {ext}")
    tmp_name = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{filename}")
    f.save(tmp_name)
    return tmp_name

def text_to_speech_file(text, lang="en", prefix="reply"):
    """
    Create an MP3 using gTTS and return the path.
    """
    # Use gTTS for simple, reliable MP3 generation
    safe_name = f"{prefix}_{uuid.uuid4().hex}.mp3"
    out_path = os.path.join(UPLOAD_DIR, safe_name)
    tts = gTTS(text=text, lang=lang, slow=False)
    tts.save(out_path)
    return out_path, safe_name

# --- Endpoints ---

@app.route("/stt", methods=["POST"])
def stt():
    """
    Upload form-data file field 'file' containing audio (wav/m4a/mp3).
    Returns JSON: { "text": "transcribed text" }
    """
    try:
        audio_path = save_uploaded_file("file", allowed_exts=None)
    except Exception as e:
        return jsonify({"error": "upload_failed", "detail": str(e)}), 400

    # If OpenAI key is missing, return a helpful error
    if not openai.api_key:
        os.remove(audio_path)
        return jsonify({"error": "no_api_key", "detail": "OPENAI_API_KEY not configured on server."}), 500

    try:
        # Use OpenAI whisper transcription endpoint (streaming or file-based)
        with open(audio_path, "rb") as af:
            resp = openai.Audio.transcriptions.create(
                file=af,
                model="gpt-4o-mini-transcribe" if False else "whisper-1"  # fallback to whisper-1 which is common
            )
        text = resp.get("text") if isinstance(resp, dict) else getattr(resp, 'text', None)
        if not text:
            text = resp.get("transcript") if isinstance(resp, dict) else ""
    except Exception as e:
        os.remove(audio_path)
        return jsonify({"error": "transcription_failed", "detail": str(e)}), 500

    os.remove(audio_path)
    return jsonify({"text": text})

@app.route("/chat", methods=["POST"])
def chat():
    """
    Body JSON: { "text": "...", "system": "optional system prompt" }
    Returns JSON: { "reply": "..." }
    """
    data = request.get_json(force=True, silent=True) or {}
    user_text = data.get("text", "")
    system_prompt = data.get("system", "You are Nova, a calm and friendly AI assistant.")

    if user_text == "":
        return jsonify({"error": "no_text"}), 400
    if not openai.api_key:
        # Server can still run without OpenAI key, but chat requires it
        return jsonify({"error": "no_api_key", "detail": "OPENAI_API_KEY not configured."}), 500

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini" if False else "gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            max_tokens=512
        )
        reply = response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return jsonify({"error": "chat_failed", "detail": str(e)}), 500

    return jsonify({"reply": reply})

@app.route("/tts", methods=["POST"])
def tts():
    """
    JSON body: { "text": "...", "lang": "en" }
    Returns: MP3 file (attachment) and header X-Reply-Filename with suggested name.
    """
    data = request.get_json(force=True, silent=True) or {}
    text = data.get("text", "")
    lang = data.get("lang", "en")

    if not text:
        return jsonify({"error": "no_text"}), 400

    try:
        mp3_path, suggested_name = text_to_speech_file(text, lang=lang, prefix="g")
        # send file and set header
        resp = make_response(send_file(mp3_path, mimetype="audio/mpeg"))
        resp.headers["X-Reply-Filename"] = suggested_name
        return resp
    except Exception as e:
        return jsonify({"error": "tts_failed", "detail": str(e)}), 500
    finally:
        # note: we leave file on disk briefly for send_file to read. It will be cleaned by system tmp or later jobs.
        pass

@app.route("/nova", methods=["POST"])
def nova_pipeline():
    """
    Full pipeline: accept audio file (form-data 'file'), transcribe -> chat -> tts.
    Returns: MP3 audio response with header X-Reply-Filename
    """
    # save upload
    try:
        audio_path = save_uploaded_file("file", allowed_exts=None)
    except Exception as e:
        return jsonify({"error": "upload_failed", "detail": str(e)}), 400

    if not openai.api_key:
        os.remove(audio_path)
        return jsonify({"error": "no_api_key", "detail": "OPENAI_API_KEY not configured."}), 500

    try:
        # 1) STT
        with open(audio_path, "rb") as af:
            stt_resp = openai.Audio.transcriptions.create(file=af, model="whisper-1")
        user_text = stt_resp.get("text") or stt_resp.get("transcript") or ""
        # 2) Chat
        system_prompt = "You are Nova, a smart, calm, and friendly AI assistant."
        chat_resp = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            max_tokens=512
        )
        reply_text = chat_resp["choices"][0]["message"]["content"].strip()
        # 3) TTS
        mp3_path, suggested_name = text_to_speech_file(reply_text, lang="en", prefix="reply")
        # send mp3 back
        resp = make_response(send_file(mp3_path, mimetype="audio/mpeg"))
        resp.headers["X-Reply-Filename"] = suggested_name
        return resp
    except Exception as e:
        return jsonify({"error": "pipeline_failed", "detail": str(e)}), 500
    finally:
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except:
            pass

@app.route("/", methods=["GET"])
def home():
    return "✅ Nova-Core server (minimal) is running."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
