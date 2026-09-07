"""
fake_provider.py
----------------
Wraps the `Faker` library to produce realistic names/addresses/phone numbers.

If the `faker` package is not installed in the environment, we fall back to a
tiny deterministic pseudo-Faker so the module still runs end-to-end (useful in
offline/sandboxed environments). In production simply `pip install faker` and
the real library will be used automatically -- no code changes required.
"""

import random
import string

try:
    from faker import Faker as _RealFaker
    _HAS_FAKER = True
except ImportError:  # pragma: no cover - exercised only when faker missing
    _HAS_FAKER = False


class _FallbackFaker:
    """Minimal stand-in exposing the subset of Faker's API this project uses."""

    _FIRST = ["James", "Maria", "Wei", "Anil", "Fatima", "Carlos", "Elena",
              "Kofi", "Sana", "Ivan", "Priya", "Diego", "Noor", "Liam",
              "Aisha", "Marco", "Yuki", "Omar", "Sofia", "Ravi"]
    _LAST = ["Silva", "Khan", "Ivanov", "Garcia", "Kumar", "Chen", "Mensah",
              "Rossi", "Petrov", "Diaz", "Nakamura", "Adeyemi", "Novak",
              "Fernandez", "Okafor", "Popescu", "Haddad", "Larsen"]
    _STREETS = ["Main St", "Baker Ave", "Church Rd", "Market Sq", "Union Blvd",
                "Harbor Dr", "Elm St", "Industrial Way", "Riverside Ln"]
    _CITIES = ["Riverport", "Newham", "Eastgate", "Westfield", "Lakeview",
               "Fort Dale", "Milbrook", "Grantville", "Cedar Falls"]

    def __init__(self, seed: int = 0):
        self._rng = random.Random(seed)

    def name(self):
        return f"{self._rng.choice(self._FIRST)} {self._rng.choice(self._LAST)}"

    def phone_number(self):
        return "+1-" + "".join(self._rng.choice(string.digits) for _ in range(10))

    def address(self):
        return (f"{self._rng.randint(1, 9999)} {self._rng.choice(self._STREETS)}, "
                f"{self._rng.choice(self._CITIES)}")

    def city(self):
        return self._rng.choice(self._CITIES)

    def seed_instance(self, seed):
        self._rng = random.Random(seed)


class FakeDataProvider:
    """Facade so the rest of the code doesn't care which backend is active."""

    def __init__(self, seed: int = 42):
        if _HAS_FAKER:
            self._faker = _RealFaker()
            self._faker.seed_instance(seed)
        else:
            self._faker = _FallbackFaker(seed)

    def full_name(self) -> str:
        return self._faker.name()

    def phone_number(self) -> str:
        return self._faker.phone_number()

    def address(self) -> str:
        return self._faker.address().replace("\n", ", ")

    def city(self) -> str:
        return self._faker.city()

    @property
    def backend(self) -> str:
        return "faker" if _HAS_FAKER else "fallback"
