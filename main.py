from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
import uuid
import os
import wave
import json
import requests
from gtts import gTTS
from vosk import Model, KaldiRecognizer

app = FastAPI()

# Load Vosk model (make sure folder name is "model")
model = Model("model")

@app.post("/process_audio/")
async def process_audio(file: UploadFile = File(...)):
    # Save uploaded audio
    audio_path = f"temp_{uuid.uuid4()}.wav"
    with open(audio_path, "wb") as f:
        f.write(await file.read())

    # 🔥 Speech-to-text using Vosk
    wf = wave.open(audio_path, "rb")
    rec = KaldiRecognizer(model, wf.getframerate())

    text = ""

    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text += result.get("text", "")

    final_result = json.loads(rec.FinalResult())
    text += final_result.get("text", "")

    if text.strip() == "":
        text = "Hello Nova"

    print("User said:", text)

    # 🔥 Send to Ollama
    ollama_url = "http://localhost:11434/api/generate"
    payload = {
        "model": "mistral",
        "prompt": text,
        "stream": False
    }

    try:
        response = requests.post(ollama_url, json=payload)
        reply_text = response.json()["response"]
    except:
        reply_text = "Sorry, my brain is offline right now."

    print("Nova says:", reply_text)

    # 🔥 Text-to-speech
    output_audio = f"reply_{uuid.uuid4()}.mp3"
    tts = gTTS(reply_text)
    tts.save(output_audio)

    # Clean up input file
    os.remove(audio_path)

    return FileResponse(
        output_audio,
        media_type="audio/mpeg",
        filename="nova_reply.mp3"
    )
