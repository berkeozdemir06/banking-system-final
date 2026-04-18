import json
import os
from cryptography.fernet import Fernet

ENCRYPTION_KEY = "ItBWmqW7u-8nm8WBt2VzyOWPCkMsZMA8fv9cvJ4xtWc="
LOCAL_DB_PATH = "/Users/ozdemir/.gemini/antigravity/scratch/banking_app/local_db.json"

cipher_suite = Fernet(ENCRYPTION_KEY.encode())

def load_local_db():
    if not os.path.exists(LOCAL_DB_PATH):
        print("File not found")
        return
    
    with open(LOCAL_DB_PATH, "rb") as f:
        content = f.read()
        if not content:
            print("Empty file")
            return
        
        try:
            decrypted_data = cipher_suite.decrypt(content)
            data = json.loads(decrypted_data.decode())
            print(json.dumps(data, indent=4))
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    load_local_db()
