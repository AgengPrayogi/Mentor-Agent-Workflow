# code_runner_service.py
from fastapi import FastAPI
import subprocess, tempfile

app = FastAPI()

@app.post("/run")
def run_code(payload: dict):
    code = payload["code"]
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        path = f.name
    try:
        result = subprocess.run(
            ["python3", path], capture_output=True, text=True, timeout=5
        )
        return {"stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Timeout: kode jalan >5 detik"}