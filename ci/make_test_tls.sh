#!/usr/bin/env bash
# Generate the mock's test TLS certificates (spec 2026-11-13 kontrakt najpierw, D5).
#
#   bash ci/make_test_tls.sh
#
# Writes src/tdkit/mock/tls/{ca.pem,server.pem,server-key.pem}: a test CA and a server
# certificate for 127.0.0.1 and localhost signed by it, valid 3650 days. These are PUBLIC test
# values for the loopback interface only. The CA key is made in a temporary folder and deleted,
# so nobody can sign anything else with this CA. tests/test_tls.py fails a year before expiry:
# run this script again then and commit the three files.
set -euo pipefail

out="$(cd "$(dirname "$0")/.." && pwd)/src/tdkit/mock/tls"
tmp_unix="$(mktemp -d)"
trap 'rm -rf "$tmp_unix"' EXIT
# Git Bash: openssl is a Windows program, so it gets Windows paths, and "/CN=..." must not be
# converted into one.
export MSYS_NO_PATHCONV=1
if command -v cygpath >/dev/null; then
  tmp="$(cygpath -m "$tmp_unix")"
  out="$(cygpath -m "$out")"
else
  tmp="$tmp_unix"
fi

openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -sha256 \
  -keyout "$tmp/ca-key.pem" -out "$out/ca.pem" -subj "/CN=tdkit test CA (loopback only)" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -addext "subjectKeyIdentifier=hash"

openssl req -newkey rsa:2048 -nodes -sha256 \
  -keyout "$out/server-key.pem" -out "$tmp/server.csr" -subj "/CN=127.0.0.1"

cat > "$tmp/server.ext" <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=IP:127.0.0.1,DNS:localhost
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid
EOF

openssl x509 -req -in "$tmp/server.csr" -CA "$out/ca.pem" -CAkey "$tmp/ca-key.pem" \
  -CAcreateserial -CAserial "$tmp/ca.srl" -days 3650 -sha256 -extfile "$tmp/server.ext" -out "$out/server.pem"

echo "wrote $out/ca.pem, server.pem, server-key.pem"
