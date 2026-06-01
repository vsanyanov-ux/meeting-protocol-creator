import asyncio
import edge_tts
import os
import subprocess

VOICES = {
    "Иван": "ru-RU-DmitryNeural",
    "Анна": "ru-RU-SvetlanaNeural",
    "Сергей": "ru-RU-DmitryNeural"
}

async def amain():
    with open("demo_meeting_transcript.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    audio_files = []
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        voice = "ru-RU-DmitryNeural" # default
        if line.startswith("Иван"):
            voice = VOICES["Иван"]
            text = line.split(":", 1)[1].strip()
            communicate = edge_tts.Communicate(text, voice)
        elif line.startswith("Анна"):
            voice = VOICES["Анна"]
            text = line.split(":", 1)[1].strip()
            communicate = edge_tts.Communicate(text, voice)
        elif line.startswith("Сергей"):
            voice = VOICES["Сергей"]
            text = line.split(":", 1)[1].strip()
            # Try to make Sergey sound a bit different by lowering pitch
            communicate = edge_tts.Communicate(text, voice, pitch="-15Hz")
        else:
            text = line
            communicate = edge_tts.Communicate(text, voice)
            
        p = f"temp_narr_{i}.mp3"
        print(f"Narrating line {i} with {voice}...")
        
        await communicate.save(p)
        audio_files.append(p)
        
    print("Concatenating files with ffmpeg...")
    with open("inputs.txt", "w", encoding="utf-8") as f:
        for p in audio_files:
            f.write(f"file '{p}'\n")
            
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "inputs.txt", "-c", "copy", "demo_meeting.mp3"], check=True)
    
    print("Cleaning up temporary files...")
    for p in audio_files:
        os.remove(p)
    os.remove("inputs.txt")
    print("Done! Saved as demo_meeting.mp3")

if __name__ == "__main__":
    asyncio.run(amain())
