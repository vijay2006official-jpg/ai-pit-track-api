import sys
import uvicorn

if __name__ == "__main__":
    print("[*] Starting AI Pit Track API on http://127.0.0.1:8000 ...")
    print("[*] API Documentation available at http://127.0.0.1:8000/docs")
    print("[*] Dashboard available at http://127.0.0.1:8000/dashboard")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
