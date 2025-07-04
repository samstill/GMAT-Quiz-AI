#!/bin/bash

# Using the actual API key from the database
API_KEY="gmat_quiz_pMdj7bEp3fA64EASEWlIefOulcL4A5vvnDixw19zYLE"

# Create a quiz named "Verbal Practice" through the API (with authentication)
echo "Creating quiz with authentication..."
curl -X POST http://localhost:8000/api/quizzes/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"name": "Verbal Practice", "description": "Practice for the GMAT Verbal section", "time_limit": 60}'

# Check if the quiz was created (with authentication)
echo -e "\n\nChecking if the quiz was created:"
curl -X GET http://localhost:8000/api/quizzes/ \
  -H "X-API-Key: $API_KEY"

# Also check what's in the database directly
echo -e "\n\nChecking database directly:"
docker exec -it gmat-quiz-ai-backend-1 python -c "
import sqlite3
import os

# Check user databases
user_db_dir = '/app/user_databases'
if os.path.exists(user_db_dir):
    db_files = [f for f in os.listdir(user_db_dir) if f.endswith('.db')]
    for db_file in db_files:
        try:
            db_path = os.path.join(user_db_dir, db_file)
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM quizzes')
            quizzes = cursor.fetchall()
            print(f'Quizzes in {db_file}:', quizzes)
            conn.close()
        except Exception as e:
            print(f'Error with {db_file}:', e)
"
