# Allow a simple `python main.py` entry point, mirroring DEFAULT paths.
from pathlib import Path
import os

os.chdir(Path(__file__).parent.parent)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("chatbot.app:app", host="0.0.0.0", port=7860)