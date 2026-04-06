from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
import uuid
import os

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Nova is alive"}

@app.post("/process_audio/")
async def process_audio(file: UploadFile = File(...)):
    
    filename = f"temp_{uuid.uuid4()}.wav"
    
    with open(filename, "wb") as f:
        f.write(await file.read())

    print("Received audio")

    # Fake response for now
    response_text = "Hello, I am Nova."

    output_file = f"reply_{uuid.uuid4()}.txt"

    with open(output_file, "w") as f:
        f.write(response_text)

    os.remove(filename)

    return {"reply": response_text}
