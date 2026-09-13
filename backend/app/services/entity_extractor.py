"""
Entity-Aware Signal Extractor for News Intelligence.
Extracts normalized keywords, named entities, organizations, products,
and technology terms from headlines to compute semantic entity overlap.
"""
import re
from typing import Set, Tuple, List

COMMON_SENTENCE_STARTERS = {
    'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from',
    'and', 'or', 'as', 'is', 'are', 'was', 'were', 'new', 'after', 'will', 'there',
    'be', 'how', 'why', 'what', 'when', 'where', 'who', 'this', 'that', 'these',
    'those', 'every', 'everyone', 'it', 'its', 'just', 'some', 'here', 'meet',
    'first', 'look', 'inside', 'dont', 'don', 'doesnt', 'didnt', 'isnt', 'arent',
    'wasnt', 'werent', 'wont', 'cant', 'couldnt', 'shouldnt', 'wouldnt'
}


CALENDAR_TERMS = {
    'september', 'october', 'november', 'december', 'january', 'february',
    'march', 'april', 'may', 'june', 'july', 'august', 'monday', 'tuesday',
    'wednesday', 'thursday', 'friday', 'saturday', 'sunday', 'year', 'month',
    'day', 'week', 'today', 'yesterday', 'tomorrow'
}

GENERIC_SHORT_ENTITIES = {
    'ai', 'us', 'uk', 'eu', 'tech', 'app', 'apps', 'web', 'ceo', 'cto', 'vp',
    'pc', 'pcs', 'os', 'tv', 'tvs'
}


class EntityExtractor:
    """
    Lightweight deterministic named entity and keyword extractor.
    Operates without external heavy models, providing fast, deterministic overlap signals.
    """

    @staticmethod
    def clean_headline(title: str) -> str:
        """
        Strips feed prefixes (APOD, Show HN) and trailing publication badges.
        """
        if not title:
            return ""
        # Strip common feed prefixes
        cleaned = re.sub(
            r'^(?:APOD|Ask HN|Show HN|Tell HN):\s*',
            '',
            title,
            flags=re.IGNORECASE
        )
        # Strip trailing source attributions
        cleaned = re.sub(
            r'\s*[-|–—]\s*(?:BBC News|BBC Technology|The Verge|Ars Technica|NASA|BleepingComputer|Krebs on Security).*$',
            '',
            cleaned,
            flags=re.IGNORECASE
        )
        return cleaned.strip()

    @classmethod
    def extract_entities(cls, title: str, description: str = "") -> Set[str]:
        """
        Extracts named entities, organizations, products, and technical terms from headline.
        """
        clean_title = cls.clean_headline(title)
        if not clean_title:
            return set()

        # Remove punctuation for word token extraction, preserving internal hyphens
        words = re.findall(r'[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*', clean_title)
        entities: Set[str] = set()

        for i, w in enumerate(words):
            w_lower = w.lower()
            # 1. Acronyms & Model numbers: 2+ all-caps or alphanumeric with digits (AI, NASA, GPT-5, M83, LG)
            if w.isupper() and len(w) >= 2:
                entities.add(w_lower)
            elif any(c.isdigit() for c in w) and any(c.isalpha() for c in w):
                entities.add(w_lower)
            # 2. Capitalized proper nouns
            elif w[0].isupper():
                if i == 0 and w_lower in COMMON_SENTENCE_STARTERS:
                    continue
                if len(w) >= 3 and w_lower not in COMMON_SENTENCE_STARTERS:
                    entities.add(w_lower)

        # 3. Capitalized multi-word phrases (e.g., Space Academy, Dario Amodei, Artemis Accords)
        phrases = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', clean_title)
        for p in phrases:
            p_lower = p.lower()
            entities.add(p_lower)
            for part in p_lower.split():
                if part not in COMMON_SENTENCE_STARTERS and len(part) >= 3:
                    entities.add(part)

        # Clean calendar names and pure numbers
        entities = {e for e in entities if e not in CALENDAR_TERMS and not e.isdigit()}
        return entities

    @classmethod
    def compute_overlap(
        cls,
        entities_a: Set[str],
        entities_b: Set[str],
        title_similarity: float = 0.0
    ) -> Tuple[float, Set[str]]:
        """
        Computes precision-gated entity overlap score between two sets of entities.
        Prevents false-positive clusters from sharing a single generic company or platform tag.
        """
        if not entities_a or not entities_b:
            return 0.0, set()

        common = entities_a & entities_b
        if not common:
            return 0.0, set()

        non_generic = common - GENERIC_SHORT_ENTITIES
        min_size = min(len(entities_a), len(entities_b))

        # Case 1: Multiple non-generic entities match (strong evidence of same event)
        if len(non_generic) >= 2:
            score = min(1.0, (len(non_generic) / max(min_size, 1)) * 1.1)
            return score, common

        # Case 2: One non-generic entity matches + title lexical similarity supports it
        if len(non_generic) == 1:
            if title_similarity >= 0.18:
                score = min(0.65, 0.45 * (1.0 / max(min_size, 1)) + 0.20)
                return score, common
            else:
                # Single entity without headline lexical support (e.g. two unrelated "OpenAI" stories)
                return 0.0, common

        # Case 3: Only generic tags match (e.g., just 'ai' or 'tv')
        if title_similarity >= 0.25:
            return 0.15, common

        return 0.0, common


entity_extractor = EntityExtractor()
