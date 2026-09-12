from __future__ import annotations

import shutil
import ssl
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

_TEST_CA_PEM = """-----BEGIN CERTIFICATE-----
MIIDBTCCAe2gAwIBAgIUFhZ9tlfduuEvOIOcGuOA7E0SSL4wDQYJKoZIhvcNAQEL
BQAwEjEQMA4GA1UEAwwHdGVzdC1jYTAeFw0yNjAzMjUxNDE5MDVaFw0yNzAzMjUx
NDE5MDVaMBIxEDAOBgNVBAMMB3Rlc3QtY2EwggEiMA0GCSqGSIb3DQEBAQUAA4IB
DwAwggEKAoIBAQDcgmzozr7Ia72OCsxk2uKUFhM6wR0H69cv4qO5OViu+0qFoYr6
Bny2o+Q/ooqCCYveamPukYlZMFilnk9b4M2VwxK72pOVTkvyWUWpIJrV6OQKqsaf
DNgDdl4U4i2U/HKKNXTNtaVPzc3d40rcwy8dHVzFaTs8o7UG73foHQ2/7KQ6sY5d
gjOchbLDlhN2Nkyc4WxXEipesonUogLzZxx9gSMZN6VmXaIyijncAFxO9vSenTQd
FstTlTI/FCPQU2cg5K3rtToPli3j7z9oeeMrrt3pp1xmU5/cliz5kQ3CXxbH1UR3
uFAaW09wTsK+fSo8rBgGWO5JU706M1aL5wvXAgMBAAGjUzBRMB0GA1UdDgQWBBR3
yFGDemoQUIFA/YW1BJYhT6hlhzAfBgNVHSMEGDAWgBR3yFGDemoQUIFA/YW1BJYh
T6hlhzAPBgNVHRMBAf8EBTADAQH/MA0GCSqGSIb3DQEBCwUAA4IBAQCq5bl2J+JO
LpOZG4n4xbQUi456bV40a9lxFwXyR4toiOnLc9QTiFLtrRRMjiAYBlpnp7Aq7rPK
0dxGhFsNhTHYv5bKF3Wt6EKnfmjC5J2PQ4j4fZbqnBJVNhtP3/QdTg/Alx2DgVlP
vUaYBYvyM8aeAGCvlTr9XbciLgDHrO6xE0mppF87jG3DbVIqhGAa8z7KR286Hmw3
JtnWOCSAT+dNsAXmz4ebm7kp9OnpLLKjvrNEUNPA20J5S+BXTtPv7x/koRwSX35M
9yOorGsG0RB4CaEy4fpiKTewGNMdHNoZNevXB1s7jm3YdW5BDxvG4Su5RGqAjS+Y
49s7jC+okfzl
-----END CERTIFICATE-----
"""


@dataclass(frozen=True, slots=True)
class LocalHttpsSite:
    base_url: str
    ca_certificate: Path


@pytest.fixture
def local_https_site(tmp_path: Path) -> Iterator[LocalHttpsSite]:
    ca_certificate = tmp_path / "ca.pem"
    if sys.platform != "linux":
        ca_certificate.write_text(_TEST_CA_PEM)
        yield LocalHttpsSite("https://127.0.0.1", ca_certificate)
        return

    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.fail("OpenSSL is required for the private CA integration contract")

    ca_config = tmp_path / "ca.cnf"
    ca_key = tmp_path / "ca-key.pem"
    server_config = tmp_path / "server.cnf"
    server_key = tmp_path / "server-key.pem"
    server_request = tmp_path / "server.csr"
    server_certificate = tmp_path / "server.pem"

    ca_config.write_text(
        """[req]
distinguished_name = subject
x509_extensions = ca_extensions
prompt = no

[subject]
CN = pyagentbrowser integration CA

[ca_extensions]
basicConstraints = critical,CA:TRUE
keyUsage = critical,keyCertSign,cRLSign
subjectKeyIdentifier = hash
"""
    )
    server_config.write_text(
        """[req]
distinguished_name = subject
req_extensions = server_extensions
prompt = no

[subject]
CN = 127.0.0.1

[server_extensions]
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = IP:127.0.0.1
"""
    )

    def run_openssl(*args: str) -> None:
        subprocess.run(
            [openssl, *args],
            check=True,
            capture_output=True,
            text=True,
        )

    run_openssl(
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-sha256",
        "-days",
        "2",
        "-config",
        str(ca_config),
        "-keyout",
        str(ca_key),
        "-out",
        str(ca_certificate),
    )
    run_openssl(
        "req",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-sha256",
        "-config",
        str(server_config),
        "-keyout",
        str(server_key),
        "-out",
        str(server_request),
    )
    run_openssl(
        "x509",
        "-req",
        "-sha256",
        "-days",
        "2",
        "-in",
        str(server_request),
        "-CA",
        str(ca_certificate),
        "-CAkey",
        str(ca_key),
        "-CAcreateserial",
        "-extfile",
        str(server_config),
        "-extensions",
        "server_extensions",
        "-out",
        str(server_certificate),
    )

    (tmp_path / "index.html").write_text("<title>Private CA</title>")
    handler = partial(SimpleHTTPRequestHandler, directory=tmp_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(server_certificate, server_key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield LocalHttpsSite(
            f"https://127.0.0.1:{server.server_port}",
            ca_certificate,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
