@echo off
set "DB_URL=sqlite:///D:/班级ai/BD/LM_SJ/database/qa_politic.db"
set "STORAGE_PATH=./backend/storage_qa"
cd /d "D:\班级ai\BD\LM_SJ"
".venv\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010 >> backend\server-qa.log 2>> backend\server-qa.err.log
