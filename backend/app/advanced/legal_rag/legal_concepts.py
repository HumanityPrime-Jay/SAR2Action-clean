"""Controlled Legal Concept Dictionary & Query Normalizer (P2).

Maps Taiwanese farmer colloquial expressions and formal statutory terms to
verified M0090019 concepts, articles, and official appendices—with zero AI models.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
ONTOLOGY_PATH = ROOT / "data" / "legal" / "agricultural_disaster_relief" / "legal_ontology.json"


@dataclass
class ConceptMatch:
    concept_id: str
    label_zh: str
    matched_triggers: list[str]
    linked_articles: list[str]
    linked_appendices: list[str]
    formal_synonyms: list[str]
    score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_taiwan_legal_query(query: str) -> str:
    """Normalize Traditional Chinese variants & colloquial numerals deterministically."""
    q = query.strip()
    q = (
        q.replace("臺", "台")
        .replace("％", "%")
        .replace("颱瘋", "颱風")
        .replace("補註", "補助")
        .replace("蕃茄", "番茄")
    )
    q = re.sub(r"\s+", " ", q)
    return q


class LegalConceptDictionary:
    """Deterministic concept matcher & synonym expander backed by legal_ontology.json."""

    def __init__(self, ontology_path: Path | None = None):
        self.ontology_path = ontology_path or ONTOLOGY_PATH
        raw = json.loads(self.ontology_path.read_text(encoding="utf-8"))
        self.ontology_id: str = raw.get("ontology_id", "M0090019-LEGAL-CONCEPTS")
        self.concepts: list[dict[str, Any]] = raw.get("concepts", [])

    def match_concepts(self, normalized_query: str) -> list[ConceptMatch]:
        matches: list[ConceptMatch] = []
        for c in self.concepts:
            triggers = [t for t in c.get("colloquial_triggers", []) if t in normalized_query]
            synonyms = [s for s in c.get("formal_synonyms", []) if s in normalized_query]
            hit_terms = list(dict.fromkeys(triggers + synonyms))
            if not hit_terms:
                continue
            # Weight longer/more specific triggers slightly higher
            score = sum(1.0 + min(len(t), 8) * 0.15 for t in hit_terms)
            matches.append(
                ConceptMatch(
                    concept_id=c["concept_id"],
                    label_zh=c["label_zh"],
                    matched_triggers=hit_terms,
                    linked_articles=list(c.get("linked_articles", [])),
                    linked_appendices=list(c.get("linked_appendices", [])),
                    formal_synonyms=list(c.get("formal_synonyms", [])),
                    score=round(score, 4),
                )
            )
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches

    def expand_synonyms(self, concept_matches: list[ConceptMatch], max_terms: int = 12) -> list[str]:
        terms: list[str] = []
        for m in concept_matches:
            for syn in m.formal_synonyms:
                if syn not in terms:
                    terms.append(syn)
                if len(terms) >= max_terms:
                    return terms
        return terms
