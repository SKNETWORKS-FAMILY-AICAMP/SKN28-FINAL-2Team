@echo off
setlocal
cd /d "%~dp0.."
call conda activate dl_nlp_env
if errorlevel 1 (
  echo Failed to activate conda environment: dl_nlp_env
  pause
  exit /b 1
)
python -m streamlit run rag_test_frontend\app.py --server.port 8501
endlocal
