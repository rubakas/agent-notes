"""Which install `agent-notes config` opens (spec 005 FR-014, SC-005)."""
from agent_notes.commands.config_review import InstallRef, default_install, list_installs
from agent_notes.domain.state import ScopeState, State


def _state(tmp_path, *, global_=False, profiles=(), locals_=()):
    return State(
        global_install=ScopeState() if global_ else None,
        global_installs={label: ScopeState() for label in profiles},
        local_installs={key: ScopeState() for key in locals_},
    )


def test_installs_are_listed_global_then_profiles_then_local(tmp_path):
    refs = list_installs(_state(tmp_path, global_=True, profiles=["work"], locals_=[str(tmp_path)]))
    assert refs == [InstallRef("global", None), InstallRef("global", None, "work"),
                    InstallRef("local", tmp_path)]


def test_a_profile_suffix_is_split_off_a_local_key(tmp_path):
    [ref] = list_installs(_state(tmp_path, locals_=[f"{tmp_path}#work"]))
    assert (ref.project_path, ref.profile_label) == (tmp_path, "work")


def test_a_hash_inside_an_existing_folder_name_stays_in_the_path(tmp_path):
    folder = tmp_path / "a#b"
    folder.mkdir()
    [ref] = list_installs(_state(tmp_path, locals_=[str(folder)]))
    assert (ref.project_path, ref.profile_label) == (folder, "")


def test_the_current_folder_install_wins(tmp_path):
    refs = list_installs(_state(tmp_path, global_=True, locals_=[str(tmp_path)]))
    assert default_install(refs, tmp_path) == InstallRef("local", tmp_path)


def test_the_default_profile_beats_a_named_one_in_the_same_folder(tmp_path):
    refs = [InstallRef("local", tmp_path, "work"), InstallRef("local", tmp_path)]
    assert default_install(refs, tmp_path) == InstallRef("local", tmp_path)


def test_a_named_profile_in_the_current_folder_is_used_when_it_is_the_only_one(tmp_path):
    refs = [InstallRef("global", None), InstallRef("local", tmp_path, "work")]
    assert default_install(refs, tmp_path) == InstallRef("local", tmp_path, "work")


def test_global_when_the_current_folder_has_no_install(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    refs = list_installs(_state(tmp_path, global_=True, locals_=[str(other)]))
    assert default_install(refs, tmp_path) == InstallRef("global", None)


def test_only_local_installs_elsewhere_means_ask(tmp_path):
    a, b, here = tmp_path / "a", tmp_path / "b", tmp_path / "here"
    for folder in (a, b, here):
        folder.mkdir()
    refs = list_installs(_state(tmp_path, locals_=[str(a), str(b)]))
    assert default_install(refs, here) is None


def test_a_single_install_is_chosen(tmp_path):
    a, here = tmp_path / "a", tmp_path / "here"
    a.mkdir()
    here.mkdir()
    refs = list_installs(_state(tmp_path, locals_=[str(a)]))
    assert default_install(refs, here) == InstallRef("local", a)


def test_a_deleted_project_is_marked_missing_and_never_chosen(tmp_path):
    gone, here = tmp_path / "gone", tmp_path / "here"
    here.mkdir()
    refs = list_installs(_state(tmp_path, locals_=[str(gone)]))
    assert refs[0].missing and refs[0].label().endswith("(missing)")
    assert default_install(refs, here) is None
