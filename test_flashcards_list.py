import requests
import json

# Test listing individual flashcards
try:
    response = requests.get("http://localhost:8000/api/flashcards/list-individual")
    print(f"List Individual Flashcards - Status Code: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*50 + "\n")

# Test listing flashcard sets
try:
    response = requests.get("http://localhost:8000/api/flashcards/list")
    print(f"List Flashcard Sets - Status Code: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*50 + "\n")

# Test getting specific individual flashcard
try:
    response = requests.get("http://localhost:8000/api/flashcards/individual/1")
    print(f"Get Individual Flashcard - Status Code: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*50 + "\n")

# Test getting specific flashcard set
try:
    response = requests.get("http://localhost:8000/api/flashcards/1")
    print(f"Get Flashcard Set - Status Code: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
