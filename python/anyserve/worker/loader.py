import sys
import os
import importlib
from typing import Optional

def load_app(app_str: str):
    """
    Loads the application object from a string format 'module:attribute'.
    Example: 'main:app' imports 'main' and retrieves 'app'.
    """
    if ":" not in app_str:
        # Fallback: if no attribute allowed, maybe default? 
        # But standard is module:attr
        raise ValueError(f"Invalid app string '{app_str}'. Must be in format 'module:attribute'")
    
    module_name, app_name = app_str.split(":", 1)
    
    # Ensure current directory is in path (like uvicorn)
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
        
    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        # Try adjusting path if module is inside a folder?
        # But sys.path.insert(0, cwd) usually handles 'examples.user_app'
        raise ImportError(f"Could not import module '{module_name}': {e}")
        
    try:
        app = getattr(module, app_name)
    except AttributeError:
        raise AttributeError(f"Module '{module_name}' has no attribute '{app_name}'")
        
    return app

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m anyserve_worker.loader <module:app>", file=sys.stderr)
        sys.exit(1)
        
    app_str = sys.argv[1]
    print(f"[Loader] Loading application '{app_str}'...", file=sys.stderr)
    
    try:
        app = load_app(app_str)
        
        # Verify it has a serve method
        if not hasattr(app, 'serve'):
             raise AttributeError(f"Object '{app_str}' is not a valid Worker application (missing serve method)")
             
        # Execute serve
        # This blocks until server stops
        app.serve()
        
    except Exception as e:
        print(f"[Loader] Error loading application: {e}", file=sys.stderr)
        sys.exit(1)
