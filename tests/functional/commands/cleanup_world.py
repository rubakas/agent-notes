"""A sandbox for reinstall tests: several HOMEs that share one dist rendered into tmp.

`use(name)` points HOME, XDG_CONFIG_HOME, AGENTS_HOME and the working directory at
that sandbox, so "A then B in one HOME" and "B alone in another" run against the same
dist and their trees can be compared (the oracle of spec 007 SC-001)."""
import hashlib
import os
from pathlib import Path
from unittest.mock import patch

import agent_notes.config as config
import agent_notes.commands.build as build_module
from agent_notes.commands.wizard.execute import _execute_install


class World:
    def __init__(self, tmp_path: Path, monkeypatch):
        self.root = tmp_path / "claude-501"
        self.mp = monkeypatch
        pkg = self.root / "pkg"
        pkg.mkdir(parents=True)
        self.dist = pkg / "dist"
        monkeypatch.setattr(config, "PKG_DIR", pkg)
        monkeypatch.setattr(config, "DIST_DIR", self.dist)
        monkeypatch.setattr(build_module, "DIST_DIR", self.dist)
        monkeypatch.setattr(config, "DIST_RULES_DIR", self.dist / "rules")
        monkeypatch.setattr(config, "DIST_SKILLS_DIR", self.dist / "skills")
        monkeypatch.setattr(config, "DIST_CLAUDE_DIR", self.dist / "claude")
        monkeypatch.setattr(config, "DIST_OPENCODE_DIR", self.dist / "opencode")
        monkeypatch.setattr(config, "DIST_GITHUB_DIR", self.dist / "copilot")
        self.use("main")
        build_module.build()

    def paths(self, name: str) -> dict:
        base = self.root / name
        return {"home": base / "home", "xdg": base / "xdg",
                "agents": base / "agents_home", "project": base / "project"}

    def use(self, name: str) -> "World":
        p = self.paths(name)
        for key in ("home", "project"):
            p[key].mkdir(parents=True, exist_ok=True)
        self.mp.setenv("HOME", str(p["home"]))
        self.mp.setenv("XDG_CONFIG_HOME", str(p["xdg"]))
        self.mp.setattr(config, "AGENTS_HOME", p["agents"])
        self.mp.chdir(p["project"])
        self.current = name
        return self

    @property
    def home(self) -> Path:
        return self.paths(self.current)["home"]

    @property
    def project(self) -> Path:
        return self.paths(self.current)["project"]

    @property
    def state_file(self) -> Path:
        return self.paths(self.current)["xdg"] / "agent-notes" / "state.json"

    def skills(self) -> list[str]:
        return sorted(d.name for d in (self.dist / "skills").iterdir() if d.is_dir())

    def wizard(self, *, scope="global", skills=None, clis=("claude",), copy=False,
               profile="", folder_overrides=None, global_home="", plugins=None,
               role_models=None, memory=("local", "")):
        with patch("agent_notes.memory.memory_router.memory_init"):
            _execute_install(
                clis=set(clis), scope=scope, copy_mode=copy,
                selected_skills=self.skills() if skills is None else list(skills),
                role_models=role_models or {}, memory_backend=memory[0], memory_path=memory[1],
                profile_label=profile, folder_overrides=folder_overrides,
                global_home_override=global_home, enabled_plugins=plugins)

    def dist_files(self) -> dict:
        """What the shared dist/ holds for claude, rules and commands: path -> sha."""
        return {p.relative_to(self.dist).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for sub in ("claude", "rules") for p in sorted((self.dist / sub).rglob("*"))
                if p.is_file()}

    def tree(self, name: str = None) -> dict:
        """Everything a sandbox holds: path -> link target, file sha or 'dir'.
        Backups (.bak.<ts>) are ignored, and the sandbox's own path is masked inside
        files (hook commands embed it)."""
        p = self.paths(name or self.current)
        base = str((self.root / (name or self.current))).encode()
        out = {}
        for label in ("home", "agents", "project"):
            root = p[label]
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if ".bak." in path.name:
                    continue
                key = f"{label}/{path.relative_to(root).as_posix()}"
                if path.is_symlink():
                    out[key] = ("link", os.readlink(path))
                elif path.is_dir():
                    out[key] = ("dir",)
                else:
                    content = path.read_bytes().replace(base, b"<sandbox>")
                    out[key] = ("file", hashlib.sha256(content).hexdigest())
        return out


def dangling(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_symlink() and not p.exists()]
