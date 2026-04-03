from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
import openai
import uuid
import os
from gtts import gTTS

app = FastAPI()

# Set your OpenAI API key here
openai.api_key = "YOUR_OPENAI_API_KEY"

@app.post("/process_audio/")
async def process_audio(file: UploadFile = File(...)):
    # Save uploaded audio
    audio_path = f"temp_{uuid.uuid4()}.wav"
    with open(audio_path, "wb") as f:
        f.write(await file.read())
    
    # Transcribe audio
    transcription = openai.Audio.transcriptions.create(
        model="whisper-1",
        file=open(audio_path)
    )
    text = transcription["text"]

    # ChatGPT response
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": text}]
    )
    reply_text = response["choices"][0]["message"]["content"]

    # Convert reply to audio (TTS)
    tts = gTTS(reply_text)
    output_audio = f"reply_{uuid.uuid4()}.mp3"
    tts.save(output_audio)

    # Clean up uploaded audio
    os.remove(audio_path)

    # Return audio file to ESP32
    return FileResponse(output_audio, media_type="audio/mpeg")
