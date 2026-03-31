from fastapi import FastAPI, HTTPException
import psutil
import os
import subprocess
import uvicorn
import flet.fastapi as flet_fastapi
from pydantic import BaseModel
from typing import List, Optional

# Configuration
SCRIPTS_ROOT = os.environ.get("SCRIPTS_ROOT", "/home/user/main")

app = FastAPI()

class CommandRequest(BaseModel):
    command: str

@app.get("/api/metrics")
async def get_metrics():
    try:
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        return {"cpu": cpu, "ram": ram, "disk": disk}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/execute")
async def execute_command(req: CommandRequest):
    try:
        # Securely execute scripts/commands
        # NOTE: In production, you'd want more validation here.
        result = subprocess.run(req.command, shell=True, capture_output=True, text=True, timeout=30)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/scripts")
async def get_scripts():
    discovered = {}
    if not os.path.exists(SCRIPTS_ROOT):
        return discovered

    for root, dirs, files in os.walk(SCRIPTS_ROOT):
        for file in files:
            if file.endswith(".sh"):
                rel_path = os.path.relpath(root, SCRIPTS_ROOT)
                category = rel_path.upper() if rel_path != "." else "GENERAL"
                
                if category not in discovered:
                    discovered[category] = []
                
                full_path = os.path.join(root, file)
                discovered[category].append({
                    "name": file.replace(".sh", "").replace("_", " ").upper(),
                    "path": full_path
                })
    return discovered

# Import Flet app logic (we'll refactor app.py to expose the main function)
import app as flet_app

# Mount Flet app to FastAPI
# This allows the same server to host the web dashboard at /
app.mount("/", flet_fastapi.app(flet_app.main))

if __name__ == "__main__":
    port = int(os.environ.get("FLET_SERVER_PORT", 8550))
    uvicorn.run(app, host="0.0.0.0", port=port)
