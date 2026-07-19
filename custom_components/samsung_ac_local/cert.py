"""
Bundled client certificate for the Samsung AC Local integration.

Contains a self-signed EC P-256 certificate with the Samsung global cloud
server UUID (ab0b0ac4-aae9-4958-a04d-8ec36fe1b2f9) in the OU field.

Samsung OCF devices do not verify certificate chains - they extract the UUID
from the client certificate subject and check it against the device ACL.
The cloud server UUID is provisioned into every device's ACL during normal
SmartThings pairing with full access (permission 31).

This cert is valid for 20 years and requires no external files.
"""

CERT_PEM = """\
-----BEGIN CERTIFICATE-----
MIIB8zCCAZmgAwIBAgIUVvSX4ujalaNkNAtPDPTn/cXnXMkwCgYIKoZIzj0EAwIw
TzEyMDAGA1UECwwpdXVpZDphYjBiMGFjNC1hYWU5LTQ5NTgtYTA0ZC04ZWMzNmZl
MWIyZjkxGTAXBgNVBAMMEFNhbXN1bmcgQUMgTG9jYWwwHhcNMjYwNzA3MTkxNDI3
WhcNNDYwNzAyMTkxNDI3WjBPMTIwMAYDVQQLDCl1dWlkOmFiMGIwYWM0LWFhZTkt
NDk1OC1hMDRkLThlYzM2ZmUxYjJmOTEZMBcGA1UEAwwQU2Ftc3VuZyBBQyBMb2Nh
bDBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABFkkIZPpA90HgyTaWWHKwS9Sm5RW
yLbBubTbFGEdS1Rs+WtCXWVEWChPbJc5SGs46anHrtNlQhLN7/4vSvqRi9ujUzBR
MB0GA1UdDgQWBBTu5IgHXrBEOMz+hnQcPdg+eVE41zAfBgNVHSMEGDAWgBTu5IgH
XrBEOMz+hnQcPdg+eVE41zAPBgNVHRMBAf8EBTADAQH/MAoGCCqGSM49BAMCA0gA
MEUCIFI4goPpn7Er93As40nnAN6vbqSUS1Heq0xzlzNu9EVTAiEAkfGwhvHj2GmZ
eCdppYH7UrHmZVu7yHCxVsCOA1PwcE8=
-----END CERTIFICATE-----
"""

KEY_PEM = """\
-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg241FgiquctQVrSyN
RTAY3LTLsWAZZFaczuGQOk/q1+KhRANCAARZJCGT6QPdB4Mk2llhysEvUpuUVsi2
wbm02xRhHUtUbPlrQl1lRFgoT2yXOUhrOOmpx67TZUISze/+L0r6kYvb
-----END PRIVATE KEY-----
"""
