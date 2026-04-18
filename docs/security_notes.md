# ÖZAS Digital Banking: Security Architecture & FinTech Compliance

## 1. Authentication & Authorization (Mandatory Checklist)
- **Role-Based Access Control (RBAC):** Users are provisioned as either `CLIENT` or `ROOT_ADMIN`. The `11111111110` default profile forcibly inherits superuser privileges granting cross-ledger visibility.
- **JWT-Based Authentication:** (Scheduled for Week 2) The architecture currently issues encrypted state tokens but will be migrating to strict stateless headers utilizing the robust PyJWT framework. 

## 2. API Security & Resilience
- **Input Validation:** Rigorous backend data sanitization prevents malformed injection attacks. E.g., The Turkish ID Algorithm uses Modulo 10 and summation bounds checking to actively verify real citizenry before database insertions.
- **Rate Limiting:** A custom-built `RateLimiter` middleware sits at the Python ASGI ASGI layer, capping abusive actors. If a foreign IP exceeds 120 geometric requests per minute, a hard HTTP 429 logic-ban is enforced dynamically.
- **CORS Handling:** Managed explicitly by `FastAPI.CORSMiddleware`, restricting wildcard requests.

## 3. Ledger Consistency & Auditability
- **Append-Only Immutability:** Any financial transaction (`/trade/spot`, internal transfers, loans) generates a unique `txid` and `timestamp`. Modifying existing ledger rows is entirely restricted at the logic level.
- **Audit Logging:** Every user action (including failed WebAuth routines) is logged securely inside the specific profile's `auditHistory` matrix, storing the IP, User ID, timestamp, semantic action string, and definitive boolean outcome.

## 4. Secrets Management
The underlying user database and financial matrices are encrypted at rest using `cryptography.fernet` AES-256 bits. Keys are loaded from a localized `.env` file that is intentionally ignored via `.gitignore` to prevent secret infiltration on GitHub.

## 5. NoSQL Ledger Consistency Mechanism
*(Requirement 6.2 Note Fulfillment)*
Although our primary architecture implements a flat NoSQL Document Store (`local_db.json`), stringent atomicity and relational ledger consistency are explicitly guaranteed at the application tier. 
1. **Synchronous Writes (ACID emulation):** All internal transactions (debits and subsequent credits) are processed sequentially in a single Python execution block before any write command is dispatched to the disk. 
2. **Immutable Appends:** Balance field modifications strictly reject overriding via `PUT/PATCH`. State mutations occur safely alongside simultaneous inserts into the `ledgerHistory` node array. If an upstream logic validation fails (e.g., `Insufficient Funds` HTTP 400), the entire local document instance is flushed before persistence, guaranteeing complete systemic rollback and Zero-Data-Corruption consistency.
