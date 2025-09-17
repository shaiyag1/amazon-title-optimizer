#!/usr/bin/env python3
"""
Debug runner for Streamlit app
This script helps run Streamlit with proper debugging support
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    # Ensure we're in the right directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Path to your Streamlit app
    streamlit_app = "StreamlitTools/main_st.py"
    
    # Check if the app exists
    if not Path(streamlit_app).exists():
        print(f"Error: {streamlit_app} not found!")
        return
    
    print(f"Running Streamlit app: {streamlit_app}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Python executable: {sys.executable}")
    
    # Run Streamlit
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            streamlit_app,
            "--server.port=8501",
            "--server.address=localhost",
            "--logger.level=debug"
        ], check=True)
    except KeyboardInterrupt:
        print("\nStreamlit app stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"Error running Streamlit: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
