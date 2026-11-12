"""
DocuMind AI - Comprehensive Authentication Security & Multi-Tenant Isolation Tests.
Validates:
1. Unauthenticated request rejection (401)
2. Malformed token header rejection (401)
3. Algorithm whitelist enforcement: alg="none" rejected (401)
4. Algorithm whitelist enforcement: untrusted alg="HS512" rejected (401)
5. Tampered token signature rejection (401)
6. Expired token rejection (401)
7. Invalid audience claim rejection (401)
8. Invalid issuer claim rejection (401)
9. Missing subject (sub) claim rejection (401)
10. Valid token acceptance & database user auto-provisioning (200)
11. User A accessing own document (200)
12. User B isolated from User A's document (404)
13. User B isolated from User A's document download (404)
14. User B isolated from User A's document deletion (404)
15. User B document listing tenant isolation
16. User B chat query document ownership validation (404)
17. User B conversation access and deletion isolation (404)
18. WebSocket: initial message requirement (rejection of unauthenticated frames)
19. WebSocket: rejection of invalid tokens with code 1008
20. WebSocket: successful authentication and registration
21. WebSocket: tenant-isolated broadcast status delivery
22. Destructive /reset endpoint protection (401 unauth / 403 auth)
23. Preservation of existing development user data
"""

import os
import sys
import time
import uuid
import json
import asyncio
import jwt
import httpx

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Configure test environment settings
TEST_JWT_SECRET = "test-secret-at-least-32-chars-long-1234567890abcdef"
TEST_SUPABASE_URL = "https://test-project.supabase.co"
os.environ["SUPABASE_JWT_SECRET"] = TEST_JWT_SECRET
os.environ["SUPABASE_URL"] = TEST_SUPABASE_URL
os.environ["SUPABASE_JWT_ALGORITHM"] = "HS256"
os.environ["ALLOW_DEV_AUTH"] = "False"
os.environ["ENABLE_RESET_ENDPOINT"] = "False"

from app.main import app
from config import settings
from app.database.local_db import LocalDB, _get_conn
from app.middleware.auth import DEV_USER_ID, verify_jwt_token
from app.services.websocket_manager import get_connection_manager

settings.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
settings.SUPABASE_URL = TEST_SUPABASE_URL
settings.SUPABASE_JWT_ALGORITHM = "HS256"
settings.ALLOW_DEV_AUTH = False
settings.ENABLE_RESET_ENDPOINT = False


def create_test_jwt(
    user_id: str,
    email: str,
    expires_in: int = 3600,
    secret: str = TEST_JWT_SECRET,
    aud: str = "authenticated",
    iss: str = f"{TEST_SUPABASE_URL}/auth/v1",
    algorithm: str = "HS256",
    custom_headers: dict = None,
) -> str:
    """Generate a signed test JWT."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "aud": aud,
        "iss": iss,
        "iat": now,
        "exp": now + expires_in,
        "role": "authenticated",
    }
    headers = custom_headers or {}
    return jwt.encode(payload, secret, algorithm=algorithm, headers=headers)


async def run_all_security_tests():
    print("=" * 70)
    print("DocuMind AI: Comprehensive Auth Security & Tenant Isolation Suite")
    print("=" * 70)

    db = LocalDB()
    user_a_id = str(uuid.uuid4())
    user_a_email = "usera@security.test"
    token_a = create_test_jwt(user_a_id, user_a_email)

    user_b_id = str(uuid.uuid4())
    user_b_email = "userb@security.test"
    token_b = create_test_jwt(user_b_id, user_b_email)

    results = []

    def record(name: str, passed: bool, detail: str = ""):
        status = "PASS" if passed else "FAIL"
        results.append((name, passed, detail))
        print(f"[{status}] {name}{f': {detail}' if detail else ''}")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Test 1: Unauthenticated request
        res = await client.get("/api/v1/documents")
        record("1. Unauthenticated request rejected (401)", res.status_code == 401, f"Status {res.status_code}")

        # Test 2: Malformed token header
        res = await client.get("/api/v1/documents", headers={"Authorization": "Bearer not-a-jwt"})
        record("2. Malformed token rejected (401)", res.status_code == 401, f"Status {res.status_code}")

        # Test 3: Algorithm 'none' attack rejected
        none_token = jwt.encode({"sub": user_a_id, "aud": "authenticated"}, key="", algorithm="none")
        res = await client.get("/api/v1/documents", headers={"Authorization": f"Bearer {none_token}"})
        record("3. Algorithm 'none' token rejected (401)", res.status_code == 401, f"Status {res.status_code}")

        # Test 4: Untrusted algorithm (HS512) rejected
        hs512_token = jwt.encode({"sub": user_a_id, "aud": "authenticated"}, TEST_JWT_SECRET, algorithm="HS512")
        res = await client.get("/api/v1/documents", headers={"Authorization": f"Bearer {hs512_token}"})
        record("4. Untrusted algorithm (HS512) rejected (401)", res.status_code == 401, f"Status {res.status_code}")

        # Test 5: Tampered HMAC signature rejected
        bad_sig_token = create_test_jwt(user_a_id, user_a_email, secret="wrong-secret-000000000000000000000000")
        res = await client.get("/api/v1/documents", headers={"Authorization": f"Bearer {bad_sig_token}"})
        record("5. Tampered token signature rejected (401)", res.status_code == 401, f"Status {res.status_code}")

        # Test 6: Expired token rejected
        expired_token = create_test_jwt(user_a_id, user_a_email, expires_in=-3600)
        res = await client.get("/api/v1/documents", headers={"Authorization": f"Bearer {expired_token}"})
        record("6. Expired token rejected (401)", res.status_code == 401, f"Status {res.status_code}")

        # Test 7: Invalid audience rejected
        bad_aud_token = create_test_jwt(user_a_id, user_a_email, aud="attacker_audience")
        res = await client.get("/api/v1/documents", headers={"Authorization": f"Bearer {bad_aud_token}"})
        record("7. Invalid audience claim rejected (401)", res.status_code == 401, f"Status {res.status_code}")

        # Test 8: Invalid issuer rejected
        bad_iss_token = create_test_jwt(user_a_id, user_a_email, iss="https://evil.supabase.co/auth/v1")
        res = await client.get("/api/v1/documents", headers={"Authorization": f"Bearer {bad_iss_token}"})
        record("8. Invalid issuer claim rejected (401)", res.status_code == 401, f"Status {res.status_code}")

        # Test 9: Missing subject claim rejected
        no_sub_payload = {"email": user_a_email, "aud": "authenticated", "iss": f"{TEST_SUPABASE_URL}/auth/v1", "exp": int(time.time()) + 3600}
        no_sub_token = jwt.encode(no_sub_payload, TEST_JWT_SECRET, algorithm="HS256")
        res = await client.get("/api/v1/documents", headers={"Authorization": f"Bearer {no_sub_token}"})
        record("9. Missing subject (sub) claim rejected (401)", res.status_code == 401, f"Status {res.status_code}")

        # Test 10: Valid token accepted & user auto-provisioned in DB
        res = await client.get("/api/v1/documents", headers={"Authorization": f"Bearer {token_a}"})
        user_record = db.get_user(user_a_id)
        user_provisioned = bool(user_record and user_record.get("email") == user_a_email)
        record("10. Valid token accepted & user provisioned (200)", res.status_code == 200 and user_provisioned, f"Status {res.status_code}")

        # Create isolated test document for user A
        doc_a_id = f"doc-a-{uuid.uuid4().hex[:8]}"
        db.insert_document({
            "document_id": doc_a_id,
            "user_id": user_a_id,
            "name": "Secret_Contract_A.pdf",
            "storage_path": f"storage/documents/{doc_a_id}.pdf",
            "file_size": 2048,
            "file_type": "application/pdf",
            "status": "ready"
        })

        # Test 11: User A accesses own document
        res = await client.get(f"/api/v1/documents/{doc_a_id}", headers={"Authorization": f"Bearer {token_a}"})
        record("11. User A can access own document (200)", res.status_code == 200, f"Status {res.status_code}")

        # Test 12: User B isolated from User A's document
        res = await client.get(f"/api/v1/documents/{doc_a_id}", headers={"Authorization": f"Bearer {token_b}"})
        record("12. User B isolated from User A's document (404)", res.status_code == 404, f"Status {res.status_code}")

        # Test 13: User B isolated from User A's document download
        res = await client.get(f"/api/v1/documents/{doc_a_id}/download", headers={"Authorization": f"Bearer {token_b}"})
        record("13. User B isolated from downloading User A's document (404)", res.status_code == 404, f"Status {res.status_code}")

        # Test 14: User B isolated from deleting User A's document
        res = await client.delete(f"/api/v1/documents/{doc_a_id}", headers={"Authorization": f"Bearer {token_b}"})
        record("14. User B cannot delete User A's document (404)", res.status_code == 404, f"Status {res.status_code}")

        # Test 15: Document list tenant isolation
        res = await client.get("/api/v1/documents", headers={"Authorization": f"Bearer {token_b}"})
        user_b_docs = res.json().get("documents", [])
        record("15. User B document list excludes User A's files", doc_a_id not in [d["document_id"] for d in user_b_docs], f"Docs: {len(user_b_docs)}")

        # Test 16: User B chat query targeting User A's document rejected
        res = await client.post(
            "/api/v1/chat/message",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"message": "Summarize confidential info", "document_ids": [doc_a_id]}
        )
        record("16. Chat query targeting other user's document rejected (404)", res.status_code == 404, f"Status {res.status_code}")

        # Test 17: Conversation isolation
        conv_a_id = f"conv-a-{uuid.uuid4().hex[:8]}"
        db.insert_conversation({"conversation_id": conv_a_id, "user_id": user_a_id, "title": "Secret Chat A"})
        res_get = await client.get(f"/api/v1/chat/conversations/{conv_a_id}", headers={"Authorization": f"Bearer {token_b}"})
        res_del = await client.delete(f"/api/v1/chat/conversations/{conv_a_id}", headers={"Authorization": f"Bearer {token_b}"})
        record("17. User B isolated from User A's conversation (404)", res_get.status_code == 404 and res_del.status_code == 404, f"Get: {res_get.status_code}, Del: {res_del.status_code}")

        # Test 18: WebSocket rejects missing/unauthenticated frames
        ws_in = asyncio.Queue()
        ws_out = asyncio.Queue()
        await ws_in.put({"type": "websocket.connect"})
        scope = {
            "type": "websocket", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 50000), "scheme": "ws",
            "root_path": "", "headers": [], "subprotocols": [],
            "path": "/ws/documents/status", "raw_path": b"/ws/documents/status", "query_string": b"",
        }
        ws_task = asyncio.create_task(app(scope, ws_in.get, ws_out.put))
        await ws_out.get()  # accept
        await ws_in.put({"type": "websocket.receive", "text": json.dumps({"type": "unauthorized_frame"})})
        e_err = await ws_out.get()
        e_close = await ws_out.get()
        ws_missing_auth_ok = e_close.get("code") == 1008
        await ws_task
        record("18. WebSocket rejects missing auth frame with code 1008", ws_missing_auth_ok, f"Code: {e_close.get('code')}")

        # Test 19: WebSocket rejects invalid token
        ws_in2 = asyncio.Queue()
        ws_out2 = asyncio.Queue()
        await ws_in2.put({"type": "websocket.connect"})
        ws_task2 = asyncio.create_task(app(scope, ws_in2.get, ws_out2.put))
        await ws_out2.get()  # accept
        await ws_in2.put({"type": "websocket.receive", "text": json.dumps({"type": "auth", "token": "invalid_jwt_token"})})
        e_err2 = await ws_out2.get()
        e_close2 = await ws_out2.get()
        ws_bad_token_ok = e_close2.get("code") == 1008
        await ws_task2
        record("19. WebSocket rejects invalid token with code 1008", ws_bad_token_ok, f"Code: {e_close2.get('code')}")

        # Test 20 & 21: WebSocket valid authentication & tenant-isolated broadcast
        ws_in3 = asyncio.Queue()
        ws_out3 = asyncio.Queue()
        await ws_in3.put({"type": "websocket.connect"})
        ws_task3 = asyncio.create_task(app(scope, ws_in3.get, ws_out3.put))
        await ws_out3.get()  # accept
        await ws_in3.put({"type": "websocket.receive", "text": json.dumps({"type": "auth", "token": token_a})})
        e_auth = await ws_out3.get()
        auth_data = json.loads(e_auth["text"])
        ws_auth_ok = auth_data.get("type") == "authenticated" and auth_data.get("user_id") == user_a_id
        record("20. WebSocket accepts valid token & registers user", ws_auth_ok, f"User: {auth_data.get('user_id')}")

        # Broadcast to User A
        manager = get_connection_manager()
        await manager.broadcast_to_user(user_a_id, {"document_id": doc_a_id, "status": "ready"})
        e_msg = await ws_out3.get()
        user_a_received = json.loads(e_msg["text"]).get("status") == "ready"
        # Broadcast to User B (User A should NOT receive it)
        await manager.broadcast_to_user("other-user-999", {"document_id": "other-doc", "status": "processing"})
        tenant_isolated = ws_out3.empty()
        record("21. WebSocket broadcast notifications are tenant-isolated", user_a_received and tenant_isolated, f"Received: {user_a_received}, Leaked: {not tenant_isolated}")

        await ws_in3.put({"type": "websocket.disconnect", "code": 1000})
        await ws_task3

        # Test 22: Destructive /reset endpoint blocked
        res_unauth = await client.post("/reset")
        res_auth = await client.post("/reset", headers={"Authorization": f"Bearer {token_a}"})
        reset_blocked = res_unauth.status_code == 401 and res_auth.status_code == 403
        record("22. Destructive /reset endpoint blocked (401 unauth / 403 auth)", reset_blocked, f"Unauth: {res_unauth.status_code}, Auth: {res_auth.status_code}")

        # Test 23: Existing dev user data integrity preserved
        conn = _get_conn()
        dev_docs = conn.execute("SELECT * FROM documents WHERE user_id = ?", (DEV_USER_ID,)).fetchall()
        dev_convs = conn.execute("SELECT * FROM conversations WHERE user_id = ?", (DEV_USER_ID,)).fetchall()
        dev_chunks = conn.execute("SELECT * FROM document_chunks WHERE user_id = ?", (DEV_USER_ID,)).fetchall()
        conn.close()
        dev_data_ok = len(dev_docs) > 0 and len(dev_convs) > 0 and len(dev_chunks) > 0
        record("23. Existing dev user data intact & untouched", dev_data_ok, f"Docs: {len(dev_docs)}, Convs: {len(dev_convs)}, Chunks: {len(dev_chunks)}")

        # Test 24: RS256 asymmetric token verification through JWKS
        from unittest.mock import patch, MagicMock
        from cryptography.hazmat.primitives.asymmetric import rsa, ec

        rsa_user_id = str(uuid.uuid4())
        rsa_priv = rsa.generate_private_key(65537, 2048)
        rsa_pub = rsa_priv.public_key()
        rs_token = jwt.encode(
            {"sub": rsa_user_id, "email": "rsa@test.com", "aud": "authenticated", "iss": f"{TEST_SUPABASE_URL}/auth/v1", "exp": int(time.time()) + 3600},
            rsa_priv, algorithm="RS256", headers={"kid": "rsa-key-1"}
        )
        mock_k_rsa = MagicMock()
        mock_k_rsa.key = rsa_pub
        with patch("app.middleware.auth._get_jwks_client") as m_jwks:
            m_client = MagicMock()
            m_client.get_signing_key_from_jwt.return_value = mock_k_rsa
            m_jwks.return_value = m_client
            res_rs = verify_jwt_token(rs_token)
            record("24. RS256 token verification via JWKS public key", res_rs["user_id"] == rsa_user_id, f"User: {res_rs['user_id']}")

        # Test 25: ES256 asymmetric token verification through JWKS
        ec_user_id = str(uuid.uuid4())
        ec_priv = ec.generate_private_key(ec.SECP256R1())
        ec_pub = ec_priv.public_key()
        es_token = jwt.encode(
            {"sub": ec_user_id, "email": "ec@test.com", "aud": "authenticated", "iss": f"{TEST_SUPABASE_URL}/auth/v1", "exp": int(time.time()) + 3600},
            ec_priv, algorithm="ES256", headers={"kid": "ec-key-1"}
        )
        mock_k_ec = MagicMock()
        mock_k_ec.key = ec_pub
        with patch("app.middleware.auth._get_jwks_client") as m_jwks:
            m_client = MagicMock()
            m_client.get_signing_key_from_jwt.return_value = mock_k_ec
            m_jwks.return_value = m_client
            res_es = verify_jwt_token(es_token)
            record("25. ES256 token verification via JWKS public key", res_es["user_id"] == ec_user_id, f"User: {res_es['user_id']}")

        # Cleanup test records
        conn = _get_conn()
        conn.execute("DELETE FROM documents WHERE document_id = ?", (doc_a_id,))
        conn.execute("DELETE FROM conversations WHERE conversation_id = ?", (conv_a_id,))
        conn.execute("DELETE FROM users WHERE user_id IN (?, ?)", (user_a_id, user_b_id))
        conn.commit()
        conn.close()

    print("=" * 70)
    passed_count = sum(1 for _, p, _ in results if p)
    print(f"Results: {passed_count}/{len(results)} security tests passed.")
    print("=" * 70)

    if passed_count != len(results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_all_security_tests())
