@echo off
echo Starting Performance vs. Beta Dashboard...
start "" "http://localhost:8501"
"C:\Users\mbra\AppData\Local\Programs\Python\Python312\python.exe" -m streamlit run dashboard/streamlit_app.py --server.headless true --server.port 8501
pause
