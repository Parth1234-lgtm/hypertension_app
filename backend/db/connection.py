from pymongo import MongoClient
from dotenv import load_dotenv
import os
import certifi
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

load_dotenv()

def _sanitize_mongo_uri(uri: str) -> str:
    """
    Remove query options that can interfere with TLS settings.
    We apply TLS settings explicitly in code via SSLContext.
    """
    if not uri:
        return uri

    parts = urlsplit(uri)
    if not parts.query:
        return uri

    query_pairs = [(k, v) for (k, v) in parse_qsl(parts.query, keep_blank_values=True)]
    filtered = [
        (k, v)
        for (k, v) in query_pairs
        if k.lower() not in {"tlsallowinvalidcertificates", "tlsinsecure", "ssl"}
    ]
    new_query = urlencode(filtered, doseq=True)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


_raw_uri = os.getenv("MONGODB_URI", "")
_uri = _sanitize_mongo_uri(_raw_uri)
_allow_invalid = os.getenv("MONGODB_TLS_ALLOW_INVALID", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "y",
    "on",
}

client = MongoClient(
    _uri,
    tls=True,
    tlsCAFile=certifi.where(),
    tlsAllowInvalidCertificates=_allow_invalid,
    serverSelectionTimeoutMS=10_000,
    connectTimeoutMS=10_000,
    socketTimeoutMS=20_000,
)
db = client[os.getenv("DB_NAME", "hypertension_app")]

# 3 collections
medical_records = db["medical_records"]   # READ ONLY - doctor writes
patient_state = db["patient_state"]       # AGENT READ+WRITE each cycle
signals = db["signals"]                   # APPEND ONLY - chat + schedule status

def get_db():
    return db

def test_connection():
    try:
        client.admin.command("ping")
        print("MongoDB connected successfully")
    except Exception as e:
        # Avoid Unicode issues on Windows console encodings (cp1252).
        print(f"MongoDB connection failed: {e}")
        raise

if __name__ == "__main__":
    test_connection()