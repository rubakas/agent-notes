"""Diff installed state vs. newly built state."""

from __future__ import annotations
from typing import Optional
from ..domain.state import State, ScopeState, BackendState, InstalledItem
from ..domain.diff import ComponentDiff, StateDiff


def _get_color_and_version():
    """Get Color and version avoiding circular import."""
    from ..config import Color, get_version
    return Color, get_version


COMPONENT_TYPES = ("agents", "skills", "rules", "commands", "config", "settings")


def diff_scope_states(old_scope: Optional[ScopeState], new_scope: ScopeState) -> StateDiff:
    """Compare a specific ScopeState's clis against another ScopeState's clis."""
    if old_scope is None:
        old_scope = ScopeState()  # Empty scope for comparison
    
    # Determine backend changes
    old_backends = set(old_scope.clis.keys())
    new_backends = set(new_scope.clis.keys())
    
    added_backends = list(new_backends - old_backends)
    removed_backends = list(old_backends - new_backends)
    
    components = []
    
    # Process all backends that appear in either old or new
    all_backends = old_backends | new_backends
    
    for backend_name in sorted(all_backends):
        old_backend = old_scope.clis.get(backend_name, BackendState())
        new_backend = new_scope.clis.get(backend_name, BackendState())
        
        for component in COMPONENT_TYPES:
            old_items = old_backend.installed.get(component, {})
            new_items = new_backend.installed.get(component, {})
            
            old_keys = set(old_items.keys())
            new_keys = set(new_items.keys())
            
            added = list(new_keys - old_keys)
            removed = list(old_keys - new_keys)
            
            # Check for modifications (keys in both with different sha)
            modified = []
            unchanged = []
            for key in old_keys & new_keys:
                old_sha = old_items[key].sha
                new_sha = new_items[key].sha
                if old_sha != new_sha:
                    modified.append(key)
                else:
                    unchanged.append(key)
            
            # Only include ComponentDiff if there's any content
            if added or removed or modified or unchanged:
                components.append(ComponentDiff(
                    backend=backend_name,
                    component=component,
                    added=sorted(added),
                    removed=sorted(removed),
                    modified=sorted(modified),
                    unchanged=sorted(unchanged)
                ))
    
    # For version/commit, take from the overall State (not scope-specific)
    old_version = getattr(old_scope, 'version', None) if hasattr(old_scope, 'version') else None
    new_version = getattr(new_scope, 'version', '') if hasattr(new_scope, 'version') else ''
    old_commit = getattr(old_scope, 'source_commit', None) if hasattr(old_scope, 'source_commit') else None
    new_commit = getattr(new_scope, 'source_commit', '') if hasattr(new_scope, 'source_commit') else ''
    
    return StateDiff(
        old_version=old_version,
        new_version=new_version,
        old_commit=old_commit,
        new_commit=new_commit,
        added_backends=sorted(added_backends),
        removed_backends=sorted(removed_backends),
        components=components
    )


def diff_states(old: Optional[State], new: State) -> StateDiff:
    """Compute StateDiff between two full State objects.
    
    This is a compatibility shim that extracts the appropriate scopes and calls diff_scope_states.
    For now, it compares global scope if present in new, otherwise tries to find a matching local scope.
    """
    current_version = _get_color_and_version()[1]()  # Get version from VERSION file
    
    if old is None:
        # If there's a global install being created, compare that
        if new.global_install:
            temp_scope = ScopeState(
                installed_at=new.global_install.installed_at,
                updated_at=new.global_install.updated_at,
                mode=new.global_install.mode,
                clis=new.global_install.clis.copy()
            )
            # Copy state-level metadata to the scope for diff purposes
            setattr(temp_scope, 'version', current_version)
            setattr(temp_scope, 'source_commit', new.source_commit)
            return diff_scope_states(None, temp_scope)
        # If it's local-only, compare the first local install
        elif new.local_installs:
            first_local = next(iter(new.local_installs.values()))
            temp_scope = ScopeState(
                installed_at=first_local.installed_at,
                updated_at=first_local.updated_at,
                mode=first_local.mode,
                clis=first_local.clis.copy()
            )
            # Copy state-level metadata to the scope for diff purposes
            setattr(temp_scope, 'version', current_version)
            setattr(temp_scope, 'source_commit', new.source_commit)
            return diff_scope_states(None, temp_scope)
        else:
            # Empty new state
            temp_scope = ScopeState()
            setattr(temp_scope, 'version', current_version)
            setattr(temp_scope, 'source_commit', new.source_commit)
            return diff_scope_states(None, temp_scope)
    
    # For old state, try to get version info if it was set previously, otherwise use current version
    old_version = getattr(old, 'version', current_version)
    
    # Determine which scope to compare based on what exists in new
    if new.global_install:
        old_scope = old.global_install
        new_scope_raw = new.global_install
        # Create temporary scopes with metadata
        new_scope = ScopeState(
            installed_at=new_scope_raw.installed_at,
            updated_at=new_scope_raw.updated_at,
            mode=new_scope_raw.mode,
            clis=new_scope_raw.clis.copy()
        )
        setattr(new_scope, 'version', current_version)
        setattr(new_scope, 'source_commit', new.source_commit)
        
        if old_scope:
            old_scope_temp = ScopeState(
                installed_at=old_scope.installed_at,
                updated_at=old_scope.updated_at,
                mode=old_scope.mode,
                clis=old_scope.clis.copy()
            )
            setattr(old_scope_temp, 'version', old_version)
            setattr(old_scope_temp, 'source_commit', old.source_commit)
        else:
            old_scope_temp = None
            
        return diff_scope_states(old_scope_temp, new_scope)
    elif new.local_installs:
        # Find a matching local scope in old, or use None
        first_new_path = next(iter(new.local_installs.keys()))
        old_scope_raw = old.local_installs.get(first_new_path) if old.local_installs else None
        new_scope_raw = new.local_installs[first_new_path]
        
        new_scope = ScopeState(
            installed_at=new_scope_raw.installed_at,
            updated_at=new_scope_raw.updated_at,
            mode=new_scope_raw.mode,
            clis=new_scope_raw.clis.copy()
        )
        setattr(new_scope, 'version', current_version)
        setattr(new_scope, 'source_commit', new.source_commit)
        
        if old_scope_raw:
            old_scope = ScopeState(
                installed_at=old_scope_raw.installed_at,
                updated_at=old_scope_raw.updated_at,
                mode=old_scope_raw.mode,
                clis=old_scope_raw.clis.copy()
            )
            setattr(old_scope, 'version', old_version)
            setattr(old_scope, 'source_commit', old.source_commit)
        else:
            old_scope = None
            
        return diff_scope_states(old_scope, new_scope)
    else:
        # Empty new state - should not happen in practice
        temp_scope = ScopeState()
        setattr(temp_scope, 'version', current_version)
        setattr(temp_scope, 'source_commit', new.source_commit)
        return diff_scope_states(None, temp_scope)


def render_diff_report(diff: StateDiff, use_color: bool = True) -> str:
    """Return a human-readable report as a multi-line string.
    
    Format:
        agent-notes update: 3d447ca -> abc1234 (5 commits)

        + 2 new agents in claude:
            + analyst.md
            + devil.md
        ~ 1 agent updated in claude:
            ~ coder.md (content changed)
        - 1 skill removed in opencode:
            - rails-legacy

        Summary: +2 added, ~1 modified, -1 removed across 2 backends.
    """
    Color, _ = _get_color_and_version()
    
    if not use_color:
        # Create a color-disabled version
        class NoColor:
            GREEN = ""
            YELLOW = ""
            RED = ""
            CYAN = ""
            NC = ""
        color = NoColor()
    else:
        color = Color()
    
    if not diff.has_changes():
        return "No changes."
    
    lines = []
    
    # Header line
    if diff.old_commit and diff.new_commit:
        if diff.old_commit == diff.new_commit:
            header = f"agent-notes update: {diff.new_commit} (no new commits)"
        else:
            header = f"agent-notes update: {diff.old_commit} -> {diff.new_commit}"
    elif diff.new_commit:
        header = f"agent-notes update: initial install at {diff.new_commit}"
    else:
        header = "agent-notes update"
    
    lines.append(header)
    lines.append("")
    
    # Group by backend, then by component type
    backends_with_changes = {}
    for comp in diff.components:
        if comp.has_changes():
            if comp.backend not in backends_with_changes:
                backends_with_changes[comp.backend] = []
            backends_with_changes[comp.backend].append(comp)
    
    # Handle added/removed backends
    for backend in diff.added_backends:
        lines.append(f"{color.GREEN}+ New backend: {backend}{color.NC}")
    
    for backend in diff.removed_backends:
        lines.append(f"{color.RED}- Backend removed: {backend}{color.NC}")
    
    # Process component changes
    for backend_name in sorted(backends_with_changes.keys()):
        backend_components = backends_with_changes[backend_name]
        
        for comp in backend_components:
            if comp.added:
                count = len(comp.added)
                plural = "s" if count != 1 else ""
                lines.append(f"{color.GREEN}+ {count} new {comp.component}{plural} in {backend_name}:{color.NC}")
                
                items_to_show = comp.added[:20]  # Show max 20
                for item in items_to_show:
                    lines.append(f"    {color.GREEN}+ {item}{color.NC}")
                
                if len(comp.added) > 20:
                    remaining = len(comp.added) - 20
                    lines.append(f"    {color.GREEN}... and {remaining} more{color.NC}")
            
            if comp.modified:
                count = len(comp.modified)
                plural = "s" if count != 1 else ""
                lines.append(f"{color.YELLOW}~ {count} {comp.component}{plural} updated in {backend_name}:{color.NC}")
                
                items_to_show = comp.modified[:20]
                for item in items_to_show:
                    lines.append(f"    {color.YELLOW}~ {item} (content changed){color.NC}")
                
                if len(comp.modified) > 20:
                    remaining = len(comp.modified) - 20
                    lines.append(f"    {color.YELLOW}... and {remaining} more{color.NC}")
            
            if comp.removed:
                count = len(comp.removed)
                plural = "s" if count != 1 else ""
                lines.append(f"{color.RED}- {count} {comp.component}{plural} removed from {backend_name}:{color.NC}")
                
                items_to_show = comp.removed[:20]
                for item in items_to_show:
                    lines.append(f"    {color.RED}- {item}{color.NC}")
                
                if len(comp.removed) > 20:
                    remaining = len(comp.removed) - 20
                    lines.append(f"    {color.RED}... and {remaining} more{color.NC}")
    
    # Summary line
    if lines and lines[-1] != "":
        lines.append("")
    
    total_added = sum(len(c.added) for c in diff.components)
    total_modified = sum(len(c.modified) for c in diff.components)
    total_removed = sum(len(c.removed) for c in diff.components)
    backend_count = len(set(c.backend for c in diff.components if c.has_changes()))
    
    summary_parts = []
    if total_added:
        summary_parts.append(f"{color.GREEN}+{total_added} added{color.NC}")
    if total_modified:
        summary_parts.append(f"{color.YELLOW}~{total_modified} modified{color.NC}")
    if total_removed:
        summary_parts.append(f"{color.RED}-{total_removed} removed{color.NC}")
    
    if summary_parts:
        summary = f"Summary: {', '.join(summary_parts)} across {backend_count} backend{'s' if backend_count != 1 else ''}."
        lines.append(summary)
    
    return "\n".join(lines)


def filter_diff(diff: StateDiff, only: Optional[list[str]] = None) -> StateDiff:
    """Return a new StateDiff keeping only the listed component types.
    
    `only` can contain "agents", "skills", "rules", "commands", "config", "settings".
    If None or empty, return the diff unchanged.
    """
    if not only:
        return diff
    
    filtered_components = []
    for comp in diff.components:
        if comp.component in only:
            filtered_components.append(comp)
    
    return StateDiff(
        old_version=diff.old_version,
        new_version=diff.new_version,
        old_commit=diff.old_commit,
        new_commit=diff.new_commit,
        added_backends=diff.added_backends,
        removed_backends=diff.removed_backends,
        components=filtered_components
    )