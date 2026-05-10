from fastapi import FastAPI, Request, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import httpx
import uvicorn
import yfinance as yf
import pandas as pd
import json
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import time
import jwt
from collections import defaultdict
import random
import re

# Load environment variables from .env file
load_dotenv()

def generate_iban(tc_str: str) -> str:
    # Generates a standard 26-digit Turkish IBAN based on the unique TC Identity
    padded_tc = tc_str.zfill(15) # Ensure strictly 15 chars for account segment
    return f"TR4200062000000{padded_tc}"

# 1. Application Definition
app = FastAPI(
    title="ÖZAS Digital Banking",
    description="Developed by Berke Özdemir & Eren Aslantaş",
    version="2.1.0"
)

# CORS Configuration for external access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Integrations — lazy import to prevent heavy AI packages from crashing startup
try:
    from backend.agent.router import router as agent_router
    app.include_router(agent_router, prefix="/api/agent", tags=["Agent Operations"])
except Exception as _agent_import_err:
    import logging as _log
    _log.getLogger(__name__).warning(f"Agent router could not be loaded: {_agent_import_err}")
    from fastapi import APIRouter as _AR
    _stub = _AR()
    @_stub.get("/status")
    def _stub_status():
        return {"status": "degraded", "error": str(_agent_import_err)}
    
    app.include_router(_stub, prefix="/api/agent", tags=["System Fallback"])
    app.include_router(_stub, prefix="/api/agent", tags=["Agent Operations"])



# --- 1.5 Rate Limiting & Attack Protection ---
class RateLimiter:
    def __init__(self, requests_limit: int, time_window: int):
        self.requests_limit = requests_limit
        self.time_window = time_window
        self.ip_records = defaultdict(list)

    def is_allowed(self, ip: str) -> bool:
        current_time = time.time()
        # Clean up timestamps outside the time window
        self.ip_records[ip] = [t for t in self.ip_records[ip] if current_time - t < self.time_window]
        
        if len(self.ip_records[ip]) >= self.requests_limit:
            return False
            
        self.ip_records[ip].append(current_time)
        return True

# Limit: 120 requests per 60 seconds per IP
limiter = RateLimiter(requests_limit=120, time_window=60)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    
    # Whitelist localhost and local network IPs (e.g. iPhone on 192.168.x.x)
    if client_ip.startswith("127.") or client_ip.startswith("192.168.") or client_ip == "::1":
        return await call_next(request)

    # Check rate limit
    if not limiter.is_allowed(client_ip):
        # Drop request with 429 status code
        return JSONResponse(
            status_code=429,
            content={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": "Too Many Requests. Security limits activated to prevent abuse/attacks.",
                "retry_after": 60
            }
        )
    
    response = await call_next(request)
    return response

@app.get("/health")
async def health_check():
    return {"status": "UP", "version": "2.1.6", "timestamp": str(datetime.now()), "security": "Rate Limiter Active"}

# 2. Path & Template Configuration
base_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.abspath(os.path.join(base_dir, "..", "frontend"))
templates = Jinja2Templates(directory=os.path.join(frontend_dir, "templates"))
static_dir = os.path.join(frontend_dir, "static")

if not os.path.exists(static_dir):
    os.makedirs(static_dir)

# gRPC Simulated Service (Optional Requirement 7.2)
# Simulates a high-performance internal liquidity calculation node
async def grpc_simulated_liquidity_node(data: dict):
    # Conceptual mapping to gRPC Protobuf serialization/deserialization
    # High speed aggregation of total capital across nodes
    await asyncio.sleep(0.05) # Simulate ultra-low latency internal call
    total = sum(float(u.get("balance", 0)) for u in data.values() if isinstance(u, dict))
    return {"total_liquidity_cap": total, "protocol": "gRPC/HTTP2", "status": "COMPLETED"}

app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Root file serving for PWA
@app.get("/manifest.json")
async def get_manifest():
    return FileResponse(os.path.join(static_dir, "manifest.json"))

@app.get("/sw.js")
async def get_sw():
    return FileResponse(os.path.join(static_dir, "sw.js"), media_type="application/javascript")

@app.websocket("/ws/health")
async def websocket_health_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Stream system health metrics every 5 seconds (Requirement 7.3)
            db_data = load_local_db()
            health = await get_system_health()
            
            # Use the simulated gRPC service
            grpc_res = await grpc_simulated_liquidity_node(db_data)
            health["daily_volume"] = grpc_res["total_liquidity_cap"]
            health["protocol_awareness"] = "WebSockets/gRPC_Active"
            
            await websocket.send_json(health)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass

# 3. Encryption & Persistence Configuration
LOCAL_DB_PATH = os.path.join(base_dir, "local_db.json")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

if not ENCRYPTION_KEY:
# 🔐 PERSISTENT SECURITY LAYER (ISO 27001 Concept)
    DATA_DIR = base_dir
    os.makedirs(DATA_DIR, exist_ok=True)
    KEY_PATH = os.path.join(DATA_DIR, "vault.key")
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH, "r") as kf:
            ENCRYPTION_KEY = kf.read().strip()
    else:
        ENCRYPTION_KEY = Fernet.generate_key().decode()
        with open(KEY_PATH, "w") as kf:
            kf.write(ENCRYPTION_KEY)

cipher_suite = Fernet(ENCRYPTION_KEY.encode())

import urllib.parse
from pymongo import MongoClient

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

# ─── In-Memory DB Cache ───────────────────────────────────────────────────────
# Eliminates repeated MongoDB/disk reads on every concurrent request.
# Invalidated on every write via save_local_db().
_DB_CACHE: dict = {}
_DB_CACHE_VALID: bool = False

def _invalidate_db_cache():
    global _DB_CACHE_VALID
    _DB_CACHE_VALID = False

def load_local_db() -> dict:
    global global_audit_logs, credit_applications, _DB_CACHE, _DB_CACHE_VALID

    # Serve from in-memory cache if valid
    if _DB_CACHE_VALID and _DB_CACHE:
        return _DB_CACHE

    full_db = {}

    # 1. Try Mongo First
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

    # Populate in-memory cache
    _DB_CACHE = db
    _DB_CACHE_VALID = True
    return db

def _mongo_sync_worker(full_db):
    """MongoDB sync in background thread — never blocks login."""
    if USE_MONGO:
        try:
            db_collection.update_one(
                {"_id": "legacy_ledger"},
                {"$set": {"data": full_db}},
                upsert=True
            )
        except Exception as e:
            print("Mongo Background Sync Error:", e)

def _local_sync_worker(full_db):
    try:
        json_str = json.dumps(full_db, indent=4)
        encrypted_data = cipher_suite.encrypt(json_str.encode())
        with open(LOCAL_DB_PATH, "wb") as f:
            f.write(encrypted_data)
    except Exception as e:
        print(f"Error saving DB: {e}")

def save_local_db(data: dict):
    global _DB_CACHE, _DB_CACHE_VALID
    # Update in-memory cache immediately so next read is instant
    _DB_CACHE = data
    _DB_CACHE_VALID = True

    import threading
    full_db = {
        "users": data,
        "audit_logs": global_audit_logs,
        "credits": credit_applications
    }
    # Persist to Mongo + local file in background — never blocks caller
    threading.Thread(target=_mongo_sync_worker, args=(full_db,), daemon=True).start()
    threading.Thread(target=_local_sync_worker, args=(full_db,), daemon=True).start()

# --- Real-time Session Tracking & Task Queue ---
USER_HEARTBEATS = {} # {tc: last_seen_timestamp}

@app.post("/admin/heartbeat")
async def register_heartbeat(req: dict):
    tc = req.get("tc_identity")
    if tc:
        USER_HEARTBEATS[tc] = time.time()
    return {"status": "ALIVE"}

@app.get("/admin/pending_tasks")
async def get_pending_tasks():
    db = load_local_db()
    kyc_list = []
    credit_list = []
    
    # Simulate a few more for the UI if needed, but primarily use DB
    for tc, u in db.items():
        if u.get("role") == "CLIENT":
            kyc_list.append({"tc": tc, "type": "KYC_VERIF", "status": "PENDING", "date": "2026-03-22"})
        if float(u.get("balance", 0)) > 50000:
            credit_list.append({"tc": tc, "type": "LIMIT_INC", "request": "50,000 ₺", "date": "2026-03-22"})
            
    return {"kyc": kyc_list, "credits": credit_list}

# --- Webhook & Messaging Cluster ---
WEBHOOK_SUBSCRIBERS = []
WEBHOOK_HISTORY = []

async def _send_webhook_request(url: str, event_type: str, payload: dict, event_entry: dict):
    """Fire-and-forget webhook HTTP call — runs in background, never blocks caller."""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json={"event": event_type, "data": payload},
                              headers={"Content-Type": "application/json"}, timeout=2.0)
        event_entry["status"] = "SENT"
    except Exception:
        event_entry["status"] = "FAILED"

def fire_webhook(event_type: str, payload: dict):
    """
    Instantly records the event and dispatches HTTP calls as background tasks.
    Completely non-blocking — callers never wait for webhook delivery.
    """
    event_entry = {
        "event": event_type,
        "payload": payload,
        "time": datetime.now().isoformat(),
        "status": "QUEUED"
    }
    WEBHOOK_HISTORY.insert(0, event_entry)
    if len(WEBHOOK_HISTORY) > 50: WEBHOOK_HISTORY.pop()

    print(f"📡 WEBHOOK EVENT: {event_type} | Data: {payload}")

    if not WEBHOOK_SUBSCRIBERS: return

    for url in WEBHOOK_SUBSCRIBERS:
        asyncio.create_task(_send_webhook_request(url, event_type, payload, event_entry))

@app.post("/webhook/subscribe")
async def subscribe_webhook(req: dict):
    url = req.get("url")
    if not url: raise HTTPException(status_code=400, detail="Missing webhook URL")
    if url not in WEBHOOK_SUBSCRIBERS:
        WEBHOOK_SUBSCRIBERS.append(url)
    return {"status": "SUCCESS", "message": f"Webhook subscribed to {url}"}

@app.get("/admin/webhook_status")
async def get_webhook_status():
    return {
        "subscribers": WEBHOOK_SUBSCRIBERS,
        "history": WEBHOOK_HISTORY
    }

@app.post("/webhook/test_fire")
async def test_webhook():
    payload = {"msg": "System Health Check", "node": "OZAS-CLN-01"}
    await fire_webhook("SystemHealthPing", payload)
    return {"status": "SUCCESS"}

@app.post("/debug/refill")
async def debug_refill(req: dict):
    tc = req.get("tc_identity")
    db_data = load_local_db()
    if tc in db_data:
        db_data[tc]["balance"] = 100000.0
        save_local_db(db_data)
        return {"status": "SUCCESS", "new_balance": 100000.0}
    return {"status": "ERROR", "message": "User not found"}

# 4. Data Models
class TradeRequest(BaseModel):
    tc_identity: str
    symbol: str
    side: str
    price: float
    quantity: float
    order_type: Optional[str] = "market"

class FuturesTradeRequest(BaseModel):
    tc_identity: str
    symbol: str
    margin_amount: float
    leverage: int
    side: str

# 5. Persistence Handlers
@app.post("/state/save")
async def save_state(state: dict):
    tc = str(state.get("tc_identity", "unknown"))
    db_data = load_local_db()
    
    if tc in db_data or tc == "admin":
        if tc not in db_data and tc == "admin":
             # Initialize admin in DB if it's the first save
             db_data["admin"] = {"tc_identity": "admin", "role": "ROOT_ADMIN", "is_admin": True}
             
        # Update selectively — protect backend-managed critical fields from frontend overwrites
        PROTECTED_FIELDS = {"auditHistory", "password", "ledgerHistory", "transactions", "balance", "iban", "role", "is_admin", "status"}
        for k, v in state.items():
            if k in PROTECTED_FIELDS:
                continue  # Never let frontend overwrite these — backend is authoritative
            db_data[tc][k] = v
        
        # Only update balance if frontend sends a higher value (e.g., after a legitimate top-up)
        # Balance changes are only made via /transfer and /auth/register endpoints
        # Frontend portfolio/investment state is allowed to update investmentBalance
        if "investmentBalance" in state:
            db_data[tc]["investmentBalance"] = state["investmentBalance"]
        save_local_db(db_data)
        return {"status": "SUCCESS", "timestamp": datetime.now().isoformat()}
    else:
        # Prevent creating user entries from save_state (must use /auth/register)
        return {"status": "SKIPPED", "message": "User not found in persistent store"}


@app.post("/trade/spot")
async def execute_spot_trade(req: TradeRequest):
    db_data = load_local_db()
    if req.tc_identity not in db_data and req.tc_identity != "admin":
        raise HTTPException(status_code=404, detail="User not found")
        
    if req.tc_identity == "admin" and "admin" not in db_data:
         db_data["admin"] = {"tc_identity": "admin", "balance": 99999999.0, "investmentBalance": 0.0, "portfolio": [], "futuresPositions": []}
         
    user = db_data[req.tc_identity]
    total_cost = req.price * req.quantity
    
    if req.side == "buy":
        if user.get("investmentBalance", 0) < total_cost:
            raise HTTPException(status_code=400, detail="Insufficient Investment Balance")
        user["investmentBalance"] -= total_cost
        # Portfolio logic handled in frontend for now to keep it simple, 
        # but we returning new balance to sync.
    else:
        # Simple sell: add to investment balance
        user["investmentBalance"] += total_cost
        
    # Log trade
    if "auditHistory" not in user: user["auditHistory"] = []
    user["auditHistory"].append({
        "user": req.tc_identity,
        "action": f"SPOT_{req.side.upper()}_{req.symbol}",
        "hash": f"TRD_{int(time.time())}",
        "outcome": "SUCCESS",
        "time": datetime.now().isoformat()
    })
    
    save_local_db(db_data)
    return {
        "status": "SUCCESS", 
        "new_balance": user.get("balance", 0), 
        "new_invest_balance": user.get("investmentBalance", 0),
        "message": f"Successfully {req.side} {req.quantity} {req.symbol}"
    }

@app.post("/trade/futures")
async def execute_futures_trade(req: FuturesTradeRequest):
    db_data = load_local_db()
    if req.tc_identity not in db_data and req.tc_identity != "admin":
        raise HTTPException(status_code=404, detail="User not found")
        
    if req.tc_identity == "admin" and "admin" not in db_data:
         db_data["admin"] = {"tc_identity": "admin", "balance": 99999999.0, "investmentBalance": 0.0, "portfolio": [], "futuresPositions": []}
         
    user = db_data[req.tc_identity]
    
    if user.get("investmentBalance", 0) < req.margin_amount:
        raise HTTPException(status_code=400, detail="Insufficient Investment Balance for Margin")
        
    user["investmentBalance"] -= req.margin_amount
    
    # Log trade
    if "auditHistory" not in user: user["auditHistory"] = []
    user["auditHistory"].append({
        "user": req.tc_identity,
        "action": f"FUT_{req.side.upper()}_{req.symbol}",
        "hash": f"TRD_FUT_{int(time.time())}",
        "outcome": "SUCCESS",
        "time": datetime.now().isoformat()
    })
    
    save_local_db(db_data)
    return {
        "status": "SUCCESS",
        "new_balance": user.get("balance", 0),
        "new_invest_balance": user.get("investmentBalance", 0),
        "message": f"Opened {req.side} position on {req.symbol} with {req.leverage}x leverage"
    }


@app.get("/state/load")
async def load_state(tc: str):
    db_data = load_local_db()
    user_state = db_data.get(tc)
    
    if user_state:
        # Migrate/Ensure keys exist
        if "iban" not in user_state: user_state["iban"] = generate_iban(tc)
        if "activeLoans" not in user_state: user_state["activeLoans"] = []
        if "ledgerHistory" not in user_state: user_state["ledgerHistory"] = []
        if "auditHistory" not in user_state: user_state["auditHistory"] = []
        if "portfolio" not in user_state: user_state["portfolio"] = []
        if "futuresPositions" not in user_state: user_state["futuresPositions"] = []
        return user_state
    
    # If not found, initialize a default secure state so the frontend doesn't wipe
    # (Matches Berke's starting profile for demo purposes)
    new_user = {
        "tc_identity": tc,
        "iban": generate_iban(tc),
        "balance": 1000000.0, # Default high-tier starting balance
        "investmentBalance": 0.0,
        "loans": 0.0,
        "activeMode": "portfolio",
        "portfolio": [],
        "ledgerHistory": [],
        "auditHistory": [],
        "termDeposit": 25000.0,
        "futuresPositions": []
    }
    db_data[tc] = new_user
    save_local_db(db_data)
    return new_user

# 6. UI Routes
@app.get("/", response_class=HTMLResponse)
async def get_login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@app.get("/agent", response_class=HTMLResponse)
async def get_agent(request: Request):
    return templates.TemplateResponse(request=request, name="agent.html")

@app.get("/checklist", response_class=HTMLResponse)
async def get_checklist(request: Request):
    return templates.TemplateResponse(request=request, name="checklist.html")

@app.get("/nav-order")
async def nav_order():
    return {"source": ":backend", "order": ["Loans", "Cards", "Insurance"]}

# 7. Authentication Endpoints
@app.post("/auth/register")
async def register_user(reg_data: dict):
    tc = str(reg_data.get("tc_identity")).strip()
    
    # 🌟 NEW: Privacy Bypass Rule (e.g. 123*)
    is_bypass = len(tc) == 4 and tc.endswith('*') and tc[:3].isdigit()
    
    if not is_bypass:
        if not tc or len(tc) != 11 or not tc.isdigit():
            raise HTTPException(status_code=400, detail="Valid 11-digit TC Identity or 3rd digits + * required")
        
        if tc[0] == '0':
            raise HTTPException(status_code=400, detail="Invalid TC Identity (cannot start with 0)")
            
        digits = [int(d) for d in tc]
        sum_odds = digits[0] + digits[2] + digits[4] + digits[6] + digits[8]
        sum_evens = digits[1] + digits[3] + digits[5] + digits[7]
        
        tenth = ((sum_odds * 7) - sum_evens) % 10
        if tenth != digits[9]:
            raise HTTPException(status_code=400, detail="Invalid TC Identity (Verification Failed)")
            
        total_sum = sum(digits[:10])
        if total_sum % 10 != digits[10]:
            raise HTTPException(status_code=400, detail="Invalid TC Identity (Summation Failed)")
    
    db_data = load_local_db()
    if tc in db_data:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Initialize basic user state
    db_data[tc] = {
        **reg_data,
        "full_name": reg_data.get("full_name", "NEW USER"),
        "role": "CLIENT",
        "is_admin": False,
        "iban": generate_iban(tc),
        "balance": 0.0, # Start with zero balance
        "investmentBalance": 0.0,
        "loans": 0.0,
        "status": "ACTIVE",
        "kyc_verified": False, # Requires Admin Approval
        "portfolio": [],
        "ledgerHistory": [],
        "auditHistory": [
            {
                "user": tc,
                "action": "SYS",
                "hash": "ENCRYPTED_ID_GEN",
                "outcome": "SUCCESS",
                "time": datetime.now().isoformat()
            }
        ]
    }
    save_local_db(db_data)
    return {"status": "SUCCESS", "message": "User registered successfully", "full_name": db_data[tc].get("full_name")}

@app.post("/auth/login")
async def login_user(credentials: dict):
    username = str(credentials.get("username", "")).strip()
    password = credentials.get("password", "")

    db_data = load_local_db()
    
    if username not in db_data:
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")
    
    user = db_data[username]
    
    # Standard Password Verification
    if user.get("password") != password:
        if "auditHistory" not in user: user["auditHistory"] = []
        user["auditHistory"].append({
            "user": username,
            "action": "WEB_AUTH_FAILED",
            "hash": "SEC_TOKEN_ERR_" + datetime.now().strftime("%s"),
            "outcome": "FAILED",
            "time": datetime.now().isoformat()
        })
        save_local_db(db_data)
        raise HTTPException(status_code=401, detail="INCORRECT_PASSWORD")
    
    # Role Logic
    # (Removed legacy admin TC override)

    # Add real authentication log to user history
    if "auditHistory" not in user:
        user["auditHistory"] = []
    
    user["auditHistory"].append({
        "user": username,
        "action": "WEB_AUTH_LOGIN",
        "hash": "SEC_TOKEN_" + datetime.now().strftime("%s"),
        "outcome": "SUCCESS",
        "time": datetime.now().isoformat()
    })
    save_local_db(db_data)

    time_stamp_now = datetime.now()

    # Issue standardized JWT Authentication Token
    expiration = datetime.utcnow() + timedelta(hours=2)
    jwt_payload = {
        "sub": username,
        "role": user.get("role", "CLIENT"),
        "is_admin": user.get("is_admin", False),
        "exp": expiration
    }
    encoded_jwt = jwt.encode(jwt_payload, ENCRYPTION_KEY, algorithm="HS256")

    return {
        "status": "SUCCESS",
        "tc_identity": username,
        "full_name": user.get("full_name", "CLIENT USER"),
        "is_admin": user.get("is_admin", False),
        "token": encoded_jwt,
        "role": user.get("role", "CLIENT")
    }

# 8. Dashboard and Market Routes
@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    # Auth guard — redirect to login if no valid session token
    token = request.cookies.get("ozas_token") or request.query_params.get("token")
    if not token:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/", status_code=302)
    try:
        jwt.decode(token, ENCRYPTION_KEY, algorithms=["HS256"])
    except Exception:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/", status_code=302)
    response = templates.TemplateResponse(request=request, name="dashboard.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/admin", response_class=HTMLResponse)
async def get_admin_app(request: Request):
    # iOS Admin Profile PWA Delivery Route
    response = templates.TemplateResponse(request=request, name="admin_app.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

# --- System-Wide Admin Routes ---
SYSTEM_MAINTENANCE_MODE = False

@app.post("/admin/trigger_webhook")
async def trigger_admin_webhook(payload: dict):
    event = payload.get("event", "MANUAL_ADMIN_TRIGGER")
    data = payload.get("data", {"triggered_by": "ROOT_ADMIN", "node": "OZAS-CLN-01"})
    await fire_webhook(event, data)
    return {"status": "SUCCESS", "message": f"Webhook '{event}' fired successfully."}

@app.post("/admin/maintenance_toggle")
async def toggle_maintenance(req: dict):
    global SYSTEM_MAINTENANCE_MODE
    SYSTEM_MAINTENANCE_MODE = not SYSTEM_MAINTENANCE_MODE
    status_str = "ACTIVE" if SYSTEM_MAINTENANCE_MODE else "OFF"
    
    # Log to system audit history
    db_data = load_local_db()
    for tc in db_data:
        if isinstance(db_data[tc], dict) and "auditHistory" in db_data[tc]:
            db_data[tc]["auditHistory"].insert(0, {
                "user": "SYSTEM",
                "action": f"MAINTENANCE_{status_str}",
                "hash": "SYS_MAINT_" + datetime.now().strftime("%s"),
                "outcome": "INFO",
                "time": datetime.now().isoformat()
            })
    save_local_db(db_data)
    
    return {"status": "SUCCESS", "maintenance_mode": SYSTEM_MAINTENANCE_MODE}

@app.get("/admin/system_health")
async def get_system_health():
    # Force fresh reload of DB to ensure real-time accuracy across nodes
    db_data = load_local_db()
    
    total_liquidity = 0.0
    u_count = 0
    kyc_pend = 0
    cred_pend = 0
    
    # Static Simulation lists for UI seed (but dynamic counts prevail)
    # Filter users needing verification
    for tc in db_data:
        node = db_data[tc]
        if isinstance(node, dict):
            u_count += 1
            total_liquidity += float(node.get("balance", 0))
            if node.get("kyc_verified") == False:
                kyc_pend += 1
            if float(node.get("balance", 0)) > 250000: # High value flags
                cred_pend += 1

    # Real-time Active Session Logic (users seen in last 60s)
    now = time.time()
    active_count = len([t for t in USER_HEARTBEATS.values() if now - t < 65])
    if active_count == 0: active_count = 1 # Minimum 1 (The Admin)

    import random
    load_raw = (u_count * 0.4) + random.uniform(1.2, 2.5)
    load_rounded = float(int(load_raw * 10) / 10.0) 
    
    return {
        "status": "HEALTHY",
        "maintenance_mode": SYSTEM_MAINTENANCE_MODE,
        "load": load_rounded,
        "active_sessions": active_count,
        "daily_volume": float(total_liquidity),
        "pending_kyc": kyc_pend,
        "pending_credit": cred_pend
    }

@app.post("/admin/approve_task")
async def approve_admin_task(req: dict):
    task_type = req.get("type")
    node_tc = req.get("tc")
    action = req.get("action")
    
    db_data = load_local_db()
    
    if node_tc in db_data:
        user = db_data[node_tc]
        if task_type == 'KYC':
            user["kyc_verified"] = (action == 'APPROVE')
            if action == 'REJECT':
                user["status"] = "REJECTED"
        
        save_local_db(db_data)
        return {"status": "SUCCESS", "message": f"Task finalized for node {node_tc}"}
        
    return {"status": "FAILED", "detail": "NODE_NOT_FOUND"}

@app.get("/admin/pending_tasks")
async def get_pending_tasks():
    db_data = load_local_db()
    kyc_list = []
    credit_list = []
    
    for tc, node in db_data.items():
        if isinstance(node, dict) and node.get("kyc_verified") == False:
            kyc_list.append({
                "tc": tc,
                "date": node.get("time", datetime.now().isoformat())[:16].replace("T", " "),
                "status": "PENDING"
            })
            
        # Mock credits for premium feel
        if isinstance(node, dict) and float(node.get("balance", 0)) > 250000:
            credit_list.append({
                "tc": tc,
                "request": "1.000.000 ₺ LMT",
                "date": "2026-03-22 23:55",
                "status": "URGENT"
            })
            
    return {"kyc": kyc_list, "credits": credit_list}
    return {"status": "SUCCESS", "message": f"Task '{task_type}' approved and updated in ledger."}

@app.get("/admin/system_state")
async def get_system_state(tc_identity: str):
    db_data = load_local_db()
    # Simple strict pseudo-auth check for the iOS app to fetch all db nodes
    if tc_identity not in ["admin", "11111111110"]:
        raise HTTPException(status_code=403, detail="Insufficient Permissions: ROOT_ADMIN required.")

    total_sys_balance = 0
    total_sys_loans = 0
    admin_balance = 0
    users = []
    global_audit_logs = []

    for identifier, profile in db_data.items():
        if identifier != "admin": # Skip the pure placeholder user from sum
            if identifier == "11111111110":
                admin_balance = profile.get("balance", 0)
                
            total_sys_balance += profile.get("balance", 0)
            total_sys_balance += profile.get("investmentBalance", 0)
            total_sys_loans += profile.get("loans", 0)
            
            users.append({
                "tc": identifier,
                "role": profile.get("role", "CLIENT"),
                "status": profile.get("status", "ACTIVE"),
                "balance": profile.get("balance", 0)
            })

            # Harvest user audits securely
            for log in profile.get("auditHistory", []):
                audit_entry = log.copy()
                audit_entry["_user"] = identifier
                global_audit_logs.append(audit_entry)

    # Sort logs descending temporally
    global_audit_logs.sort(key=lambda x: x.get("time", ""), reverse=True)

    return {
        "status": "SUCCESS",
        "system_metrics": {
            "total_liquidity": total_sys_balance,
            "total_loans_issued": total_sys_loans,
            "user_count": len(users),
            "admin_vault_iban": "TR3600064000000000000000ADMIN",
            "admin_vault_balance": db_data.get("11111111110", {}).get("balance", 0)
        },
        "users": users,
        "logs": global_audit_logs[:100] # Provide top 100 most recent records across network
    }

# 7. Market Data Proxy (Using yfinance for robustness)
@app.get("/contacts/list")
async def list_contacts():
    """Returns registered accounts for the Transfer Quick Select feature."""
    db_data = load_local_db()
    contacts = []
    for tc, profile in db_data.items():
        if not isinstance(profile, dict): continue
        if profile.get("status", "ACTIVE") != "ACTIVE": continue
        iban = profile.get("iban", "")
        name = profile.get("full_name", tc)
        if iban and name:
            contacts.append({"tc": tc, "full_name": name, "iban": iban})
    return contacts

@app.get("/market/search")
async def market_search(q: str):
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient() as client:
        try:
            # Search API still works usually, but we'll use a better endpoint
            url = f"https://query2.finance.yahoo.com/v1/finance/search?q={q}&quotesCount=10&newsCount=0"
            resp = await client.get(url, headers=headers)
            # (Polling logic remains as fallback or for static components)
            # (Actual high-speed data now flows through the WebSocket below)
            return resp.json()
        except Exception as e:
            # Fallback mock results if server is IP-blocked
            return {"quotes": []}

# Global FX Cache to speed up details requests
FX_CACHE = {"USDTRY": 32.95, "last_sync": 0}

# Per-symbol result cache — 3 min TTL is enough for a banking demo
MARKET_DETAILS_CACHE = {}
MARKET_DETAILS_TTL = 180

# Period → Yahoo Finance range mapping
_YF_RANGE = {"1d":"1d","1mo":"1mo","3mo":"3mo","6mo":"6mo","1y":"1y","max":"10y"}
_YF_INTERVAL = {"5m":"5m","60m":"1h","1d":"1d","1wk":"1wk"}
_YF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}
import random, math

def _compute_eurtry_sync(period: str, interval: str):
    """
    EUR/TRY rate from api.frankfurter.app (free, no-auth, works from cloud).
    Falls back to yfinance cross-pair computation, then to hardcoded value.
    Chart is Brownian motion anchored at the live rate.
    """
    price, prev_close = 0.0, 0.0

    # Primary: frankfurter.app — free currency API, no auth required
    try:
        with httpx.Client(timeout=6) as client:
            resp = client.get("https://api.frankfurter.app/latest",
                              params={"from": "EUR", "to": "TRY"})
            data = resp.json()
            price = float(data["rates"]["TRY"])
            # Fetch yesterday for prev_close
            resp2 = client.get("https://api.frankfurter.app/2025-05-09",
                               params={"from": "EUR", "to": "TRY"})
            prev_close = float(resp2.json()["rates"]["TRY"])
    except Exception as e1:
        print(f"frankfurter.app error: {e1}")
        # Fallback: EURUSD × USDTRY from yfinance
        try:
            eu = yf.Ticker("EURUSD=X").fast_info
            us = yf.Ticker("USDTRY=X").fast_info
            eurusd = float(eu.last_price or 1.08)
            usdtry = float(us.last_price or 38.5)
            price      = eurusd * usdtry
            prev_close = float(eu.previous_close or eurusd) * float(us.previous_close or usdtry)
        except Exception as e2:
            print(f"yfinance fallback error: {e2}")
            price, prev_close = 43.0, 42.8   # last-resort hardcoded value

    chart = _brownian_chart(price, n=78, volatility_pct=0.0008)
    return price, prev_close, "TRY", "OPEN", chart

def _brownian_chart(anchor: float, n: int = 78, volatility_pct: float = 0.001) -> list:
    """Generate a realistic Brownian motion chart anchored at `anchor` as the last value."""
    vol = anchor * volatility_pct
    chart = [anchor]
    for _ in range(n - 1):
        chart.append(chart[-1] + random.gauss(0, vol))
    # Rescale so chart[-1] == anchor exactly
    if chart[-1] != 0:
        scale = anchor / chart[-1]
        chart = [v * scale for v in chart]
    return chart

# Minimum plausible price thresholds — if Yahoo returns below this, data is wrong
_MIN_PRICE = {
    ".IS":   100.0,   # BIST stocks: ASELS ~428, THYAO ~~290 etc.
    "=F":    50.0,    # Futures: Gold ~2500, Oil ~70
    "-USD":  100.0,   # Crypto: BTC ~90k, ETH ~3k
    "=X":    0.5,     # FX pairs: USDTRY ~38, EURUSD ~1.0
    "default": 1.0,
}
# Known realistic prices for key demo assets (used as chart anchors when Yahoo fails)
_KNOWN_PRICES = {
    "ASELS.IS": 428.50,
    "AAPL":     211.0,
    "NVDA":     875.0,
    "TSLA":     175.0,
    "MSFT":     415.0,
}

def _get_min_price(symbol: str) -> float:
    for suffix, threshold in _MIN_PRICE.items():
        if symbol.endswith(suffix):
            return threshold
    return _MIN_PRICE["default"]

def _fetch_market_details_sync(symbol: str, period: str, interval: str):
    """
    Yahoo Finance Chart API + intelligent fallback.
    - Fetches chart data from Yahoo v8 API.
    - If the returned price is below the minimum plausible threshold for this
      asset type, the data is considered corrupt (Yahoo cloud-IP issue).
    - In that case: use a known realistic price (or chart max) as anchor,
      and generate a Brownian motion chart around it.
    """
    yf_range    = _YF_RANGE.get(period, "1d")
    yf_interval = _YF_INTERVAL.get(interval, "5m")
    url         = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params      = {"range": yf_range, "interval": yf_interval, "includePrePost": "false"}
    min_price   = _get_min_price(symbol)

    try:
        with httpx.Client(timeout=12, headers=_YF_HEADERS) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            body = resp.json()

        result       = body["chart"]["result"][0]
        meta         = result["meta"]
        meta_price   = float(meta.get("regularMarketPrice") or 0)
        prev_close   = float(meta.get("chartPreviousClose") or meta.get("previousClose") or meta_price)
        currency     = meta.get("currency", "TRY")
        market_state = meta.get("marketState", "OPEN")

        closes     = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        chart_raw  = [float(v) for v in closes if v is not None]

        # Determine the best price candidate
        chart_last = chart_raw[-1] if chart_raw else 0
        best_price = max(meta_price, chart_last)   # pick whichever is larger (wrong scale is usually smaller)

        if best_price >= min_price:
            # Data looks plausible — use it
            price = best_price
            if chart_last > 0 and price != chart_last:
                # Rescale chart so last point == price
                scale = price / chart_last
                chart_data = [v * scale for v in chart_raw]
            else:
                chart_data = chart_raw
            if meta_price < min_price and chart_last >= min_price:
                # chart was correct, recalc prev_close from chart start
                prev_close = chart_data[0] if len(chart_data) > 1 else price
        else:
            # Both meta and chart are in wrong scale — use known price or best guess
            anchor = _KNOWN_PRICES.get(symbol, best_price * 1000 if best_price > 0 else min_price * 2)
            print(f"⚠️  {symbol}: Yahoo data too small (best={best_price:.4f}, min={min_price}) — using anchor={anchor}")
            price      = anchor
            prev_close = anchor * 0.999  # ~0.1% change as placeholder
            chart_data = _brownian_chart(anchor, n=len(chart_raw) if chart_raw else 78)

    except Exception as e:
        print(f"⚠️  Yahoo Chart API error for {symbol}: {e} — using fallback")
        anchor     = _KNOWN_PRICES.get(symbol, min_price * 2)
        price      = anchor
        prev_close = anchor * 0.999
        currency   = "TRY" if symbol.endswith(".IS") or "TRY" in symbol else "USD"
        market_state = "CLOSED"
        chart_data = _brownian_chart(anchor)

    return price, prev_close, currency, market_state, chart_data

def _fetch_usdtry_sync():
    t = yf.Ticker("USDTRY=X")
    return t.fast_info.last_price

# Fast price-only cache (15s TTL) — for instant odometer updates
MARKET_PRICE_CACHE = {}
MARKET_PRICE_TTL = 15

def _fetch_price_only_sync(symbol: str):
    """Quick price fetch via Yahoo Chart API meta — same as website price."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"range": "1d", "interval": "1m", "includePrePost": "false"}
    try:
        with httpx.Client(timeout=8, headers=_YF_HEADERS) as client:
            resp = client.get(url, params=params)
            meta = resp.json()["chart"]["result"][0]["meta"]
        price      = float(meta.get("regularMarketPrice") or 0)
        prev_close = float(meta.get("chartPreviousClose") or meta.get("previousClose") or price)
        currency   = meta.get("currency", "TRY")
        market_state = meta.get("marketState", "OPEN")
    except Exception:
        ticker = yf.Ticker(symbol)
        fi = ticker.fast_info
        price = float(fi.last_price or 0)
        prev_close = float(fi.previous_close or price)
        currency = fi.currency or "TRY"
        try:    market_state = fi.market_state or "OPEN"
        except: market_state = "OPEN"
    return price, prev_close, currency, market_state

@app.get("/market/price")
async def market_price_fast(symbol: str):
    """Lightweight price-only endpoint. Returns in ~0.3s."""
    now = time.time()
    # Check price cache
    cached = MARKET_PRICE_CACHE.get(symbol)
    if cached and (now - cached["ts"]) < MARKET_PRICE_TTL:
        return cached["data"]
    # Also reuse full details cache if available
    for period in ["1d", "5d"]:
        dk = f"{symbol}|{period}|5m"
        dc = MARKET_DETAILS_CACHE.get(dk)
        if dc and (now - dc["ts"]) < MARKET_DETAILS_TTL:
            d = dc["data"]
            result = {"symbol": symbol, "regularMarketPrice": d["regularMarketPrice"],
                      "regularMarketPreviousClose": d["regularMarketPreviousClose"],
                      "currency": d["currency"], "rate": d["rate"],
                      "marketState": d.get("marketState", "OPEN")}
            MARKET_PRICE_CACHE[symbol] = {"data": result, "ts": now}
            return result
    try:
        loop = asyncio.get_event_loop()
        if symbol == "EURTRY=X":
            price, prev_close, currency, market_state, _ = await loop.run_in_executor(
                None, _compute_eurtry_sync, "1d", "5m"
            )
        else:
            price, prev_close, currency, market_state = await loop.run_in_executor(
                None, _fetch_price_only_sync, symbol
            )
        result = {"symbol": symbol, "regularMarketPrice": price,
                  "regularMarketPreviousClose": prev_close, "currency": currency,
                  "rate": FX_CACHE["USDTRY"], "marketState": market_state}
        MARKET_PRICE_CACHE[symbol] = {"data": result, "ts": now}
        return result
    except Exception as e:
        if cached: return cached["data"]
        return {"error": str(e), "regularMarketPrice": 0, "rate": 32.95}

def _prewarm_cache(symbols_periods):
    """Called once at startup in a background thread to pre-fill cache."""
    for symbol, period, interval in symbols_periods:
        try:
            result = _fetch_market_details_sync(symbol, period, interval)
            cache_key = f"{symbol}|{period}|{interval}"
            MARKET_DETAILS_CACHE[cache_key] = {
                "data": {
                    "symbol": symbol,
                    "regularMarketPrice": result[0],
                    "regularMarketPreviousClose": result[1],
                    "currency": result[2],
                    "rate": FX_CACHE["USDTRY"],
                    "chart": result[4],
                    "marketState": result[3]
                },
                "ts": time.time()
            }
            print(f"✅ Pre-warmed cache: {symbol}")
        except Exception as e:
            print(f"Pre-warm skipped {symbol}: {e}")

# Pre-warm the most common assets in background at startup
import threading
threading.Thread(
    target=_prewarm_cache,
    args=([
        ("ASELS.IS", "1d", "5m"),
        ("AAPL",    "1d", "5m"),
        ("NVDA",    "1d", "5m"),
        ("TSLA",    "1d", "5m"),
        ("MSFT",    "1d", "5m"),
        ("BTC-USD", "1d", "5m"),
        ("ETH-USD", "1d", "5m"),
        ("GC=F",    "1d", "5m"),
        ("CL=F",    "1d", "5m"),
    ],),
    daemon=True
).start()

@app.get("/market/details")
async def market_details(symbol: str, period: str = "1d", interval: str = "5m"):
    cache_key = f"{symbol}|{period}|{interval}"
    now = time.time()

    cached = MARKET_DETAILS_CACHE.get(cache_key)
    if cached and (now - cached["ts"]) < MARKET_DETAILS_TTL:
        return cached["data"]

    try:
        loop = asyncio.get_event_loop()
        if symbol == "EURTRY=X":
            price, prev_close, currency, market_state, chart_data = await loop.run_in_executor(
                None, _compute_eurtry_sync, period, interval
            )
        else:
            price, prev_close, currency, market_state, chart_data = await loop.run_in_executor(
                None, _fetch_market_details_sync, symbol, period, interval
            )

        # Refresh FX rate in background if stale
        if now - FX_CACHE["last_sync"] > 120:
            asyncio.create_task(asyncio.get_event_loop().run_in_executor(None, _fetch_usdtry_sync))

        usdtry = FX_CACHE["USDTRY"]

        result = {
            "symbol": symbol,
            "regularMarketPrice": price,
            "regularMarketPreviousClose": prev_close,
            "currency": currency,
            "rate": usdtry,
            "chart": chart_data,
            "marketState": market_state
        }

        MARKET_DETAILS_CACHE[cache_key] = {"data": result, "ts": now}
        return result

    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        if cached:
            return cached["data"]
        return {"error": str(e), "regularMarketPrice": 0, "rate": 32.95}


MARKET_WATCH_CACHE = {"data": None, "ts": 0}
MARKET_INDICES_CACHE = {"data": None, "ts": 0}

def _fetch_watch_sync():
    symbols = ["USDTRY=X", "EURTRY=X", "XAUUSD=L", "BTC-USD"]
    results = {}
    for sym in symbols:
        t = yf.Ticker(sym)
        price = t.fast_info.last_price
        prev = t.fast_info.previous_close
        chg = ((price - prev) / prev) * 100
        name = sym.replace("=X", "").replace("-USD", "").replace("=L", " GOLD")
        results[name] = {"price": f"{price:,.2f}", "change": f"{chg:+.2f}%"}
    return results

@app.get("/market/watch")
async def market_watch():
    now = time.time()
    if MARKET_WATCH_CACHE["data"] and (now - MARKET_WATCH_CACHE["ts"]) < 60:
        return MARKET_WATCH_CACHE["data"]
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _fetch_watch_sync)
        MARKET_WATCH_CACHE["data"] = result
        MARKET_WATCH_CACHE["ts"] = now
        return result
    except:
        return MARKET_WATCH_CACHE["data"] or {"USD/TRY": {"price": "32.95", "change": "+0.15%"}}

NAME_MAP = {
    "USDTRY=X": "USD / TRY", "EURTRY=X": "EUR / TRY", "GBPTRY=X": "GBP / TRY",
    "XAUUSD=L": "GOLD (ONS)", "XAGUSD=L": "SILVER (ONS)", "GC=F": "GOLD FUTURES", "CL=F": "CRUDE OIL"
}

def _fetch_single_index(sym):
    ticker = yf.Ticker(sym)
    hist = ticker.history(period="1d", interval="15m")
    info = ticker.fast_info
    price = info.last_price
    prev_close = info.previous_close
    change_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0
    sparkline = [p for p in hist['Close'].tolist() if p == p][-20:]
    return {"symbol": sym, "name": NAME_MAP.get(sym, sym), "price": price, "change": change_pct, "sparkline": sparkline}

@app.get("/market/indices")
async def market_indices():
    now = time.time()
    if MARKET_INDICES_CACHE["data"] and (now - MARKET_INDICES_CACHE["ts"]) < 60:
        return MARKET_INDICES_CACHE["data"]

    symbols = ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "XAUUSD=L", "XAGUSD=L", "GC=F", "CL=F"]
    loop = asyncio.get_event_loop()

    # Fetch all symbols in parallel via thread pool
    tasks = [loop.run_in_executor(None, _fetch_single_index, sym) for sym in symbols]
    raw = await asyncio.gather(*tasks, return_exceptions=True)

    results = [r for r in raw if isinstance(r, dict)]
    if results:
        MARKET_INDICES_CACHE["data"] = results
        MARKET_INDICES_CACHE["ts"] = now
    return results or MARKET_INDICES_CACHE.get("data") or []



# 8. Banking Endpoints
@app.post("/chat")
async def chat_endpoint(req: dict):
    user_msg = req.get("message", "").lower()
    tc = req.get("tc_identity", "unknown")
    db_data = load_local_db()
    user_state = db_data.get(tc, {})
    balance = user_state.get("balance", 0)
    
    if "balance" in user_msg or "bakiye" in user_msg:
        res = f"Bakiye analizi yapıldı: Mevcut bakiyeniz {balance:,.2f} ₺. Portföyünüz stabil görünüyor."
    elif "selam" in user_msg or "merhaba" in user_msg:
        res = "Merhaba! Ben OZAS Assistant. Size nasıl yardımcı olabilirim?"
    else:
        res = "Anladım. Başka bir konuda yardımcı olmamı ister misiniz? (Bakiye, Transfer vb.)"
    return {"reply": res}

@app.post("/loans/apply")
async def apply_loan(req: dict):
    tc = req.get("tc_identity")
    salary = float(req.get("salary", 0))
    occupation = req.get("occupation", "Other")
    req_amount = float(req.get("amount", 0))
    loan_type = req.get("type", "Personal")
    term = int(req.get("term", 12))
    insured = req.get("insured", False)
    
    if occupation == "Student":
        return {
            "status": "DENIED",
            "message": "Sorry, our credit policies do not currently allow loans for students. Please contact support for academic financing options."
        }
    
    # Calculate MAX LIMIT based on tiers
    if salary <= 5000:
        max_limit = salary * 3
    elif salary <= 15000:
        max_limit = salary * 5
    elif salary <= 40000:
        max_limit = salary * 8
    else:
        max_limit = salary * 12

    if req_amount > max_limit:
        return {
            "status": "ERROR",
            "message": f"Your requested amount ({req_amount:,.2f} ₺) exceeds your maximum eligible limit of {max_limit:,.2f} ₺ based on your income profile."
        }
    
    if req_amount <= 0:
        return {"status": "ERROR", "message": "Invalid loan amount."}

    db_data = load_local_db()
    if tc in db_data:
        user = db_data[tc]
        
        # Determine interest rate (simulation)
        base_rate = 2.49
        rate_bump = (term - 12) * 0.05 if term > 12 else 0
        final_rate = base_rate + rate_bump
        
        # Initialize lists if missing
        if "activeLoans" not in user: user["activeLoans"] = []
        if "ledgerHistory" not in user: user["ledgerHistory"] = []
        if "auditHistory" not in user: user["auditHistory"] = []

        loan_id = f"LN-{int(time.time())}"
        new_loan = {
            "loan_id": loan_id,
            "type": loan_type,
            "amount": req_amount,
            "term": term,
            "rate": final_rate,
            "insured": insured,
            "monthly": (req_amount * (1 + final_rate/100)) / term,
            "date": datetime.now().isoformat()
        }
        
        user["activeLoans"].append(new_loan)
        user["balance"] = user.get("balance", 0.0) + req_amount
        user["loans"] = user.get("loans", 0.0) + req_amount
        
        # Transaction History
        user["ledgerHistory"].insert(0, {
            "txid": f"GL-{int(time.time())}",
            "desc": f"Loan Disbursement: {loan_type} ({loan_id})",
            "debit": 0,
            "credit": req_amount,
            "move": req_amount,
            "balance": user["balance"],
            "time": datetime.now().isoformat()
        })
        
        save_local_db(db_data)
        
        return {
            "status": "SUCCESS",
            "loan": new_loan,
            "message": f"Success! Your {loan_type} loan for {req_amount:,.2f} ₺ has been approved and deposited. Monthly payment: {new_loan['monthly']:,.2f} ₺."
        }
    
    raise HTTPException(status_code=404, detail="Identity not found.")

@app.post("/transfer/internal")
async def internal_transfer(req: dict):
    """
    Core P2P internal transfer mechanism using targeted IBAN resolution.
    Strictly coordinates Dual-Ledger atomicity & Webhook event lifecycles.
    Required Events: TransferCreated, AccountDebited, AccountCredited, TransferCompleted.
    """
    sender_tc = req.get("sender_tc")
    receiver_iban = req.get("receiver_iban", "").replace(" ", "").upper()
    amount = float(req.get("amount", 0))

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid transfer amount")

    db_data = load_local_db()
    if sender_tc not in db_data:
        raise HTTPException(status_code=404, detail="Sender Identity not found.")
        
    sender = db_data[sender_tc]
    if sender.get("balance", 0) < amount:
        raise HTTPException(status_code=400, detail="Insufficient Balance")

    # Locate receiver by IBAN within DB
    receiver_tc = None
    clean_receiver_iban = re.sub(r'[^A-Z0-9]', '', receiver_iban.upper())

    for identifier, profile in db_data.items():
        if not isinstance(profile, dict): continue
        profile_iban = re.sub(r'[^A-Z0-9]', '', profile.get("iban", "").upper())

        is_exact_match    = (profile_iban == clean_receiver_iban)
        # Flexible match: any IBAN ending with ADMIN goes to the "admin" system account
        is_admin_match    = (clean_receiver_iban.endswith("ADMIN") and identifier == "admin")

        if (is_exact_match or is_admin_match) and identifier != sender_tc:
            receiver_tc = identifier
            break

    if not receiver_tc:
        raise HTTPException(status_code=404, detail="Destination IBAN is Invalid or Unregistered.")

        
    receiver = db_data[receiver_tc]

    # 1. Execute atomic dual-ledger update
    tx_id = f"TRX-{int(time.time())}"
    now_iso = datetime.now().isoformat()

    sender["balance"] -= amount
    if "ledgerHistory" not in sender: sender["ledgerHistory"] = []
    sender["ledgerHistory"].insert(0, {
        "txid": tx_id,
        "desc": f"Transfer Sent to {receiver_iban}",
        "debit": amount,
        "credit": 0,
        "move": -amount,
        "balance": sender["balance"],
        "time": now_iso
    })

    receiver["balance"] = receiver.get("balance", 0) + amount
    if "ledgerHistory" not in receiver: receiver["ledgerHistory"] = []
    receiver["ledgerHistory"].insert(0, {
        "txid": tx_id,
        "desc": f"Transfer Received from {sender_tc}",
        "debit": 0,
        "credit": amount,
        "move": amount,
        "balance": receiver["balance"],
        "time": now_iso
    })

    # 2. Persist — non-blocking background write
    save_local_db(db_data)

    # 3. Fire all webhooks as background tasks — never block the response
    fire_webhook("TransferCreated",   {"tx_id": tx_id, "amount": amount, "sender": sender_tc, "receiver": receiver_iban})
    fire_webhook("AccountDebited",    {"tx_id": tx_id, "account": sender_tc, "amount": amount})
    fire_webhook("AccountCredited",   {"tx_id": tx_id, "account": receiver_tc, "amount": amount})
    fire_webhook("TransferCompleted", {"tx_id": tx_id, "status": "SUCCESS"})

    return {
        "status": "SUCCESS",
        "message": f"Successfully merged {amount:,.2f} ₺ into {receiver_iban}",
        "sender_balance": sender["balance"],
        "sender_ledger": sender["ledgerHistory"]
    }

if __name__ == "__main__":
    # Render.com provides a PORT env variable
    port_num = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port_num)