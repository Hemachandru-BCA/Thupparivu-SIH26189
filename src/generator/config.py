"""
config.py
---------
Central configuration for the CriminalAnalysis AI synthetic data generator.
Keeping all tunable parameters in one place makes the simulation reproducible
and easy to scale up/down for testing.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SimulationConfig:
    # Volumes
    NUM_GANGS: int = 10
    NUM_PEOPLE: int = 5000
    NUM_CALLS: int = 50000
    NUM_TRANSACTIONS: int = 20000
    NUM_MEETINGS: int = 8000

    # Hidden coordinator behaviour
    NUM_HIDDEN_COORDINATORS: int = 6          # people who secretly influence multiple gangs
    MIN_GANGS_PER_COORDINATOR: int = 2
    MAX_GANGS_PER_COORDINATOR: int = 4
    COORDINATOR_INDIRECT_HOP_MIN: int = 1     # coordinator never calls a gang member directly;
    COORDINATOR_INDIRECT_HOP_MAX: int = 2     # instead reaches them via 1-2 intermediary "lieutenants"

    # Reproducibility
    RANDOM_SEED: int = 42

    # Output
    OUTPUT_DIR: str = "data/synthetic"

    # Roles within a gang
    ROLES = ("boss", "lieutenant", "member", "associate")
