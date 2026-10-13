"""Utility script to create a sample multi-page PDF document for testing RAG ingestion."""
from pathlib import Path


def generate_simple_pdf(output_path: Path):
    """Generate a clean 2-page PDF document with text streams without heavy external dependencies."""
    # PDF specification 1.4 minimal text document
    content_page1 = (
        "BT\n"
        "/F1 16 Tf\n"
        "50 720 Td\n"
        "(ENTERPRISE DATA ENCRYPTION AND KEY MANAGEMENT POLICY) Tj\n"
        "/F1 11 Tf\n"
        "0 -30 Td\n"
        "(Section 1: Data at Rest Encryption Standards) Tj\n"
        "0 -20 Td\n"
        "(All customer data stored in persistent volumes must be encrypted with AES-GCM 256-bit.) Tj\n"
        "0 -20 Td\n"
        "(Encryption keys must be rotated automatically every 90 days via AWS KMS or Azure Key Vault.) Tj\n"
        "0 -20 Td\n"
        "(Hardcoded encryption keys in git repositories will result in immediate credential revocation.) Tj\n"
        "ET"
    )

    content_page2 = (
        "BT\n"
        "/F1 16 Tf\n"
        "50 720 Td\n"
        "(Section 2: Network Transmission & Ingress Rules) Tj\n"
        "/F1 11 Tf\n"
        "0 -30 Td\n"
        "(TLS version 1.3 is strictly enforced for all public facing endpoints. TLS 1.0 and 1.1 are disabled.) Tj\n"
        "0 -20 Td\n"
        "(Port 22 SSH ingress is blocked globally from the public internet. Access requires bastion VPN.) Tj\n"
        "0 -20 Td\n"
        "(Security audit logs must be reviewed by the InfoSec team weekly.) Tj\n"
        "ET"
    )

    stream1 = content_page1.encode("latin-1")
    stream2 = content_page2.encode("latin-1")

    # Construct PDF objects
    objs = []
    # 1: Catalog
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    # 2: Pages
    objs.append(b"<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>")
    # 3: Page 1
    objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 7 0 R >> >> >>")
    # 4: Stream 1
    objs.append(f"<< /Length {len(stream1)} >>\nstream\n".encode("latin-1") + stream1 + b"\nendstream")
    # 5: Page 2
    objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 6 0 R /Resources << /Font << /F1 7 0 R >> >> >>")
    # 6: Stream 2
    objs.append(f"<< /Length {len(stream2)} >>\nstream\n".encode("latin-1") + stream2 + b"\nendstream")
    # 7: Font
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    # Build PDF with xref table
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objs, start=1):
        offsets.append(len(output))
        output.extend(f"{idx} 0 obj\n".encode("latin-1"))
        output.extend(obj)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode("latin-1"))
    for off in offsets[1:]:
        output.extend(f"{off:010d} 00000 n \n".encode("latin-1"))

    output.extend(
        f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("latin-1")
    )

    output_path.write_bytes(output)
    print(f"Generated sample PDF at: {output_path}")


if __name__ == "__main__":
    target = Path(__file__).parent / "enterprise_security_policy.pdf"
    generate_simple_pdf(target)
