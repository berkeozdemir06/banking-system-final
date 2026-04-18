import re

with open("backend/agent/router.py", "r") as f:
    text = f.read()

new_text = text.replace("def ingest_kap(req: IngestKAPRequest):", "def ingest_kap(req: IngestKAPRequest):\n    import traceback")
new_text = new_text.replace("return {\"ticker\": req.ticker, \"docs\": len(docs), \"chunks_added\": added}", "return {\"ticker\": req.ticker, \"docs\": len(docs), \"chunks_added\": added}\n    except Exception as e:\n        return {\"error\": str(e), \"trace\": traceback.format_exc()}")
with open("backend/agent/router.py", "w") as f:
    f.write(new_text)

