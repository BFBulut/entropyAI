#!/usr/bin/env python3
"""CLI utility for Entropy AI to programmatically synthesize new skills."""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(root_dir / "src"))

from entropy.skills.manager import SkillManager

def main():
    parser = argparse.ArgumentParser(description="Create a new skill programmatically")
    parser.add_argument("--name", required=True, help="Skill name (kebab-case)")
    parser.add_argument("--desc", required=True, help="Skill description")
    parser.add_argument("--instructions", required=True, help="Skill instructions markdown")
    args = parser.parse_args()

    mgr = SkillManager()
    skill = mgr.create_skill(args.name, args.desc, args.instructions)
    print(f"Skill '{skill.name}' successfully created at {skill.path}")

if __name__ == "__main__":
    main()
