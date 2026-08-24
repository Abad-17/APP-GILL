import os
import sys
import streamlit.web.cli as stcli

def main():
    # PyInstaller crea una carpeta temporal en sys._MEIPASS al empaquetar
    if getattr(sys, 'frozen', False):
        dirname = sys._MEIPASS
    else:
        dirname = os.path.dirname(__file__)
        
    script_path = os.path.join(dirname, "app.py")
    
    # Inyectamos los argumentos directamente al sistema
    sys.argv = ["streamlit", "run", script_path, "--global.developmentMode=false"]
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()