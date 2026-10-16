# Run Script and Frontend Backend Integration Fixes

## Issues Fixed

### 1. **Run Script Dependency Management**
- **Problem**: The `run.py` script didn't verify that Python dependencies were installed
- **Solution**: Added `ensure_dependencies()` function that checks for required packages and installs them if missing using `pip install -r requirements.txt`

### 2. **Virtual Environment Handling**
- **Problem**: Running `python run.py` might use the system Python instead of the project's virtual environment
- **Solution**: 
  - Created `run.sh` shell script that automatically sources the virtual environment before running Python
  - The script creates `.venv` if it doesn't exist
  - Works on both Unix/macOS and can be adapted for Windows

### 3. **Frontend Build Automation**
- **Problem**: No easy way to rebuild the frontend or run frontend dev server alongside the backend
- **Solution**: Added three run modes to `run.py`:
  - `python run.py` - Start backend only (production mode)
  - `python run.py dev` - Run both backend and frontend dev servers concurrently
  - `python run.py build` - Build frontend first, then start backend

### 4. **Frontend Development Workflow**
- **Problem**: Developers needed to manually start two terminals (one for backend, one for frontend)
- **Solution**: Added `run_dev()` function that:
  - Ensures npm dependencies are installed
  - Starts the FastAPI backend on port 8080
  - Starts the Vite dev server on port 5173
  - Proxies API requests to the backend in development

### 5. **Frontend Build Directory Structure**
- **Status**: No issues found - the setup is correct:
  - Frontend source: `frontend/` (React + Vite)
  - Frontend build output: `web/dist/` (built by `npm run build`)
  - Backend serves built frontend from `web/dist/`

## Testing Results

✅ Backend starts and serves the API correctly
✅ Frontend HTML is properly served with built JavaScript
✅ API endpoints respond correctly (tested `/api/meta`, `/api/health`)
✅ Frontend and backend integration works as expected
✅ Both `run.py` and `run.sh` scripts work properly

## Usage

**Quick start (recommended):**
```bash
./run.sh                  # Starts backend server
./run.sh dev             # Starts backend + frontend dev servers
./run.sh build           # Builds frontend, then starts backend
```

**Alternative (manual):**
```bash
source .venv/bin/activate
pip install -r requirements.txt
python run.py            # Backend only
python run.py dev        # Backend + frontend dev
python run.py build      # Build frontend, then backend
```

## Files Modified

1. **run.py** - Enhanced with dependency checking and dev/build modes
2. **run.sh** - New shell script wrapper for easy virtual environment handling
3. **README.md** - Updated with new usage instructions

## Architecture Notes

- Backend: FastAPI on 0.0.0.0:8080
- Frontend (dev): Vite on localhost:5173 with API proxy to backend
- Frontend (production): Built into `web/dist/` and served by FastAPI
- All configuration: `nocturne.toml`
