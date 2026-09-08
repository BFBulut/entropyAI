"""
Soldier module alias for AgencySoldier.
"""

from agency_soldier import AgencySoldier, run_agency_soldier, generate_markdown_report

__all__ = ["AgencySoldier", "run_agency_soldier", "generate_markdown_report"]

if __name__ == "__main__":
    import sys
    soldier = AgencySoldier()
    sys.exit(soldier.main())
