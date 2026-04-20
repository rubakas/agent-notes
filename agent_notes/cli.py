"""CLI entry point with argument parsing."""

import argparse
import sys

def main():
    parser = argparse.ArgumentParser(
        prog="agent-notes",
        description="AI agent configuration manager",
    )
    parser.add_argument("--version", "-v", action="store_true", help="Show version")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # install
    p_install = subparsers.add_parser("install", help="Build and install components")
    p_install.add_argument("--local", action="store_true", help="Install to current project")
    p_install.add_argument("--copy", action="store_true", help="Copy instead of symlink (with --local)")
    
    # build
    subparsers.add_parser("build", help="Build agent configuration files from source")
    
    # uninstall
    p_uninstall = subparsers.add_parser("uninstall", help="Remove installed components")
    p_uninstall.add_argument("--local", action="store_true", help="Remove from current project")
    
    # update
    subparsers.add_parser("update", help="Pull latest, rebuild, reinstall")
    
    # doctor
    p_doctor = subparsers.add_parser("doctor", help="Check installation health")
    p_doctor.add_argument("--local", action="store_true", help="Check local installation")
    p_doctor.add_argument("--fix", action="store_true", help="Fix found issues")
    
    # info
    subparsers.add_parser("info", help="Show status and component counts")
    
    # list
    p_list = subparsers.add_parser("list", help="List installed components")
    p_list.add_argument("filter", nargs="?", default="all", choices=["agents", "skills", "rules", "all"])
    
    # validate
    subparsers.add_parser("validate", help="Lint source configuration files")
    
    # memory
    p_memory = subparsers.add_parser("memory", help="Manage agent memory")
    p_memory.add_argument("action", nargs="?", default="list", choices=["list", "size", "show", "reset", "export", "import"])
    p_memory.add_argument("name", nargs="?", help="Agent name (for show/reset)")
    
    args = parser.parse_args()
    
    if args.version:
        from .config import get_version
        print(f"agent-notes {get_version()}")
        return
    
    if not args.command:
        parser.print_help()
        return
    
    # Route to modules
    if args.command == "build":
        from .build import build
        build()
    elif args.command == "install":
        if args.local or args.copy:
            from .install import install
            install(local=args.local, copy=args.copy)
        else:
            from .wizard import interactive_install
            interactive_install()
    elif args.command == "uninstall":
        from .install import uninstall
        uninstall(local=args.local)
    elif args.command == "update":
        from .update import update
        update()
    elif args.command == "doctor":
        from .doctor import doctor
        doctor(local=args.local, fix=args.fix)
    elif args.command == "info":
        from .install import show_info
        show_info()
    elif args.command == "list":
        from .list import list_components
        list_components(args.filter)
    elif args.command == "validate":
        from .validate import validate
        validate()
    elif args.command == "memory":
        from .memory import memory
        memory(args.action, args.name)

if __name__ == "__main__":
    main()