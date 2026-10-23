from pathlib import Path
from threading import Event
import shutil
from src.folder_organizer import organize_folder
from src.rinomina_f24 import _impronta_contenuto, processa_nuovo_file
from tests.test_pdf_files import _printed_quietanza, make_pdf

def test_all_existing_copies_are_removed_and_remaining_documents_renamed(tmp_path):
    for group, amount in [("a", "10,00"), ("b", "20,00")]:
        for index in range(3):
            _printed_quietanza(tmp_path / f"download-{group}-{index}.pdf", amount=amount,
                              printed=f"18/10/2026 Ore: 10:20:0{index}")
    result = organize_folder(tmp_path, log=lambda _: None)
    assert (result.total, result.renamed, result.duplicates, result.errors) == (6, 2, 4, 0)
    files = list(tmp_path.glob("*.pdf"))
    assert len(files) == 2
    assert all(p.name.startswith("F24_20261018_") for p in files)
    assert len({_impronta_contenuto(p, {}) for p in files}) == 2

def test_standard_name_is_preserved_and_operation_is_idempotent(tmp_path):
    source = tmp_path / "download.pdf"
    _printed_quietanza(source)
    kept = processa_nuovo_file(str(source))
    original = (tmp_path / kept).read_bytes()
    _printed_quietanza(tmp_path / "copia.pdf", printed="19/10/2026 Ore: 11:22:33")
    result = organize_folder(tmp_path, log=lambda _: None)
    assert result.duplicates == 1 and result.renamed == 0
    assert (tmp_path / kept).read_bytes() == original
    again = organize_folder(tmp_path, log=lambda _: None)
    assert again.duplicates == again.renamed == again.errors == 0
    assert again.unchanged == 1

def test_same_date_and_amount_with_distinct_protocols_are_preserved(tmp_path):
    for index, protocol in enumerate(["123 7", "123 8", "999 7"]):
        _printed_quietanza(tmp_path / f"doc-{index}.pdf", protocol=protocol)
    result = organize_folder(tmp_path, log=lambda _: None)
    assert result.duplicates == 0
    assert result.renamed == 3
    assert len(list(tmp_path.glob("*.pdf"))) == 3

def test_unrecognized_pdf_is_not_renamed_but_exact_copy_is_removed(tmp_path):
    source = tmp_path / "a.pdf"
    make_pdf(source, ["DOCUMENTO SINTETICO NON RICONOSCIUTO"])
    shutil.copyfile(source, tmp_path / "b.PDF")
    (tmp_path / "note.txt").write_text("conservare")
    result = organize_folder(tmp_path, log=lambda _: None)
    assert result.duplicates == 1 and result.unclassified == 1
    assert source.exists() and (tmp_path / "note.txt").exists()

def test_subfolders_are_outside_selected_folder_scope(tmp_path):
    nested = tmp_path / "altra-utenza"
    nested.mkdir()
    _printed_quietanza(tmp_path / "download.pdf")
    _printed_quietanza(nested / "non-toccare.pdf")
    original = (nested / "non-toccare.pdf").read_bytes()
    result = organize_folder(tmp_path, log=lambda _: None)
    assert result.total == result.renamed == 1
    assert (nested / "non-toccare.pdf").read_bytes() == original

def test_cancel_before_start_preserves_all_files(tmp_path):
    _printed_quietanza(tmp_path / "a.pdf")
    _printed_quietanza(tmp_path / "b.pdf")
    stop = Event()
    stop.set()
    result = organize_folder(tmp_path, stop, log=lambda _: None)
    assert result.cancelled and result.processed == 0
    assert {p.name for p in tmp_path.iterdir()} == {"a.pdf", "b.pdf"}

def test_locked_duplicate_is_reported_without_removing_keeper(tmp_path, monkeypatch):
    source = tmp_path / "download.pdf"
    _printed_quietanza(source)
    kept = processa_nuovo_file(str(source))
    duplicate = tmp_path / "copy.pdf"
    shutil.copyfile(tmp_path / kept, duplicate)
    unlink = Path.unlink
    def deny_duplicate(path, *args, **kwargs):
        if path == duplicate:
            raise PermissionError()
        return unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", deny_duplicate)
    result = organize_folder(tmp_path, log=lambda _: None)
    assert result.errors == 1 and result.duplicates == 0
    assert (tmp_path / kept).exists() and duplicate.exists()


def test_multi_year_organizer_keeps_one_copy_per_selected_year_and_leaves_other_years(tmp_path):
    from src.folder_organizer import organize_folders
    for year in ("2023", "2024", "2025"):
        folder = tmp_path / year
        folder.mkdir()
        _printed_quietanza(folder / "a.pdf")
        _printed_quietanza(folder / "b.pdf", printed="19/10/2026 Ore: 11:22:33")
    result = organize_folders([tmp_path / "2023", tmp_path / "2025"], log=lambda _: None)
    assert result.duplicates == 2 and result.renamed == 2
    assert len(list((tmp_path / "2023").glob("*.pdf"))) == 1
    assert len(list((tmp_path / "2025").glob("*.pdf"))) == 1
    assert len(list((tmp_path / "2024").glob("*.pdf"))) == 2



def test_organizer_preserves_model_label_and_deduplicates_model_content(tmp_path):
    source = tmp_path / "download.pdf"
    _printed_quietanza(source)
    name = processa_nuovo_file(str(source), document_kind="modello")
    original = (tmp_path / name).read_bytes()
    _printed_quietanza(tmp_path / "copia.pdf", printed="19/10/2026 Ore: 11:22:33")
    result = organize_folder(tmp_path, log=lambda _: None)
    assert result.duplicates == 1 and result.renamed == result.errors == 0
    assert name.startswith("F24_modello_")
    assert (tmp_path / name).read_bytes() == original
    assert len(list(tmp_path.glob("*.pdf"))) == 1
