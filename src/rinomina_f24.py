#!/usr/bin/env python3
"""
Rinomina le quietanze F24 con il formato:
  F24_AAAAMMGG_IMPORTO_NNN.pdf
"""

import os, re, sys
import hashlib
from pathlib import Path
from datetime import date
import shutil
import pdfplumber
from collections import defaultdict

# ─── Utility ────────────────────────────────────────────────────────────────

def normalizza_importo(raw):
    """'15.137,, 94' → '15137,94'  |  '57.245,3 4' → '57245,34'"""
    s = re.sub(r'[^\d,.]', '', raw)   # solo cifre, virgole, punti
    s = re.sub(r',+', ',', s)         # virgole doppie → una
    if ',' in s:
        s = s.replace('.', '')        # punti migliaia → tolti
    # assicura sempre due decimali
    if ',' not in s and s:
        s += ',00'
    return s


def digits_to_date(seq):
    """Lista di almeno 8 cifre [G,G,M,M,A,A,A,A] → 'AAAAMMGG' o None"""
    seq = seq[-8:]  # prende sempre le ultime 8 (evita cifre spurie prima)
    if len(seq) < 8:
        return None
    dd   = ''.join(seq[0:2])
    mm   = ''.join(seq[2:4])
    yyyy = ''.join(seq[4:8])
    if not (1 <= int(dd) <= 31 and 1 <= int(mm) <= 12 and 2000 <= int(yyyy) <= 2099):
        return None
    try:
        date(int(yyyy), int(mm), int(dd))
    except ValueError:
        return None
    return f"{yyyy}{mm}{dd}"


# ─── Estrattori per tipo ─────────────────────────────────────────────────────

def estrai_quietanza(text):
    """
    Formato Quietanza di Versamento.
    """
    m = re.search(r'DATA DEL VERSAMENTO\s+([\d\s]+?)(?:ABI|CAB|\n)', text)
    if not m:
        return None
    data_str = digits_to_date(re.findall(r'\d', m.group(1)))
    if not data_str:
        return None

    m_imp = re.search(r'Saldo delega\s+([\d\.,\s]+)', text)
    importo = normalizza_importo(m_imp.group(1)) if m_imp else '0,00'

    m_prot = re.search(r'PROTOCOLLO TELEMATICO\s+\d+\s+(\d+)', text)
    ricevuta = int(m_prot.group(1)) if m_prot else 0

    return data_str, importo, ricevuta


def estrai_f24_standard(text):
    """
    Formato Mod. F24 Standard (layout multi-sezione).
    """
    idx = text.find('Utente:')
    body = text[idx:] if idx >= 0 else text

    m = re.search(r'(\d[\d\s]{6,18}\d)\s+\d{5}\s+\d{5}', body)
    if not m:
        return None
    data_str = digits_to_date(re.findall(r'\d', m.group(1)))
    if not data_str:
        return None

    zona = body[:body.find('ESTREMI DEL VERSAMENTO')] if 'ESTREMI DEL VERSAMENTO' in body else body
    matches = re.findall(r'([\d]+(?:\.\d{3})*,,\s*\d{2})', zona)
    if matches:
        importo = normalizza_importo(matches[-1])
    else:
        m_imp = re.findall(r'([\d]+(?:\.\d{3})*,\d{2})', zona)
        importo = normalizza_importo(m_imp[-1]) if m_imp else '0,00'

    m_ore = re.search(r'Ore:\s*(\d{2}):(\d{2}):(\d{2})', text)
    ricevuta = int(m_ore.group(1) + m_ore.group(2) + m_ore.group(3)) if m_ore else 0

    return data_str, importo, ricevuta


def estrai_f24_semplificato(text):
    """
    Formato Mod. F24 Semplificato.
    """
    idx = text.find('Utente:')
    body = text[idx:] if idx >= 0 else text

    m = re.search(r'(\d[\d\s]{6,18}\d)\s+\d{5}\s+\d{5}', body)
    if not m:
        return None
    data_str = digits_to_date(re.findall(r'\d', m.group(1)))
    if not data_str:
        return None

    zona = body[:m.start() + 15]
    m_imp = re.findall(r'([\d]{1,3}(?:\.\d{3})*,\d{2})', zona)
    candidati = [x for x in m_imp if x != '0,00']
    importo = normalizza_importo(candidati[-1]) if candidati else '0,00'

    m_ore = re.search(r'Ore:\s*(\d{2}):(\d{2}):(\d{2})', text)
    ricevuta = int(m_ore.group(1) + m_ore.group(2) + m_ore.group(3)) if m_ore else 0

    return data_str, importo, ricevuta


def estrai_f24_accise(text):
    """
    Formato Mod. F24 Accise.
    """
    idx = text.find('Utente:')
    body = text[idx:] if idx >= 0 else text

    m = re.search(r'(\d[\d\s]{6,18}\d)\s+\d{5}\s+\d{5}', body)
    if not m:
        return None
    data_str = digits_to_date(re.findall(r'\d', m.group(1)))
    if not data_str:
        return None

    zona = body[:m.start() + 15]
    matches = re.findall(r'([\d]+(?:,+\s*\d+)+)', zona)
    candidati = []
    for raw in matches:
        imp = normalizza_importo(raw)
        if re.match(r'^\d+,\d{2}$', imp) and imp != '0,00':
            candidati.append(imp)
    importo = candidati[-1] if candidati else '0,00'

    m_ore = re.search(r'Ore:\s*(\d{2}):(\d{2}):(\d{2})', text)
    ricevuta = int(m_ore.group(1) + m_ore.group(2) + m_ore.group(3)) if m_ore else 0

    return data_str, importo, ricevuta


def estrai_dati(path_pdf):
    """Rileva il tipo di F24 ed estrae (data_str, importo_str, ricevuta_int)."""
    try:
        with pdfplumber.open(path_pdf) as pdf:
            text = pdf.pages[0].extract_text() or ""

        if 'QUIETANZA DI VERSAMENTO' in text:
            return estrai_quietanza(text)
        elif 'Mod. F24 Semplificato' in text:
            return estrai_f24_semplificato(text)
        elif 'Mod. F24 Accise' in text or 'F24 ACCISE' in text.upper():
            return estrai_f24_accise(text)
        elif 'MODELLO DI PAGAMENTO' in text or 'MOD. F24' in text.upper():
            return estrai_f24_standard(text)
        else:
            return (estrai_quietanza(text)
                    or estrai_f24_semplificato(text)
                    or estrai_f24_accise(text)
                    or estrai_f24_standard(text))
    except Exception:
        return None


# ─── CONTROLLO DUPLICATI AVANZATO ────────────────────────────────────────────

def calcola_hash_md5(filepath: str) -> str:
    """Calcola l'hash MD5 di un file per verificarne l'univocità del contenuto."""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def _normalizza_testo_documento(text):
    """Ignora solo data/ora di generazione nell'intestazione Utente del portale."""
    lines = []
    for line in text.splitlines():
        if (re.search(r"\bUtente\s*:", line, re.IGNORECASE)
                and re.search(r"\bOre\s*:\s*\d{1,2}:\d{2}(?::\d{2})?", line, re.IGNORECASE)):
            line = re.sub(r"(\bOre\s*:\s*)\d{1,2}:\d{2}(?::\d{2})?",
                          r"\1<generazione>", line, flags=re.IGNORECASE)
            line = re.sub(r"(\bData\s*:\s*)\d{1,2}[/.-]\d{1,2}[/.-]\d{4}",
                          r"\1<generazione>", line, flags=re.IGNORECASE)
        lines.append(re.sub(r"\s+", " ", line).strip())
    return "\n".join(lines).strip()

def _impronta_contenuto(path, cache):
    path = Path(path)
    stat = path.stat()
    key = str(path.resolve())
    stamp = (stat.st_size, stat.st_mtime_ns)
    cached = cache.get(key)
    if cached is not None and cached[0] == stamp:
        return cached[1]
    fingerprint = None
    try:
        with pdfplumber.open(path) as pdf:
            texts = [page.extract_text() or "" for page in pdf.pages]
            full_text = "\n".join(texts).upper()
            # Conservare i documenti ambigui o privi di testo: solo confronto binario.
            recognized = any(marker in full_text for marker in (
                "QUIETANZA DI VERSAMENTO", "MOD. F24", "MODELLO DI PAGAMENTO", "F24 ACCISE"))
            if recognized and texts and all(text.strip() for text in texts):
                digest = hashlib.sha256(b"f24-content-v1")
                for page, text in zip(pdf.pages, texts):
                    digest.update(b"\0PAGE\0")
                    digest.update(_normalizza_testo_documento(text).encode("utf-8"))
                    # Preservare anche differenze nelle immagini incorporate.
                    for item in page.images:
                        digest.update(b"\0IMAGE\0")
                        digest.update(str((item.get("srcsize"), item.get("bits"),
                                           item.get("colorspace"))).encode("utf-8"))
                        digest.update(item["stream"].get_data())
                fingerprint = digest.hexdigest()
    except Exception:
        # Nessuna eliminazione basata su un confronto non disponibile.
        pass
    cache[key] = (stamp, fingerprint)
    return fingerprint

def processa_nuovo_file(temp_path: str, output_dir=None, comparison_cache=None, document_kind="quietanza") -> str:
    """Confronta byte e contenuto F24, escludendo i soli dati di generazione noti."""
    if document_kind not in {"quietanza", "modello"}:
        raise ValueError("Tipo di documento non supportato.")
    prefix = "F24_modello" if document_kind == "modello" else "F24"
    source = Path(temp_path)
    folder = Path(output_dir) if output_dir is not None else source.parent
    folder.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    cache = comparison_cache if comparison_cache is not None else {}
    candidates = [item for item in folder.glob("*.pdf") if item.resolve() != source.resolve()]
    for existing in candidates:
        if existing.stat().st_size == source.stat().st_size:
            if hashlib.sha256(existing.read_bytes()).hexdigest() == digest:
                source.unlink()
                return "skipped"
    content = _impronta_contenuto(source, cache)
    if content is not None:
        for existing in candidates:
            if _impronta_contenuto(existing, cache) == content:
                source.unlink()
                return "skipped"
    data = estrai_dati(str(source))
    sequence = 1
    if data:
        day = data[0]
        for existing in folder.glob(f"{prefix}_{day}_*.pdf"):
            match = re.match(rf"{prefix}_{day}_(\d+)_", existing.name)
            if match:
                sequence = max(sequence, int(match.group(1)) + 1)
    while True:
        if data:
            day, amount, _ = data
            name = f"{prefix}_{day}_{sequence:03d}_{amount.replace(',', '.')}euro.pdf"
        else:
            suffix = "" if sequence == 1 else f"_{sequence}"
            name = f"{prefix}_da_verificare_{digest[:16]}{suffix}.pdf"
        destination = folder / name
        try:
            target = destination.open("xb")
        except FileExistsError:
            sequence += 1
            continue
        try:
            with target, source.open("rb") as stream:
                shutil.copyfileobj(stream, target)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        stat = destination.stat()
        cache[str(destination.resolve())] = ((stat.st_size, stat.st_mtime_ns), content)
        source.unlink()
        return name

# ─── Main (per uso standalone) ────────────────────────────────────────────────

if __name__ == "__main__":
    cartella = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "."
    # Esecuzione standalone se lanciato direttamente
    print("Esecuzione standalone di rinomina...")
