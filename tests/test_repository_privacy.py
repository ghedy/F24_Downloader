import json
import subprocess
import uuid
import pytest
from tools.prepare_release import release_files, ROOT
from tools.check_repository import check_repository, RepositoryCheckError


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


@pytest.fixture
def repository(tmp_path):
    for source in release_files(ROOT):
        target = tmp_path / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    unique = uuid.uuid4().hex
    private = {"utenze": [{"descrizione": "private-company-" + unique, "codice": "private-code-" + unique}],
               "credenziali": {"SPID_SIELTE": {"username": "private-user-" + unique,
                                               "password": "private-password-" + unique}},
               "impostazioni": {"output_dir": "Z:/private-folder-" + unique + "/quietanze"}}
    (tmp_path / "config/config.json").write_text(json.dumps(private), encoding="utf-8")
    (tmp_path / "config/credentials.bin.non-utilizzabile-demo").write_bytes(b"private encrypted archive")
    git(tmp_path, "init", "--initial-branch=main")
    git(tmp_path, "add", "--", *[str(path.relative_to(ROOT).as_posix()) for path in release_files(ROOT)])
    return tmp_path, private


def test_index_contains_only_public_files_and_ignores_local_settings(repository):
    root, private = repository
    assert check_repository(root, staged=True) == len(release_files(root))
    tracked = git(root, "ls-files").decode()
    assert "config/config.json" not in tracked and "credentials.bin" not in tracked
    assert (root / "config/config.json").is_file()  # Il programma conserva i dati locali.


@pytest.mark.parametrize("field", ["code", "description", "username", "password", "output_dir", "escaped_output_dir"])
def test_staged_private_values_are_rejected_without_printing_them(repository, field):
    root, private = repository
    values = {"code": private["utenze"][0]["codice"],
              "description": private["utenze"][0]["descrizione"],
              **private["credenziali"]["SPID_SIELTE"], **private["impostazioni"]}
    value = values["output_dir"] if field == "escaped_output_dir" else values[field]
    if field == "escaped_output_dir":
        value = json.dumps(value.replace("/", "\\"))[1:-1]
    path = root / "README.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n" + value, encoding="utf-8")
    git(root, "add", "README.md")
    with pytest.raises(RepositoryCheckError, match="dato privato") as error:
        check_repository(root, staged=True)
    assert value not in str(error.value)


def test_check_reads_the_actual_index_instead_of_unstaged_changes(repository):
    root, private = repository
    path = root / "README.md"
    original = path.read_text(encoding="utf-8")
    path.write_text(original + private["impostazioni"]["output_dir"], encoding="utf-8")
    assert check_repository(root, staged=True) > 0
    with pytest.raises(RepositoryCheckError, match="dato privato"):
        check_repository(root, staged=False)
    git(root, "add", "README.md")
    path.write_text(original, encoding="utf-8")
    with pytest.raises(RepositoryCheckError, match="dato privato"):
        check_repository(root, staged=True)


def test_force_added_configuration_is_rejected(repository):
    root, _ = repository
    git(root, "add", "-f", "config/config.json")
    with pytest.raises(RepositoryCheckError, match="non ammessi"):
        check_repository(root, staged=True)


def test_public_example_cannot_contain_a_download_default(repository):
    root, _ = repository
    path = root / "config/config.example.json"
    example = json.loads(path.read_text(encoding="utf-8"))
    example["impostazioni"]["output_dir"] = "./f24_output"
    path.write_text(json.dumps(example), encoding="utf-8")
    git(root, "add", "config/config.example.json")
    with pytest.raises(RepositoryCheckError, match="configurazione di esempio"):
        check_repository(root, staged=True)
