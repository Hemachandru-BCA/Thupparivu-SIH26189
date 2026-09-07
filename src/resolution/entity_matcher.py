"""Entity matching and resolution utilities.

This module provides a reusable, configurable entity-resolution toolkit:

- String normalization (Unicode folding, punctuation removal, honorific stripping)
- Levenshtein distance / similarity (pure Python, no external dependencies)
- Standard American Soundex phonetic codes
- Fuzzy similarity (``difflib.SequenceMatcher`` ratio)
- Token-aware alignment with first-initial support (``"J. Doe"`` ~ ``"John Doe"``)
- Configurable weighted scoring with conservative "strong evidence" gates
- Union-find clustering of equivalent mentions into canonical entities
- Deterministic (stable) GUID assignment via ``uuid5``
- Alias bookkeeping and original-name -> GUID mapping

The module has **no** graph, FastAPI, or file-system dependencies, so it can be
used standalone in other pipelines. Typical usage::

    from entity_matcher import EntityResolver, MatchConfig, EntityMention

    resolver = EntityResolver(MatchConfig(combined_threshold=0.80))
    result = resolver.resolve_names(["John Doe", "J. Doe", "Jon Doe"])
    print(result.entities[0].canonical_name)   # -> "John Doe"
    print(result.name_to_guid)                 # -> {"John Doe": "<guid>", ...}

All thresholds, component weights and behaviour switches live in
:class:`MatchConfig`; nothing is hard-coded to a particular dataset.
"""

from __future__ import annotations

import logging
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

__all__ = [
    "MatchConfig",
    "MatchResult",
    "TokenAlignment",
    "EntityMention",
    "ResolvedEntity",
    "ResolutionResult",
    "EntityResolver",
    "EntityResolutionError",
    "normalize_name",
    "tokenize",
    "levenshtein_distance",
    "levenshtein_similarity",
    "soundex",
    "fuzzy_similarity",
    "compare_names",
]


class EntityResolutionError(RuntimeError):
    """Raised when entity resolution cannot proceed (e.g. invalid config)."""


# --------------------------------------------------------------------------
# Normalization
# --------------------------------------------------------------------------

#: Tokens that are removed from the *front* of a name (configurable).
DEFAULT_HONORIFICS: frozenset = frozenset(
    {"mr", "mrs", "ms", "miss", "dr", "prof", "professor", "sir", "madam", "rev", "hon"}
)

#: Tokens that are removed from the *end* of a name (configurable).
DEFAULT_SUFFIXES: frozenset = frozenset(
    {"jr", "sr", "ii", "iii", "iv", "phd", "md", "esq"}
)

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+", re.UNICODE)


def normalize_name(
    name: Any,
    *,
    strip_honorifics: bool = True,
    honorifics: Optional[frozenset] = None,
    suffixes: Optional[frozenset] = None,
) -> str:
    """Return a canonical, comparison-ready form of ``name``.

    Steps:
      1. NFKD Unicode normalization + removal of combining marks (accents).
      2. Lowercasing.
      3. Punctuation replaced by spaces, whitespace collapsed.
      4. Optional removal of honorific/suffix tokens (``"dr"``, ``"jr"``, ...).

    Malformed input (``None``, non-strings, empty strings) degrades gracefully
    to an empty string so callers can skip the mention instead of crashing.

    Args:
        name: The raw surface form of an entity name.
        strip_honorifics: Whether to drop honorific/suffix tokens.
        honorifics: Override for the front-token stop list.
        suffixes: Override for the tail-token stop list.

    Returns:
        The normalized name (possibly empty string).
    """
    if not isinstance(name, str):
        if name is not None:
            logger.debug("normalize_name received non-string input %r; ignoring", name)
        return ""

    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    tokens = _WS_RE.sub(" ", text).strip().split(" ")
    tokens = [t for t in tokens if t]

    if strip_honorifics:
        front = honorifics if honorifics is not None else DEFAULT_HONORIFICS
        back = suffixes if suffixes is not None else DEFAULT_SUFFIXES
        while tokens and tokens[0] in front:
            tokens.pop(0)
        while tokens and tokens[-1] in back:
            tokens.pop()

    return " ".join(tokens)


def tokenize(name: str) -> List[str]:
    """Split an already-normalized name into its tokens."""
    return name.split(" ") if name else []


# --------------------------------------------------------------------------
# Character-level similarity
# --------------------------------------------------------------------------

def levenshtein_distance(a: str, b: str) -> int:
    """Compute the Levenshtein edit distance between two strings.

    Pure-Python implementation using a rolling single-row DP table
    (O(len(a) * len(b)) time, O(min(len)) space). Empty/None strings are
    treated as zero-length strings.
    """
    if a is None:
        a = ""
    if b is None:
        b = ""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    # Keep the inner loop over the shorter string.
    if len(a) > len(b):
        a, b = b, a

    previous = list(range(len(a) + 1))
    for j, ch_b in enumerate(b, start=1):
        current = [j]
        for i, ch_a in enumerate(a, start=1):
            substitution = previous[i - 1] + (ch_a != ch_b)
            current.append(min(previous[i] + 1, current[i - 1] + 1, substitution))
        previous = current
    return previous[-1]


def levenshtein_similarity(a: str, b: str) -> float:
    """Normalized Levenshtein similarity in ``[0.0, 1.0]``.

    ``1.0`` means identical, ``0.0`` means completely different. Two empty
    strings are considered identical.
    """
    if not a and not b:
        return 1.0
    longest = max(len(a), len(b))
    if longest == 0:
        return 1.0
    return 1.0 - (levenshtein_distance(a, b) / longest)


def fuzzy_similarity(a: str, b: str) -> float:
    """Fuzzy string similarity via :meth:`difflib.SequenceMatcher.ratio`.

    Captures common-substring similarity that raw edit distance under-scores
    (e.g. reordered words, insertions in the middle of long names).
    """
    if not a and not b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


# --------------------------------------------------------------------------
# Soundex
# --------------------------------------------------------------------------

_SOUNDEX_MAP: Dict[str, str] = {}
for _letters, _code in (
    ("BFPV", "1"),
    ("CGJKQSXZ", "2"),
    ("DT", "3"),
    ("L", "4"),
    ("MN", "5"),
    ("R", "6"),
):
    for _ch in _letters:
        _SOUNDEX_MAP[_ch] = _code
_VOWELS = frozenset("AEIOUY")
_H_W = frozenset("HW")


def soundex(token: str) -> str:
    """Return the standard American Soundex code for ``token``.

    Examples: ``Robert -> R163``, ``Rupert -> R163``, ``Ashcraft -> A261``,
    ``Tymczak -> T522``, ``Pfister -> P236``, ``Honeyman -> H555``.

    Non-alphabetic characters are ignored. An empty/blank token yields ``""``.
    """
    if not token:
        return ""
    letters = [ch for ch in token.upper() if ch.isalpha()]
    if not letters:
        return ""

    first = letters[0]
    codes: List[str] = []
    prev = _SOUNDEX_MAP.get(first, "")
    for ch in letters[1:]:
        if ch in _H_W:
            # H and W are transparent: they neither code nor reset duplicates.
            continue
        code = _SOUNDEX_MAP.get(ch)
        if code:
            if code != prev:
                codes.append(code)
            prev = code
        else:
            # Vowels (and Y) act as separators: they reset the duplicate check.
            prev = ""
        if len(codes) == 3:
            break
    return (first + "".join(codes) + "000")[:4]


# --------------------------------------------------------------------------
# Token-level alignment (with first-initial support)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class TokenAlignment:
    """Result of aligning two token sequences.

    Attributes:
        score: Overall alignment score in ``[0.0, 1.0]`` (gaps score 0).
        initials_used: True when at least one pair matched via the
            single-letter-initial rule (e.g. ``"j"`` ~ ``"john"``).
        pairs: The aligned ``(token_a, token_b, score)`` triples.
    """

    score: float
    initials_used: bool
    pairs: Tuple[Tuple[str, str, float], ...]


def _pair_score(t1: str, t2: str, initial_match_score: float) -> Tuple[float, bool]:
    """Score a single token pair; returns ``(score, initials_used)``."""
    if t1 == t2:
        return 1.0, False
    if initial_match_score > 0 and (len(t1) == 1 or len(t2) == 1):
        if t1[0] == t2[0]:
            return initial_match_score, True
        return 0.0, False
    return levenshtein_similarity(t1, t2), False


def token_alignment(
    tokens_a: Sequence[str],
    tokens_b: Sequence[str],
    *,
    initial_match_score: float = 1.0,
) -> TokenAlignment:
    """Find the best pairwise alignment between two token sequences.

    A small dynamic-programming sequence alignment (gaps allowed, gaps score
    0.0) maximising the summed pair score, normalized by the longer token
    count. Single-letter tokens can match tokens sharing their first letter
    (scored ``initial_match_score``), which is what makes ``"J. Doe"`` match
    ``"John Doe"``.
    """
    n, m = len(tokens_a), len(tokens_b)
    if n == 0 or m == 0:
        return TokenAlignment(0.0, False, ())

    # dp[i][j] = (best_sum, initials_used, pairs)
    dp: Dict[Tuple[int, int], Tuple[float, bool, Tuple]] = {}

    def solve(i: int, j: int) -> Tuple[float, bool, Tuple]:
        if i == n or j == m:
            return 0.0, False, ()
        key = (i, j)
        if key in dp:
            return dp[key]

        pair_s, pair_init = _pair_score(tokens_a[i], tokens_b[j], initial_match_score)
        take = solve(i + 1, j + 1)
        take_val = (pair_s + take[0], pair_init or take[1], ((tokens_a[i], tokens_b[j], pair_s),) + take[2])

        skip_a = solve(i + 1, j)
        skip_b = solve(i, j + 1)

        best = max(take_val, skip_a, skip_b)  # tuples compare by score first
        dp[key] = best
        return best

    total, initials_used, pairs = solve(0, 0)
    norm = max(n, m)
    return TokenAlignment(total / norm if norm else 0.0, initials_used, pairs)


def _soundex_pair_score(t1: str, t2: str, initials_enabled: bool) -> float:
    """Phonetic pair score: Soundex equality (with initial-token support)."""
    s1, s2 = soundex(t1), soundex(t2)
    if s1 and s1 == s2:
        return 1.0
    if initials_enabled and (len(t1) == 1 or len(t2) == 1):
        return 1.0 if (t1[0] == t2[0] and bool(s1) == bool(s2)) else 0.0
    return 0.0


# --------------------------------------------------------------------------
# Configuration and pairwise comparison
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class MatchConfig:
    """Configuration for entity matching. Every knob is adjustable.

    Scoring model
    -------------
    ``score`` is the weighted mean of the active components:

    - ``weight_levenshtein``: full-string normalized Levenshtein similarity
    - ``weight_fuzzy``: full-string ``SequenceMatcher`` ratio
    - ``weight_token``: DP token-alignment score (includes first-initial rule)
    - ``weight_soundex``: phonetic token-alignment score

    A pair merges when ``score >= combined_threshold`` **and** at least one
    *strong-evidence gate* passes (this prevents coarse phonetic matches such
    as ``John`` ~ ``Jane`` from merging on their own):

    - ``levenshtein_strong``: ``levenshtein_similarity >= levenshtein_threshold``
    - ``initials_match``: an initial-vs-token pair was used and
      ``levenshtein_similarity >= initials_min_levenshtein``
    - ``soundex_strong``: all aligned tokens are Soundex-equal and
      ``levenshtein_similarity >= soundex_min_levenshtein``
    - ``token_set_equal``: the two names contain the same tokens (order-insensitive,
      e.g. ``"Doe, John"`` ~ ``"John Doe"``), if ``allow_token_reorder``

    Exact normalized-string equality always merges.
    """

    # Component weights (renormalized over active components at scoring time).
    weight_levenshtein: float = 0.35
    weight_fuzzy: float = 0.15
    weight_token: float = 0.25
    weight_soundex: float = 0.25

    # Decision thresholds.
    combined_threshold: float = 0.80
    levenshtein_threshold: float = 0.85
    initials_min_levenshtein: float = 0.55
    soundex_min_levenshtein: float = 0.75
    token_min_levenshtein: float = 0.50

    # Behaviour switches.
    initial_match_score: float = 1.0
    soundex_enabled: bool = True
    fuzzy_enabled: bool = True
    initials_enabled: bool = True
    allow_token_reorder: bool = True
    use_first_letter_prefilter: bool = True
    strip_honorifics: bool = True

    # Canonical-name selection: "frequency_then_completeness" | "longest" | "first_seen"
    canonical_strategy: str = "frequency_then_completeness"

    def active_weights(self) -> Dict[str, float]:
        """Return the active component weights, renormalized to sum to 1.0."""
        weights = {"levenshtein": self.weight_levenshtein}
        if self.fuzzy_enabled:
            weights["fuzzy"] = self.weight_fuzzy
        weights["token"] = self.weight_token
        if self.soundex_enabled:
            weights["soundex"] = self.weight_soundex
        total = sum(weights.values())
        if total <= 0:
            raise EntityResolutionError("At least one component weight must be positive")
        return {k: v / total for k, v in weights.items()}


@dataclass(frozen=True)
class MatchResult:
    """Outcome of comparing two surface names.

    Attributes:
        name_a / name_b: The original (non-normalized) inputs.
        matched: Whether the two names should be merged.
        score: Combined weighted similarity score in ``[0.0, 1.0]``.
        components: Individual component scores (``levenshtein``, ``fuzzy``,
            ``token``, ``soundex``) for debugging / explainability.
        reason: Short machine-readable explanation of the decision.
    """

    name_a: str
    name_b: str
    matched: bool
    score: float
    components: Dict[str, float] = field(default_factory=dict)
    reason: str = ""

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return (
            f"MatchResult({self.name_a!r} ~ {self.name_b!r}: "
            f"matched={self.matched}, score={self.score:.3f}, reason={self.reason})"
        )


def compare_names(name_a: str, name_b: str, config: Optional[MatchConfig] = None) -> MatchResult:
    """Compare two surface names and decide whether they are the same entity.

    Fully stateless and reusable; :class:`EntityResolver` uses this internally
    for pairwise candidate comparison.
    """
    cfg = config or MatchConfig()

    norm_a = normalize_name(name_a, strip_honorifics=cfg.strip_honorifics)
    norm_b = normalize_name(name_b, strip_honorifics=cfg.strip_honorifics)

    if not norm_a or not norm_b:
        return MatchResult(name_a, name_b, False, 0.0, {}, "empty_normalized_name")

    # 1) Exact normalized match always merges.
    if norm_a == norm_b:
        return MatchResult(name_a, name_b, True, 1.0, {"exact_normalized": 1.0}, "exact_normalized")

    tokens_a, tokens_b = tokenize(norm_a), tokenize(norm_b)

    # 2) Cheap conservative prefilter: any high-scoring alignment requires at
    #    least one shared token initial.
    if cfg.use_first_letter_prefilter:
        if not ({t[0] for t in tokens_a} & {t[0] for t in tokens_b}):
            return MatchResult(name_a, name_b, False, 0.0, {}, "prefilter_first_letter_mismatch")

    # 3) Order-insensitive token-set equality (e.g. "Doe, John" vs "John Doe").
    if cfg.allow_token_reorder and sorted(tokens_a) == sorted(tokens_b):
        return MatchResult(name_a, name_b, True, 1.0, {"token_set": 1.0}, "token_set_equal")

    # 4) Weighted component scoring.
    components: Dict[str, float] = {
        "levenshtein": levenshtein_similarity(norm_a, norm_b)
    }
    if cfg.fuzzy_enabled:
        components["fuzzy"] = fuzzy_similarity(norm_a, norm_b)

    alignment = token_alignment(
        tokens_a, tokens_b, initial_match_score=cfg.initial_match_score if cfg.initials_enabled else 0.0
    )
    components["token"] = alignment.score

    soundex_score = 0.0
    snd_pairs: List[float] = []
    if cfg.soundex_enabled:
        # Soundex scoring reuses the token alignment pairs with a phonetic scorer.
        for ta, tb, _s in alignment.pairs:
            snd_pairs.append(_soundex_pair_score(ta, tb, cfg.initials_enabled))
        soundex_score = (sum(snd_pairs) / max(len(tokens_a), len(tokens_b))) if snd_pairs else 0.0
        components["soundex"] = soundex_score

    weights = cfg.active_weights()
    score = sum(weights[k] * components[k] for k in weights)
    score = max(0.0, min(1.0, score))

    if score < cfg.combined_threshold:
        return MatchResult(name_a, name_b, False, score, components, "below_threshold")

    # 5) Strong-evidence gates.
    lev = components["levenshtein"]
    if lev >= cfg.levenshtein_threshold:
        reason = "levenshtein_strong"
    elif cfg.initials_enabled and alignment.initials_used and lev >= cfg.initials_min_levenshtein:
        reason = "initials_match"
    elif (
        cfg.soundex_enabled
        and snd_pairs
        and all(s >= 0.999 for s in snd_pairs)
        and lev >= cfg.soundex_min_levenshtein
    ):
        reason = "soundex_strong"
    elif components["token"] >= 0.999 and lev >= cfg.token_min_levenshtein:
        reason = "token_exact"
    else:
        return MatchResult(
            name_a, name_b, False, score, components, "threshold_met_but_no_strong_gate"
        )

    return MatchResult(name_a, name_b, True, score, components, reason)


# --------------------------------------------------------------------------
# Mentions, entities, resolution
# --------------------------------------------------------------------------

#: Sentinel type key for mentions that carry no ``entity_type``.
_UNTYPED = "__untyped__"

#: Default deterministic UUID namespace (uuid5 of a fixed URL string).
GUID_NAMESPACE: uuid.UUID = uuid.uuid5(
    uuid.NAMESPACE_URL, "entity-resolution/graph-pipeline/v1"
)


@dataclass
class EntityMention:
    """A single occurrence of an entity name in the source data.

    Attributes:
        name: Raw surface form (case/punctuation preserved).
        entity_type: Optional type hint (``person``, ``organization``, ...).
            Mentions with conflicting types are never merged.
        attributes: Any extra attributes carried by the mention.
        source_index: Optional index of the record the mention came from.
    """

    name: str
    entity_type: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    source_index: Optional[int] = None
    occurrences: int = 1


@dataclass
class ResolvedEntity:
    """A canonical entity produced by resolution.

    Attributes:
        guid: Stable, deterministic GUID (uuid5 of type + canonical name).
        canonical_name: The best surface form representing the cluster.
        aliases: All known surface forms, ordered by frequency then appearance.
        entity_type: Cluster type (mode of member types, ``None`` if untyped).
        attributes: Merged attributes from all member mentions (last wins).
        mention_count: Number of raw mentions collapsed into this entity.
        name_counts: Surface form -> occurrence count.
    """

    guid: str
    canonical_name: str
    aliases: List[str]
    entity_type: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    mention_count: int = 0
    name_counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation (as shown in the project spec)."""
        return {
            "guid": self.guid,
            "canonical_name": self.canonical_name,
            "aliases": list(self.aliases),
        }


@dataclass
class ResolutionResult:
    """Full output of one resolution run.

    Attributes:
        entities: Canonical entities (one per cluster).
        name_to_guid: Exact original surface name -> GUID mapping.
        normalized_to_guid: Normalized name -> GUID mapping.
        stats: Aggregate counters (mentions, unique names, clusters, ...).
        merge_groups: Clusters that merged more than one distinct surface name
            (useful for explaining what entity resolution changed).
    """

    entities: List[ResolvedEntity] = field(default_factory=list)
    name_to_guid: Dict[str, str] = field(default_factory=dict)
    normalized_to_guid: Dict[str, str] = field(default_factory=dict)
    stats: Dict[str, Any] = field(default_factory=dict)
    merge_groups: List[Dict[str, Any]] = field(default_factory=list)

    def to_er_summary(self) -> Dict[str, Any]:
        """Compact entity-resolution summary for ``graph_metrics.json``."""
        return {
            "original_mention_count": self.stats.get("original_mentions", 0),
            "original_unique_names": self.stats.get("original_unique_names", 0),
            "resolved_entity_count": self.stats.get("resolved_entities", 0),
            "merge_group_count": len(self.merge_groups),
            "merge_groups": self.merge_groups,
            "name_to_guid": dict(self.name_to_guid),
        }


class EntityResolver:
    """Clusters entity mentions into canonical entities.

    Clustering uses **complete-linkage** agglomeration: matched pairs are
    processed in descending score order and two clusters are only merged when
    *every* cross-pair between them matches. This prevents an ambiguous
    mention (e.g. the initial form ``"J. Doe"``) from bridging two otherwise
    distinct entities (``"John Doe"`` vs ``"Jane Doe"``) through transitivity.

    The resolver is reusable across datasets: pass a different
    :class:`MatchConfig` (thresholds, weights, behaviour) per use case and a
    ``guid_namespace`` string to keep GUID spaces separate.

    Usage::

        resolver = EntityResolver()
        result = resolver.resolve_names(["John Doe", "J. Doe", "Jon Doe"])
        assert len(result.entities) == 1
    """

    def __init__(
        self,
        config: Optional[MatchConfig] = None,
        *,
        guid_namespace: Optional[str] = None,
        strict_type_separation: bool = True,
    ) -> None:
        """Create a resolver.

        Args:
            config: Matching configuration; defaults to :class:`MatchConfig`().
            guid_namespace: Optional namespace string. GUIDs are derived with
                ``uuid5(namespace, "<type>::<normalized canonical name>")`` so
                they remain *stable across runs* for the same canonical input.
            strict_type_separation: When True (default), mentions with
                different (or missing vs present) entity types are never
                compared. When False, untyped mentions are allowed to match
                typed ones.
        """
        self.config = config or MatchConfig()
        self.strict_type_separation = strict_type_separation
        self.guid_namespace = (
            GUID_NAMESPACE
            if guid_namespace is None
            else uuid.uuid5(uuid.NAMESPACE_URL, guid_namespace)
        )

    # -- public API ---------------------------------------------------------

    def resolve(self, mentions: Iterable[EntityMention]) -> ResolutionResult:
        """Resolve an iterable of mentions into canonical entities."""
        entries: List[EntityMention] = []
        for idx, mention in enumerate(mentions):
            if mention is None or not isinstance(mention.name, str):
                logger.debug("Skipping malformed mention at position %d", idx)
                continue
            if not mention.name.strip():
                logger.debug("Skipping blank mention at position %d", idx)
                continue
            entries.append(mention)

        if not entries:
            return ResolutionResult(
                stats={
                    "original_mentions": 0,
                    "original_unique_names": 0,
                    "resolved_entities": 0,
                }
            )

        # Collapse exact-normalized duplicates before fuzzy matching. Synthetic
        # event extraction can legitimately mention the same person thousands
        # of times; comparing those repeated mentions pairwise is needless O(k²)
        # work and was the main scalability failure in the shipped pipeline.
        collapsed: Dict[Tuple[str, str], EntityMention] = {}
        for mention in entries:
            typ = (mention.entity_type or "").strip().lower() if isinstance(mention.entity_type, str) else ""
            norm = normalize_name(mention.name, strip_honorifics=self.config.strip_honorifics)
            key = (typ, norm)
            existing = collapsed.get(key)
            if existing is None:
                collapsed[key] = EntityMention(
                    name=mention.name, entity_type=mention.entity_type,
                    attributes=dict(mention.attributes), source_index=mention.source_index, occurrences=getattr(mention, "occurrences", 1)
                )
            else:
                existing.occurrences += getattr(mention, "occurrences", 1)
                if mention.attributes:
                    existing.attributes.update(mention.attributes)
        entries = list(collapsed.values())

        # Normalize the entity types once (lower-cased; None when absent).
        types = [
            (e.entity_type or "").strip().lower() or None if isinstance(e.entity_type, str) else None
            for e in entries
        ]

        # Blocking: only compare within the same type group (strict mode), or
        # additionally untyped-vs-typed when strict separation is disabled.
        groups: Dict[str, List[int]] = {}
        for i, t in enumerate(types):
            groups.setdefault(t or _UNTYPED, []).append(i)

        def comparable(i: int, j: int) -> bool:
            ti, tj = types[i], types[j]
            if ti is not None and tj is not None:
                return ti == tj
            if ti is None and tj is None:
                return True
            # One typed, one untyped:
            return not self.strict_type_separation

        candidate_pairs: List[Tuple[int, int]] = []
        # Exact-normalized entities such as ACCOUNT/PHONE/LOCATION do not need
        # an O(n²) fuzzy pass. Fuzzy comparison is retained for PERSON/ORG,
        # but blocked by name shape so large synthetic runs stay tractable.
        normalized = [normalize_name(e.name, strip_honorifics=self.config.strip_honorifics) for e in entries]
        for typ, members in groups.items():
            if typ not in {"person", "organization"}:
                by_norm: Dict[str, List[int]] = {}
                for i in members:
                    by_norm.setdefault(normalized[i], []).append(i)
                for same in by_norm.values():
                    for x in range(len(same)):
                        for y in range(x + 1, len(same)):
                            candidate_pairs.append((same[x], same[y]))
                continue
            blocks: Dict[Tuple[str, str, int], List[int]] = {}
            for i in members:
                toks = normalized[i].split()
                key = ((toks[0][0] if toks and toks[0] else ""),
                       (toks[-1][0] if toks and toks[-1] else ""), len(toks))
                blocks.setdefault(key, []).append(i)
            for bucket in blocks.values():
                for x in range(len(bucket)):
                    for y in range(x + 1, len(bucket)):
                        candidate_pairs.append((bucket[x], bucket[y]))

        if not self.strict_type_separation:
            untyped = groups.get(_UNTYPED, [])
            for i in untyped:
                for j in range(len(entries)):
                    if i != j and types[j] is not None:
                        candidate_pairs.append((i, j) if i < j else (j, i))

        # 1) Pairwise comparison of all candidate pairs.
        verdicts: Dict[Tuple[int, int], MatchResult] = {}
        for i, j in candidate_pairs:
            if not comparable(i, j):
                continue
            verdicts[(i, j)] = compare_names(entries[i].name, entries[j].name, self.config)

        # 2) Complete-linkage agglomerative clustering. Process matched pairs
        #    by descending score, but only merge two clusters when EVERY
        #    cross-pair between them also matched. This stops an ambiguous
        #    mention (e.g. an initial like "J. Doe") from bridging two
        #    otherwise-distinct entities via transitivity.
        matched_pairs = sorted(
            ((v.score, i, j) for (i, j), v in verdicts.items() if v.matched),
            key=lambda t: (-t[0], t[1], t[2]),
        )

        cluster_of: Dict[int, int] = {i: i for i in range(len(entries))}
        clusters: Dict[int, Set[int]] = {i: {i} for i in range(len(entries))}

        def _key(a: int, b: int) -> Tuple[int, int]:
            return (a, b) if a < b else (b, a)

        for _score, i, j in matched_pairs:
            ci, cj = cluster_of[i], cluster_of[j]
            if ci == cj:
                continue
            cross_ok = True
            for a in clusters[ci]:
                for b in clusters[cj]:
                    verdict = verdicts.get(_key(a, b))
                    if verdict is None or not verdict.matched:
                        cross_ok = False
                        break
                if not cross_ok:
                    break
            if not cross_ok:
                continue
            if cj < ci:
                ci, cj = cj, ci  # deterministic: merge into the smaller root id
            clusters[ci] |= clusters[cj]
            for m in clusters[cj]:
                cluster_of[m] = ci
            del clusters[cj]

        # 3) Materialize clusters deterministically (sorted root ids, sorted members).
        member_groups: List[List[int]] = [
            sorted(members) for _, members in sorted(clusters.items())
        ]

        entities: List[ResolvedEntity] = []
        seen_names: Dict[str, str] = {}
        seen_norms: Dict[str, str] = {}
        merge_groups: List[Dict[str, Any]] = []

        for members in member_groups:
            member_entries = [entries[i] for i in members]
            entity = self._build_entity(member_entries)
            entities.append(entity)

            for surface in entity.aliases:
                seen_names.setdefault(surface, entity.guid)
            for surface in entity.name_counts:
                norm = normalize_name(surface, strip_honorifics=self.config.strip_honorifics)
                seen_norms.setdefault(norm, entity.guid)
            distinct = set(entity.name_counts)
            if len(distinct) > 1:
                merge_groups.append(
                    {
                        "guid": entity.guid,
                        "canonical_name": entity.canonical_name,
                        "aliases": list(entity.aliases),
                    }
                )

        entities.sort(key=lambda e: e.canonical_name.lower())
        unique_names = len({e.name for e in entries})
        stats = {
            "original_mentions": len(entries),
            "original_unique_names": unique_names,
            "resolved_entities": len(entities),
            "merged_cluster_count": len(merge_groups),
        }
        return ResolutionResult(
            entities=entities,
            name_to_guid=seen_names,
            normalized_to_guid=seen_norms,
            stats=stats,
            merge_groups=merge_groups,
        )

    def resolve_names(self, names: Iterable[str]) -> ResolutionResult:
        """Convenience wrapper: resolve bare name strings (untyped mentions)."""
        return self.resolve(EntityMention(name=n) for n in names)

    # -- internals -----------------------------------------------------------

    def _build_entity(self, members: Sequence[EntityMention]) -> ResolvedEntity:
        """Collapse one cluster of mentions into a :class:`ResolvedEntity`."""
        counts: Dict[str, int] = {}
        first_seen: Dict[str, int] = {}
        attrs: Dict[str, Any] = {}
        type_counts: Dict[str, int] = {}

        for pos, m in enumerate(members):
            name = m.name.strip()
            counts[name] = counts.get(name, 0) + getattr(m, "occurrences", 1)
            first_seen.setdefault(name, pos)
            if m.attributes:
                attrs.update(m.attributes)  # last-wins merge
            if m.entity_type:
                key = m.entity_type.strip()
                if key:
                    type_counts[key] = type_counts.get(key, 0) + 1

        canonical = self._select_canonical(counts, first_seen)
        entity_type: Optional[str] = None
        if type_counts:
            entity_type = max(type_counts.items(), key=lambda kv: (kv[1], kv[0]))[0]

        aliases = sorted(
            counts,
            key=lambda n: (-counts[n], first_seen[n]),
        )
        norm_canonical = normalize_name(canonical, strip_honorifics=self.config.strip_honorifics)
        type_key = entity_type.strip().lower() if entity_type else "entity"
        guid = str(uuid.uuid5(self.guid_namespace, f"{type_key}::{norm_canonical}"))

        return ResolvedEntity(
            guid=guid,
            canonical_name=canonical,
            aliases=aliases,
            entity_type=entity_type,
            attributes=attrs,
            mention_count=sum(getattr(m, "occurrences", 1) for m in members),
            name_counts=counts,
        )

    def _select_canonical(self, counts: Mapping[str, int], first_seen: Mapping[str, int]) -> str:
        """Pick the canonical surface form according to ``canonical_strategy``."""
        strategy = self.config.canonical_strategy
        if strategy == "first_seen":
            return min(counts, key=lambda n: first_seen[n])
        if strategy == "longest":
            return max(counts, key=lambda n: (len(tokenize(normalize_name(n))), len(n), n))
        if strategy != "frequency_then_completeness":
            raise EntityResolutionError(f"Unknown canonical_strategy: {strategy!r}")
        # Most frequent, then most complete (tokens, length), then alphabetical
        # for deterministic output.
        return min(
            counts,
            key=lambda n: (
                -counts[n],
                -len(tokenize(normalize_name(n, strip_honorifics=self.config.strip_honorifics))),
                -len(n),
                n.lower(),
            ),
        )
