#!/usr/bin/env python3
"""Throwaway JWT setup for AUTH_MODE=jwt: RSA key, JWKS file, signed good/expired/wrong-key tokens.
    jwt_keys.py <dir for jwks.json> <env file out>"""
import json, sys, time
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

outdir, envfile = sys.argv[1:3]
claims = {"iss": "https://issuer.test", "aud": "finch", "sub": "finch-user"}
key, other = (rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2))
jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
jwk.update(kid="k1", use="sig", alg="RS256")
json.dump({"keys": [jwk]}, open(f"{outdir}/jwks.json", "w"))
now = int(time.time())
sign = lambda k, **c: jwt.encode({**claims, "iat": now - 7200, "exp": now + 3600, **c}, k, algorithm="RS256", headers={"kid": "k1"})
with open(envfile, "w") as f:
    f.write(f"export FLIGHT_TOKEN={sign(key)}\n")
    f.write(f"export FLIGHT_EXPIRED_TOKEN={sign(key, exp=now - 3600)}\n")
    f.write(f"export FLIGHT_BAD_TOKEN={sign(other)}\n")
