import requests
import json

# Test deleting individual flashcard (if it exists)
try:
    # First create a test flashcard to delete
    test_card = {
        "name": "To Delete Card", 
        "topics": "Test",
        "flashcard": {
            "front": {"visual": "", "text": "Delete me"},
            "back": "This will be deleted"
        }
    }
    
    create_response = requests.post("http://localhost:8000/api/flashcards/save-individual", json=test_card)
    if create_response.status_code == 201:
        card_id = create_response.json()["id"]
        print(f"Created test card with ID: {card_id}")
        
        # Now delete it
        delete_response = requests.delete(f"http://localhost:8000/api/flashcards/delete-individual/{card_id}")
        print(f"Delete Individual Flashcard - Status Code: {delete_response.status_code}")
        print(f"Response: {delete_response.text}")
    else:
        print(f"Failed to create test card: {create_response.text}")
        
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*50 + "\n")

# Test deleting flashcard set (if it exists)  
try:
    # First create a test flashcard set to delete
    test_set = {
        "name": "To Delete Set",
        "topics": "Test", 
        "flashcards": [
            {
                "front": {"visual": "", "text": "Delete me set"},
                "back": "This set will be deleted"
            }
        ]
    }
    
    create_response = requests.post("http://localhost:8000/api/flashcards/save", json=test_set)
    if create_response.status_code == 201:
        set_id = create_response.json()["id"]
        print(f"Created test set with ID: {set_id}")
        
        # Now delete it
        delete_response = requests.delete(f"http://localhost:8000/api/flashcards/delete/{set_id}")
        print(f"Delete Flashcard Set - Status Code: {delete_response.status_code}")
        print(f"Response: {delete_response.text}")
    else:
        print(f"Failed to create test set: {create_response.text}")
        
except Exception as e:
    print(f"Error: {e}")
