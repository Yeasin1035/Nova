from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
import uuid
import os
from gtts import gTTS
import requests

app = FastAPI()

@app.post("/process_audio/")
async def process_audio(file: UploadFile = File(...)):
    # Save uploaded audio
    audio_path = f"temp_{uuid.uuid4()}.wav"
    with open(audio_path, "wb") as f:
        f.write(await file.read())

    # Fake transcription
    text = "Hello Nova"

    # Send to Ollama
    ollama_url = "http://localhost:11434/api/generate"
    payload = {
        "model": "mistral",
        "prompt": text,
        "stream": False
    }

    response = requests.post(ollama_url, json=payload)
    reply_text = response.json()["response"]

    # Convert reply to speech
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
