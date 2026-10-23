from pathlib import Path
import pytest
from src.rinomina_f24 import processa_nuovo_file, estrai_dati, digits_to_date

def make_pdf(path, lines):
    # PDF di prova completo: nessun documento reale.
    stream = ("BT /F1 12 Tf 20 750 Td 16 TL " +
              " ".join(f"({line}) Tj T*" for line in lines) + " ET").encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    data = b"%PDF-1.4\n"
    positions = [0]
    for number, body in enumerate(objects, 1):
        positions.append(len(data))
        data += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(data)
    data += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode()
    data += b"".join(f"{position:010d} 00000 n \n".encode() for position in positions[1:])
    data += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    path.write_bytes(data)

def quietanza(path, amount="1.234,56"):
    make_pdf(path, ["QUIETANZA DI VERSAMENTO", "DATA DEL VERSAMENTO 18 10 2026 ABI",
                    f"Saldo delega {amount}", "PROTOCOLLO TELEMATICO 123 7"])

def test_real_synthetic_pdf_extraction_and_name(tmp_path):
    source = tmp_path / "temp.pdf"
    quietanza(source)
    assert estrai_dati(str(source)) == ("20261018", "1234,56", 7)
    name = processa_nuovo_file(str(source))
    assert name == "F24_20261018_001_1234.56euro.pdf"
    assert (tmp_path / name).exists()
    assert not source.exists()

def test_duplicate_is_skipped_even_when_metadata_cannot_be_extracted(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    source = tmp_path / "temp.pdf"
    make_pdf(source, ["DOCUMENTO SINTETICO NON RICONOSCIUTO"])
    first = processa_nuovo_file(str(source), output)
    assert first.startswith("F24_da_verificare_")
    make_pdf(source, ["DOCUMENTO SINTETICO NON RICONOSCIUTO"])
    assert processa_nuovo_file(str(source), output) == "skipped"
    assert len(list(output.glob("*.pdf"))) == 1

def test_distinct_documents_same_day_are_not_overwritten(tmp_path):
    source = tmp_path / "temp.pdf"
    quietanza(source)
    first = processa_nuovo_file(str(source))
    original = (tmp_path / first).read_bytes()
    quietanza(source, "99,00")
    second = processa_nuovo_file(str(source))
    assert first != second
    assert "_002_" in second
    assert (tmp_path / first).read_bytes() == original

def test_impossible_calendar_date_is_not_used_in_filename():
    assert digits_to_date(list("31022026")) is None
    assert digits_to_date(list("29022024")) == "20240229"


def _printed_quietanza(path, printed="18/10/2026 Ore: 10:20:00", protocol="123 7",
                       taxpayer="CONTRIBUENTE DEMO A", tax="TRIBUTO 1001", amount="1.234,56"):
    make_pdf(path, ["Utente: OPERATORE DEMO Data: " + printed,
                   "QUIETANZA DI VERSAMENTO", taxpayer,
                   "DATA DEL VERSAMENTO 18 10 2026 ABI",
                   "Saldo delega " + amount, "PROTOCOLLO TELEMATICO " + protocol, tax])

def test_same_quietanza_with_new_print_date_and_time_is_skipped(tmp_path):
    output = tmp_path / "output"
    source = tmp_path / "incoming.pdf"
    _printed_quietanza(source)
    first = processa_nuovo_file(str(source), output)
    original = (output / first).read_bytes()
    _printed_quietanza(source, printed="19/10/2026 Ore: 11:25:31")
    assert source.read_bytes() != original
    assert processa_nuovo_file(str(source), output) == "skipped"
    assert (output / first).read_bytes() == original
    assert len(list(output.glob("*.pdf"))) == 1

def test_changed_internal_pdf_metadata_without_content_change_is_skipped(tmp_path):
    source = tmp_path / "incoming.pdf"
    output = tmp_path / "output"
    _printed_quietanza(source)
    processa_nuovo_file(str(source), output)
    _printed_quietanza(source)
    source.write_bytes(source.read_bytes() + b"\n% Regenerated file with new metadata\n")
    assert processa_nuovo_file(str(source), output) == "skipped"

@pytest.mark.parametrize("changes", [
    {"protocol": "999 7"}, {"protocol": "123 8"}, {"taxpayer": "CONTRIBUENTE DEMO B"},
    {"tax": "TRIBUTO 2002"}, {"amount": "99,00"},
])
def test_same_date_does_not_merge_different_quietanze(tmp_path, changes):
    source = tmp_path / "incoming.pdf"
    output = tmp_path / "output"
    _printed_quietanza(source)
    first = processa_nuovo_file(str(source), output)
    _printed_quietanza(source, printed="19/10/2026 Ore: 11:25:31", **changes)
    second = processa_nuovo_file(str(source), output)
    assert second != "skipped"
    assert first != second
    assert len(list(output.glob("*.pdf"))) == 2

def test_generation_normalization_preserves_payment_date_and_other_times():
    from src.rinomina_f24 import _normalizza_testo_documento
    text = ("Utente: DEMO Data: 18/10/2026 Ore: 10:20:00\n"
            "DATA DEL VERSAMENTO 17 10 2026\nData: 16/10/2026 Ore: 08:00:00")
    normalized = _normalizza_testo_documento(text)
    assert "DATA DEL VERSAMENTO 17 10 2026" in normalized
    assert "Data: 16/10/2026 Ore: 08:00:00" in normalized
    assert "Utente: DEMO" in normalized
    assert "10:20:00" not in normalized

def test_ambiguous_pdf_is_not_discarded_by_text_only_comparison(tmp_path):
    source = tmp_path / "incoming.pdf"
    output = tmp_path / "output"
    make_pdf(source, ["DOCUMENTO NON IDENTIFICATO"])
    first = processa_nuovo_file(str(source), output)
    make_pdf(source, ["DOCUMENTO NON IDENTIFICATO"])
    source.write_bytes(source.read_bytes() + b"\n% potentially different document\n")
    second = processa_nuovo_file(str(source), output)
    assert second != "skipped"
    assert first != second

def _make_multipage_pdf(path, pages):
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        ("<< /Type /Pages /Kids [" + " ".join(f"{4+2*i} 0 R" for i in range(len(pages))) +
         f"] /Count {len(pages)} >>").encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for index, lines in enumerate(pages):
        stream = ("BT /F1 12 Tf 20 750 Td 16 TL " +
                  " ".join(f"({line}) Tj T*" for line in lines) + " ET").encode("ascii")
        objects.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                        f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5+2*index} 0 R >>").encode())
        objects.append(b"<< /Length " + str(len(stream)).encode() +
                       b" >>\nstream\n" + stream + b"\nendstream")
    data = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(data))
        data += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(data)
    data += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode()
    data += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    data += (f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF").encode()
    path.write_bytes(data)

def test_differences_on_later_pages_are_preserved(tmp_path):
    source = tmp_path / "incoming.pdf"
    output = tmp_path / "output"
    first_page = ["QUIETANZA DI VERSAMENTO", "DATA DEL VERSAMENTO 18 10 2026 ABI",
                  "Saldo delega 100,00", "PROTOCOLLO TELEMATICO 123 7"]
    _make_multipage_pdf(source, [first_page, ["TRIBUTO 1001"]])
    first = processa_nuovo_file(str(source), output)
    _make_multipage_pdf(source, [first_page, ["TRIBUTO 2002"]])
    second = processa_nuovo_file(str(source), output)
    assert second != "skipped"
    assert first != second
