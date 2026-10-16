"""Start NOCTURNE: python run.py [options]

   Options:
     dev      - Run both backend and frontend dev servers (requires npm)
     build    - Build frontend first, then start backend
     (none)   - Start backend server only (host/port from nocturne.toml)
"""
import subprocess
import sys
from pathlib import Path

import uvicorn

from app.config import cfg

def ensure_dependencies():
    """Install Python dependencies if needed."""
    import importlib.util
    required = ["fastapi", "itsdangerous"]
    missing = [pkg for pkg in required if importlib.util.find_spec(pkg) is None]
    if missing:
        print(f"Installing missing dependencies: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"])

def build_frontend():
    """Build the React frontend."""
    frontend = Path("frontend")
    if not frontend.exists():
        print("Error: frontend/ directory not found")
        sys.exit(1)

    dist = Path("web/dist/index.html")
    if dist.exists():
        print("Frontend is already built. Use 'npm run build' in frontend/ to rebuild.")
        return

    print("Building frontend...")
    subprocess.check_call(["npm", "install"], cwd=frontend)
    subprocess.check_call(["npm", "run", "build"], cwd=frontend)

def run_dev():
    """Run backend and frontend dev servers concurrently."""
    frontend = Path("frontend")
    if not frontend.exists():
        print("Error: frontend/ directory not found")
        sys.exit(1)

    print("Installing frontend dependencies...")
    subprocess.check_call(["npm", "install"], cwd=frontend)

    print("\nStarting NOCTURNE in development mode...")
    print(f"Backend: http://localhost:{cfg.app.port}")
    print("Frontend: http://localhost:5173")
    print("\nPress Ctrl+C to stop\n")

    backend = subprocess.Popen(
        [sys.executable, "-c",
         "import uvicorn; from app.config import cfg; "
         "uvicorn.run('app.web:app', host=cfg.app.host, port=int(cfg.app.port), proxy_headers=True, log_level='info')"],
        cwd=Path.cwd()
    )
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend
    )

    try:
        backend.wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        backend.terminate()
        frontend_proc.terminate()
        backend.wait(timeout=5)
        frontend_proc.wait(timeout=5)

if __name__ == "__main__":
    ensure_dependencies()

    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "dev":
            run_dev()
        elif cmd == "build":
            build_frontend()
            print("Frontend built successfully!")
            print(f"Starting backend on http://localhost:{cfg.app.port}")
            uvicorn.run("app.web:app", host=cfg.app.host, port=int(cfg.app.port), proxy_headers=True, log_level="info")
        else:
            print(f"Unknown option: {cmd}")
            print(__doc__)
            sys.exit(1)
    else:
        uvicorn.run("app.web:app", host=cfg.app.host, port=int(cfg.app.port), proxy_headers=True, log_level="info")
