import base64
import hmac
import re
from binascii import hexlify
from typing import Optional
from hashlib import sha256
from fastapi import Header, Query
from ..config.config import app_settings

# HKDF-SHA256 with L fixed to 32
def hkdf_sha256_l_32(ikm, info, salt):
    # HKDF-Extract(salt, IKM) -> PRK
    #
    # PRK = HMAC-Hash(salt, IKM)
    prk = hmac.new(salt, ikm, sha256).digest()

    # HKDF-Expand(PRK, info, L) -> OKM
    #
    # N = ceil(L/HashLen)
    # T = T(1) | T(2) | T(3) | ... | T(N)
    # T(0) = empty string (zero length)
    # T(1) = HMAC-Hash(PRK, T(0) | info | 0x01)
    # T(2) = HMAC-Hash(PRK, T(1) | info | 0x02)
    # ...
    # OKM = first L octets of T
    #
    # L = 32 ( HashLen )
    # N = 1
    # OKM = T = T(1) = HMAC-Hash(PRK, T(0) | info | 0x01)
    return hmac.new(prk, b"" + info + bytearray([1]), sha256).digest()


def derive_service_key(master_services_key_seed, key_id, service="stt"):
    salt = sha256(service.encode("utf-8")).digest()
    return hexlify(
        hkdf_sha256_l_32(
            master_services_key_seed.encode("utf-8"), key_id.encode("utf-8"), salt
        )
    )

def parse_authorization_header(
    header: str,
) -> (Optional[str], Optional[str], Optional[str], Optional[str]):
    # Parses header values that look like:
    pattern = (
        r'Signature keyId="(.+?)",algorithm="(.+?)",headers="(.+?)",signature="(.+?)"'
    )
    result = re.search(pattern, header)
    if result:
        return result.group(1), result.group(2), result.group(3), result.group(4)
    return None, None, None, None

def check_stt_request(
    pair: str = Query(),
    authorization: Optional[str] = Header(None),
    request_key: Optional[str] = Header(None)
):
    if not authorization or not request_key or request_key != pair:
        return False

    # Parse the keyId, algorithm, signature from the header
    key_id, algorithm, headers, signature_b64 = parse_authorization_header(authorization)
    if not key_id or not algorithm or not headers or not signature_b64 or algorithm != "hs2019" or headers != "request-key":
       return False

    # Derive the service key, and expected signature and verify
    service_key = derive_service_key(app_settings.master_services_key_seed, key_id)
    expected_signing_string = f"request-key: {request_key}"
    expected_signature = hmac.new(service_key, expected_signing_string.encode("utf-8"), sha256).digest()
    expected_signature_b64 = base64.b64encode(expected_signature).decode("utf-8")

    if not hmac.compare_digest(expected_signature_b64, signature_b64):
        return False
    
    return True

    