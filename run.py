import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "true").lower() == "true",
        reload_dirs=[os.path.join(BASE_DIR, "app")],
    )