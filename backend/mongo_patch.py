import urllib.parse
from pymongo import MongoClient
import json
import os
from datetime import datetime, timedelta

# Auto MongoDB Fallback Layer
try:
    _pw = urllib.parse.quote_plus("Ankara123***")
    MONGO_URI = f"mongodb+srv://ozas_admin:{_pw}@cluster0.r2ixfsx.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
    mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    mongo_db = mongo_client["banking_system"]
    db_collection = mongo_db["main_database"]
    USE_MONGO = True
except Exception as e:
    print("MongoDB Init Error:", e)
    USE_MONGO = False

global_audit_logs = []
credit_applications = []

def load_local_db() -> dict:
    global global_audit_logs, credit_applications
    full_db = {}
    
    # 1. Try Mongo
    if USE_MONGO:
        try:
            doc = db_collection.find_one({"_id": "legacy_ledger"})
            if doc:
                full_db = doc.get("data", {})
        except Exception as e:
            print("Mongo Load Error:", e)

    # 2. Local File Fallback
    if not full_db and os.path.exists(LOCAL_DB_PATH):
        try:
            with open(LOCAL_DB_PATH, "rb") as f:
                content = f.read()
                if content:
                    decrypted_data = cipher_suite.decrypt(content)
                    full_db = json.loads(decrypted_data.decode())
        except Exception:
            pass

    db = full_db.get("users") if "users" in full_db else full_db
    if not isinstance(db, dict):
        db = {}
    global_audit_logs = full_db.get("audit_logs", global_audit_logs)
    credit_applications = full_db.get("credits", credit_applications)
                    
    needs_save = False

    # --- SYSTEM ADMINISTRATIVE NODE (NEW POLICY) ---
    admin_id = "admin"
    if admin_id not in db:
        db[admin_id] = {
            "tc_identity": admin_id,
            "password": "0635",
            "full_name": "SYSTEM ADMIN",
            "iban": "TR3600064000000000000000ADMIN",
            "role": "SYSTEM_ADMIN",
            "is_admin": True,
            "balance": 99999999.0,
            "status": "ACTIVE",
            "transactions": [],
            "auditHistory": [
                {"user": admin_id, "action": "INITIAL_ADMIN_BOOT", "hash": "ADM_INIT_001", "outcome": "SUCCESS", "time": datetime.now().isoformat()},
            ],
            "ledgerHistory": []
        }
        needs_save = True

    # CLEANUP: Remove Legacy Root Account if exists Safely
    if "11111111110" in db:
        db.pop("11111111110", None)
        needs_save = True

    # Auto-Inject Test User (Berke) for Mobile Flow
    test_tc = "54802618970"
    if test_tc not in db:
        db[test_tc] = {
            "tc_identity": test_tc,
            "password": "0635",
            "full_name": "Berke Özdemir",
            "iban": "TR420006200000054802618970",
            "role": "CLIENT",
            "is_admin": False,
            "balance": 183459.11,
            "status": "ACTIVE",
            "hold_amount": 0.0,
            "transactions": [],
            "auditHistory": [
                {"user": test_tc, "action": "WEB_AUTH_LOGIN", "hash": "SEC_TOKEN_8892", "outcome": "SUCCESS", "time": datetime.now().isoformat()},
                {"user": test_tc, "action": "KYC_VERIFICATION", "hash": "KYC_OK_7721", "outcome": "APPROVED", "time": (datetime.now() - timedelta(days=2)).isoformat()}
            ],
            "ledgerHistory": [
                {"txid": "TX-9982", "desc": "OZAS INVESTMENT RETURN (MONTHLY)", "debit": 0, "credit": 12450.00, "move": 12450.00, "balance": 183459.11, "time": datetime.now().isoformat()},
                {"txid": "TX-9981", "desc": "SALARY PAYMENT - TECH CORP", "debit": 0, "credit": 43500.00, "move": 43500.00, "balance": 171009.11, "time": (datetime.now() - timedelta(days=1)).isoformat()},
                {"txid": "TX-9980", "desc": "ATM WITHDRAWAL - ISTANBUL/LEVENT", "debit": 1500.00, "credit": 0, "move": -1500.00, "balance": 127509.11, "time": (datetime.now() - timedelta(days=2)).isoformat()}
            ]
        }
        needs_save = True
    
    # Always ensure test user password is correct
    db[test_tc]["password"] = "0635"
    
    if needs_save:
        save_local_db(db)
        
    return db

def save_local_db(data: dict):
    full_db = {
        "users": data,
        "audit_logs": global_audit_logs,
        "credits": credit_applications
    }
    
    # 1. Save to Mongo
    if USE_MONGO:
        try:
            db_collection.update_one(
                {"_id": "legacy_ledger"},
                {"$set": {"data": full_db}},
                upsert=True
            )
        except Exception as e:
            print("Mongo Save Error:", e)

    # 2. Local File Backing (Encrypted)
    try:
        json_str = json.dumps(full_db, indent=4)
        encrypted_data = cipher_suite.encrypt(json_str.encode())
        with open(LOCAL_DB_PATH, "wb") as f:
            f.write(encrypted_data)
    except Exception as e:
        print(f"Error saving DB: {e}")
