import requests
import json

# Test data for individual flashcard
test_flashcard = {
    "name": "Test Card",
    "topics": "Test Topic", 
    "flashcard": {
        "front": {
            "visual": "",
            "text": "What is 2+2?"
        },
        "back": "4"
    }
}

# Test saving individual flashcard
try:
    response = requests.post("http://localhost:8000/api/flashcards/save-individual", 
                           json=test_flashcard)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

# Test data for flashcard set
test_flashcard_set = {
    "name": "Test Set",
    "topics": "Test Topics",
    "flashcards": [
        {
            "front": {
                "visual": "",
                "text": "What is 3+3?"
            },
            "back": "6"
        }
    ]
}

# Test saving flashcard set
try:
    response = requests.post("http://localhost:8000/api/flashcards/save", 
                           json=test_flashcard_set)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
