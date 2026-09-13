"""
Global Importance Engine (Phase 5).
Deterministically scores news stories from 0 to 100 based on observable signals
from story reporting, severity, reach, multi-dimensional impact, urgency, novelty,
escalation, and reporting breadth.

Key Principles:
1. Global Importance != Personal Relevance (strictly independent).
2. The score is NOT an LLM-hallucinated integer. An explicit deterministic formula
   combines validated signals using configuration weights.
3. Source count does NOT dominate importance (bounded at 5% weight).
4. Urgency and importance remain strictly decoupled.
5. All scores are explainable with clear factor breakdowns.
"""
import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from backend.app.core.config import settings
from backend.app.core.db_repository import db_repository
from backend.app.schemas.story import ImportanceSignals, ImportanceBreakdown

logger = logging.getLogger("pulse.services.importance")


def _has_keyword(text: str, keywords: List[str]) -> bool:
    """Matches keywords using regex word boundaries or exact multi-word matching."""
    for kw in keywords:
        if " " in kw or "-" in kw:
            if kw in text:
                return True
        else:
            if re.search(r'\b' + re.escape(kw) + r'\b', text):
                return True
    return False


class ImportanceService:
    """
    Deterministic Global Importance Engine.
    """

    def __init__(self):
        self.weights = settings.IMPORTANCE_WEIGHTS
        self.tiers = settings.IMPORTANCE_TIERS
        self.reach_weights = settings.REACH_LEVEL_WEIGHTS
        self.novelty_weights = settings.NOVELTY_LEVEL_WEIGHTS
        self.version = getattr(settings, "IMPORTANCE_VERSION", "v1")

    def extract_signals(self, story: Dict[str, Any]) -> ImportanceSignals:
        """
        Extracts structured signals from a story cluster and its constituent content.
        Uses deterministic, observable evidence from the story title, summary,
        claims, entities, category, and source coverage.
        """
        title = (story.get("ai_title") or story.get("title") or "").lower()
        summary = (story.get("ai_summary") or story.get("summary") or "").lower()
        why_it_matters = (story.get("why_it_matters") or "").lower()
        category = (story.get("ai_category") or story.get("category") or "technology").lower()
        
        # Combine text for holistic pattern recognition
        full_text = f"{title} {summary} {why_it_matters}"
        
        raw_claims = story.get("claims") or []
        claims_text = " ".join(
            (c.get("text", "") if isinstance(c, dict) else getattr(c, "text", "")).lower()
            for c in raw_claims
        )
        full_text = f"{full_text} {claims_text}"

        source_count = max(1, int(story.get("source_count") or len(story.get("articles") or []) or 1))
        article_count = max(source_count, int(story.get("article_count") or len(story.get("articles") or []) or 1))
        
        raw_entities = story.get("entities") or []
        entity_count = len(raw_entities)

        # ------------------------------------------------------------------
        # 1. Scope & Reach Extraction
        # ------------------------------------------------------------------
        scope = "regional"
        if _has_keyword(full_text, [
            "global", "worldwide", "international", "planet", "across nations",
            "united nations", "all countries", "earth", "worldwide outage"
        ]):
            scope = "global"
        elif _has_keyword(full_text, [
            "neighboring territory", "neighboring countries", "across borders",
            "cross-border", "foreign", "multinational", "allies", "overseas"
        ]):
            scope = "international"
        elif _has_keyword(full_text, [
            "national", "federal", "nationwide", "congress", "white house",
            "pentagon", "parliament", "supreme court", "across the country",
            "united states", "china", "european union", "eu regulators"
        ]):
            scope = "national"
        elif _has_keyword(full_text, [
            "local", "city council", "metro", "subway", "neighborhood",
            "county", "municipal", "water main", "road closure", "traffic delay"
        ]):
            scope = "local"
        else:
            # Domain-based scope defaults
            if category in ("space", "science") or _has_keyword(full_text, ["exoplanet", "astronomy", "telescope", "astrophysics", "mars", "moon"]):
                scope = "global"
            elif category in ("cybersecurity", "ai", "world"):
                scope = "international"
            else:
                scope = "regional"

        # ------------------------------------------------------------------
        # 2. Multi-dimensional Impact Signals (0.0 to 1.0)
        # ------------------------------------------------------------------
        geopolitical_impact: Optional[float] = None
        public_safety_impact: Optional[float] = None
        security_impact: Optional[float] = None
        economic_impact: Optional[float] = None
        technological_impact: Optional[float] = None
        scientific_impact: Optional[float] = None
        environmental_impact: Optional[float] = None
        public_health_impact: Optional[float] = None
        industry_impact: Optional[float] = None
        cultural_impact: Optional[float] = None

        # Geopolitical
        if _has_keyword(full_text, [
            "war", "military", "sanctions", "geopolitical", "missile", "invasion",
            "nato", "diplomatic", "troops", "conflict", "treaty", "sovereignty",
            "territorial", "defense ministry", "weapons"
        ]):
            geopolitical_impact = 0.90
            public_safety_impact = 0.85
            if any(w in full_text for w in ["escalat", "strikes", "expand"]):
                geopolitical_impact = 0.98

        # Security & Cyberattack
        if _has_keyword(full_text, [
            "cyberattack", "zero-day", "ransomware", "breach", "vulnerability",
            "cve", "exploit", "malware", "hacked", "backdoor", "ddos",
            "espionage", "threat actor", "critical infrastructure", "cisa"
        ]):
            security_impact = 0.92
            technological_impact = 0.80
            economic_impact = 0.65
            if _has_keyword(full_text, ["zero-day", "critical infrastructure", "actively exploited"]):
                security_impact = 0.98
                public_safety_impact = max(public_safety_impact or 0.0, 0.70)

        # Technology & AI Releases
        if _has_keyword(full_text, [
            "breakthrough", "frontier model", "benchmark", "next-generation",
            "announces new model", "llm", "ai model", "unveils", "supercomputer",
            "quantum", "gpu architecture", "semiconductor", "foundry", "chip"
        ]):
            technological_impact = max(technological_impact or 0.0, 0.85)
            industry_impact = max(industry_impact or 0.0, 0.75)
            economic_impact = max(economic_impact or 0.0, 0.60)

        # Science & Discoveries
        if _has_keyword(full_text, [
            "discovery", "exoplanet", "telescope", "james webb", "particle physics",
            "fusion", "crispr", "dna", "cure", "species discovered", "astrophysics",
            "superconductor", "space mission", "mars rover", "nasa", "esa"
        ]):
            scientific_impact = 0.95
            technological_impact = max(technological_impact or 0.0, 0.60)

        # Economic & Markets
        if _has_keyword(full_text, [
            "interest rate", "federal reserve", "central bank", "recession",
            "inflation", "gdp", "antitrust", "tariff", "trade war", "market crash",
            "banking collapse", "treasury", "sec lawsuit"
        ]):
            economic_impact = max(economic_impact or 0.0, 0.88)
            industry_impact = max(industry_impact or 0.0, 0.80)

        # Public Health & Environment
        if _has_keyword(full_text, ["pandemic", "outbreak", "virus", "who", "cdc", "vaccine", "toxic"]):
            public_health_impact = 0.90
            public_safety_impact = max(public_safety_impact or 0.0, 0.85)
        if _has_keyword(full_text, ["climate", "hurricane", "wildfire", "earthquake", "emission", "spill"]):
            environmental_impact = 0.85
            public_safety_impact = max(public_safety_impact or 0.0, 0.75)

        # Minor software update check
        if _has_keyword(full_text, [
            "minor update", "patch notes", "bug fixes", "version bump", "dot release",
            "maintenance release", "ui tweak", "changelog"
        ]):
            technological_impact = 0.25
            industry_impact = 0.20

        # Celebrity / Entertainment gossip check
        if _has_keyword(full_text, [
            "actor", "actress", "celebrity", "red carpet", "oscar", "dating",
            "divorce", "gossip", "paparazzi", "hollywood", "reality star",
            "influencer drama", "box office weekend"
        ]):
            cultural_impact = 0.35

        # Local service disruption check
        if _has_keyword(full_text, [
            "water main", "traffic detour", "subway delay", "metro station",
            "local power outage", "road work", "pothole"
        ]):
            public_safety_impact = max(public_safety_impact or 0.0, 0.30)
            industry_impact = max(industry_impact or 0.0, 0.20)

        # ------------------------------------------------------------------
        # 3. Severity Score (0.0 to 1.0)
        # ------------------------------------------------------------------
        # Default severity based on category
        severity = 0.50
        if geopolitical_impact and geopolitical_impact >= 0.90:
            severity = 0.95
        elif security_impact and security_impact >= 0.90:
            severity = 0.90
        elif public_health_impact and public_health_impact >= 0.85:
            severity = 0.88
        elif scientific_impact and scientific_impact >= 0.90:
            severity = 0.75
        elif technological_impact and technological_impact >= 0.80:
            severity = 0.70
        elif economic_impact and economic_impact >= 0.80:
            severity = 0.75
        elif cultural_impact and not (security_impact or geopolitical_impact or technological_impact):
            severity = 0.18
        elif _has_keyword(full_text, ["minor update", "bug fix", "patch notes", "bug fixes", "changelog"]):
            severity = 0.20
        elif scope == "local" and not (geopolitical_impact or security_impact):
            severity = 0.25
        elif category in ("cybersecurity", "ai"):
            severity = 0.65
        elif category in ("technology", "science", "space"):
            severity = 0.55

        # ------------------------------------------------------------------
        # 4. Urgency Score (0.0 to 1.0)
        # Urgency is separate from importance!
        # Breaking events, active exploits, immediate outages = high urgency.
        # Historic discoveries, papers, static announcements = lower urgency.
        # ------------------------------------------------------------------
        urgency = 0.40
        if _has_keyword(full_text, [
            "active conflict", "under attack", "actively exploited", "ongoing outage",
            "immediate risk", "emergency", "breaking", "underway", "spreading rapidly"
        ]):
            urgency = 0.95
        elif _has_keyword(full_text, ["zero-day", "cve", "breach", "missile", "strikes", "water main"]):
            urgency = 0.80
        elif _has_keyword(full_text, ["announces", "unveils", "released today", "launched"]):
            urgency = 0.60
        elif scientific_impact and scientific_impact >= 0.80:
            # Historic scientific discovery: high importance, but low real-time urgency
            urgency = 0.25
        elif _has_keyword(full_text, ["paper", "retrospective", "analysis reveals", "history of", "in review"]):
            urgency = 0.20
        elif cultural_impact and not security_impact:
            urgency = 0.25

        # ------------------------------------------------------------------
        # 5. Novelty Score (0.0 to 1.0)
        # ------------------------------------------------------------------
        novelty = 0.70
        if _has_keyword(full_text, ["first ever", "newly discovered", "unprecedented", "breakthrough", "world first"]):
            novelty = 1.00
        elif _has_keyword(full_text, ["unveils", "announces", "releases", "launches", "reported today", "discovery", "discovered"]):
            novelty = 0.85
        elif _has_keyword(full_text, ["develops", "expands", "advances", "escalates"]):
            novelty = 0.70
        elif _has_keyword(full_text, ["follow-up", "update", "part 2", "continues"]):
            novelty = 0.50
        elif _has_keyword(full_text, ["minor update", "patch", "revision", "fix", "bug fixes"]):
            novelty = 0.30
        elif _has_keyword(full_text, ["repeated", "reminder", "reiterates"]):
            novelty = 0.15

        # ------------------------------------------------------------------
        # 6. Escalation Score (0.0 to 1.0)
        # Captures whether an existing event is becoming materially more serious.
        # ------------------------------------------------------------------
        escalation = 0.10
        if any(w in full_text for w in [
            "escalat", "spreads to", "widens", "intensif", "affects additional",
            "more victims", "confirmed finding", "moves from allegation to", "death toll rises"
        ]):
            escalation = 0.80
        elif any(w in full_text for w in ["expanding", "broader impact", "spread"]):
            escalation = 0.50

        return ImportanceSignals(
            source_count=source_count,
            article_count=article_count,
            category=category,
            entity_count=entity_count,
            geographic_scope=scope,
            severity=round(max(0.0, min(1.0, severity)), 3),
            affected_population="broad" if scope in ("global", "international") else "focused",
            political_impact=round(geopolitical_impact, 3) if geopolitical_impact is not None else None,
            public_safety_impact=round(public_safety_impact, 3) if public_safety_impact is not None else None,
            security_impact=round(security_impact, 3) if security_impact is not None else None,
            economic_impact=round(economic_impact, 3) if economic_impact is not None else None,
            technological_impact=round(technological_impact, 3) if technological_impact is not None else None,
            scientific_impact=round(scientific_impact, 3) if scientific_impact is not None else None,
            environmental_impact=round(environmental_impact, 3) if environmental_impact is not None else None,
            public_health_impact=round(public_health_impact, 3) if public_health_impact is not None else None,
            industry_impact=round(industry_impact, 3) if industry_impact is not None else None,
            cultural_impact=round(cultural_impact, 3) if cultural_impact is not None else None,
            urgency=round(max(0.0, min(1.0, urgency)), 3),
            novelty=round(max(0.0, min(1.0, novelty)), 3),
            escalation=round(max(0.0, min(1.0, escalation)), 3),
            official_confirmation=True
        )

    def calculate_impact_score(self, signals: ImportanceSignals) -> Tuple[float, str]:
        """
        Combines supported impact dimensions without double counting.
        Takes the primary (maximum) dimension score M, plus a diminishing
        contribution from other active dimensions:
            impact = min(1.0, M + 0.15 * sum(other_dims))
        Returns (impact_score, primary_dimension_name).
        """
        dimension_map = {
            "geopolitical": signals.political_impact,
            "public safety": signals.public_safety_impact,
            "security": signals.security_impact,
            "economic": signals.economic_impact,
            "technology": signals.technological_impact,
            "scientific": signals.scientific_impact,
            "environmental": signals.environmental_impact,
            "public health": signals.public_health_impact,
            "industry": signals.industry_impact,
            "cultural": signals.cultural_impact
        }

        active = {k: v for k, v in dimension_map.items() if v is not None and v > 0.0}

        if not active:
            cat = signals.category.lower()
            category_defaults = {
                "cybersecurity": (0.75, "security"),
                "ai": (0.70, "technology"),
                "technology": (0.60, "technology"),
                "science": (0.65, "scientific"),
                "space": (0.65, "scientific"),
                "world": (0.60, "geopolitical"),
                "business": (0.55, "economic")
            }
            default_val, default_name = category_defaults.get(cat, (0.45, "industry"))
            return default_val, default_name

        primary_dim = max(active, key=active.get)
        max_val = active[primary_dim]
        other_vals = [v for k, v in active.items() if k != primary_dim]

        # Non-linear consolidation prevents inflating score by simply tagging multiple dimensions
        secondary_contribution = sum(other_vals) * 0.15
        impact_score = min(1.0, max_val + secondary_contribution)
        return round(impact_score, 3), primary_dim

    def calculate_reach_score(self, signals: ImportanceSignals) -> float:
        """
        Calculates normalized reach score based on geographic scope.
        """
        scope = (signals.geographic_scope or "regional").lower()
        return self.reach_weights.get(scope, 0.40)

    def calculate_reporting_breadth(self, source_count: int, article_count: int) -> float:
        """
        Calculates normalized reporting breadth score.
        Source count represents reporting breadth, NOT automatic importance.
        Scaled sublinearly so breadth never overpowers intrinsic significance.
        """
        sc = max(1, source_count)
        if sc == 1:
            return 0.20
        elif sc == 2:
            return 0.45
        elif sc == 3:
            return 0.70
        elif sc == 4:
            return 0.85
        else:
            return 1.00

    def generate_explanation(
        self,
        tier: str,
        score: int,
        signals: ImportanceSignals,
        primary_dim: str,
        reach_score: float,
        severity_score: float,
        urgency_score: float
    ) -> str:
        """
        Generates an evidence-grounded, explainable rationale for the score.
        Avoids generic 'reported by many sources' claims.
        """
        scope_str = signals.geographic_scope.lower()
        dim_str = primary_dim.lower()

        if tier == "CRITICAL":
            if signals.security_impact and signals.security_impact >= 0.85:
                return (
                    f"Critical global importance ({score}/100) due to severe cybersecurity impact with {scope_str} reach "
                    f"and elevated urgency affecting critical digital systems."
                )
            elif (signals.political_impact or 0) >= 0.85:
                return (
                    f"Critical global importance ({score}/100) involving a major geopolitical development with {scope_str} scope "
                    f"and profound public safety implications."
                )
            else:
                return (
                    f"Critical global importance ({score}/100) driven by exceptionally high severity ({severity_score:.2f}) "
                    f"and {scope_str} reach across the {dim_str} sector."
                )

        elif tier == "HIGH":
            if signals.security_impact and signals.security_impact >= 0.80:
                return (
                    f"High global importance ({score}/100) driven by major cybersecurity significance affecting {scope_str} digital systems."
                )
            elif (signals.political_impact or 0) >= 0.80:
                return (
                    f"High global importance ({score}/100) involving a significant geopolitical development with {scope_str} implications."
                )
            elif signals.scientific_impact and signals.scientific_impact >= 0.80 and urgency_score < 0.40:
                return (
                    f"High global importance ({score}/100) reflecting a landmark scientific and technological breakthrough "
                    f"with global reach, despite low immediate operational urgency."
                )
            elif signals.technological_impact and signals.technological_impact >= 0.75:
                return (
                    f"High global importance ({score}/100) driven by major technological significance with {scope_str} industry impact."
                )
            elif signals.economic_impact and signals.economic_impact >= 0.75:
                return (
                    f"High global importance ({score}/100) representing significant economic and regulatory consequences with {scope_str} reach."
                )
            else:
                return (
                    f"High global importance ({score}/100) reflecting substantial {dim_str} significance affecting {scope_str} audiences."
                )

        elif tier == "MEDIUM":
            if scope_str == "local" and urgency_score >= 0.70:
                return (
                    f"Moderate importance ({score}/100) involving an active local service disruption with immediate local urgency "
                    f"but limited global reach."
                )
            else:
                return (
                    f"Moderate importance ({score}/100) covering notable {dim_str} developments with focused {scope_str} reach."
                )

        else:  # LOW
            if signals.cultural_impact and not (signals.security_impact or signals.technological_impact):
                return (
                    f"Low global importance ({score}/100) as this relates to routine entertainment and cultural reporting "
                    f"with minimal broader structural impact."
                )
            elif severity_score <= 0.30:
                return (
                    f"Low global importance ({score}/100) reflecting routine minor updates and technical maintenance with limited public impact."
                )
            else:
                return (
                    f"Low global importance ({score}/100) representing localized or specialized interest without broad global consequences."
                )

    def calculate_importance(self, signals: ImportanceSignals) -> ImportanceBreakdown:
        """
        Applies the deterministic formula:
            raw_score = (
                severity * w_severity
              + reach * w_reach
              + impact * w_impact
              + urgency * w_urgency
              + novelty * w_novelty
              + escalation * w_escalation
              + reporting_breadth * w_reporting_breadth
            ) * 100
        """
        impact_score, primary_dim = self.calculate_impact_score(signals)
        reach_score = self.calculate_reach_score(signals)
        reporting_breadth = self.calculate_reporting_breadth(signals.source_count, signals.article_count)

        severity_score = signals.severity
        urgency_score = signals.urgency
        novelty_score = signals.novelty
        escalation_score = signals.escalation

        w = self.weights
        weighted_sum = (
            severity_score * w.get("severity", 0.25)
            + reach_score * w.get("reach", 0.20)
            + impact_score * w.get("impact", 0.20)
            + urgency_score * w.get("urgency", 0.10)
            + novelty_score * w.get("novelty", 0.10)
            + escalation_score * w.get("escalation", 0.10)
            + reporting_breadth * w.get("reporting_breadth", 0.05)
        )

        final_score = int(round(weighted_sum * 100))
        final_score = max(0, min(100, final_score))

        # Determine Tier
        if final_score >= self.tiers.get("CRITICAL", 85):
            tier = "CRITICAL"
        elif final_score >= self.tiers.get("HIGH", 70):
            tier = "HIGH"
        elif final_score >= self.tiers.get("MEDIUM", 45):
            tier = "MEDIUM"
        else:
            tier = "LOW"

        explanation = self.generate_explanation(
            tier=tier,
            score=final_score,
            signals=signals,
            primary_dim=primary_dim,
            reach_score=reach_score,
            severity_score=severity_score,
            urgency_score=urgency_score
        )

        return ImportanceBreakdown(
            importance_score=final_score,
            importance_tier=tier,
            severity=severity_score,
            reach=reach_score,
            impact=impact_score,
            urgency=urgency_score,
            novelty=novelty_score,
            escalation=escalation_score,
            reporting_breadth=reporting_breadth,
            explanation=explanation,
            importance_version=self.version,
            calculated_at=datetime.utcnow().isoformat()
        )

    def calculate_story_importance(self, story_id: str) -> Optional[ImportanceBreakdown]:
        """
        Calculates and persists importance for a single story by ID.
        """
        story = db_repository.get_story_by_id(story_id)
        if not story:
            return None

        signals = self.extract_signals(story)
        breakdown = self.calculate_importance(signals)
        db_repository.save_story_importance(story_id, breakdown.model_dump())
        return breakdown

    def calculate_batch_importance(self, limit: int = 20) -> Dict[str, Any]:
        """
        Calculates importance across stories, prioritizing unscored stories.
        """
        stories = db_repository.get_unscored_stories(limit=limit)
        if len(stories) < limit:
            additional = db_repository.get_stories(limit=limit - len(stories))
            existing_ids = {s["id"] for s in stories}
            for s in additional:
                if s["id"] not in existing_ids:
                    stories.append(s)

        processed = []
        for s in stories[:limit]:
            signals = self.extract_signals(s)
            breakdown = self.calculate_importance(signals)
            db_repository.save_story_importance(s["id"], breakdown.model_dump())
            processed.append({
                "story_id": s["id"],
                "title": s.get("ai_title") or s.get("title"),
                "importance_score": breakdown.importance_score,
                "importance_tier": breakdown.importance_tier,
                "explanation": breakdown.explanation
            })

        return {
            "processed_count": len(processed),
            "version": self.version,
            "stories": processed
        }


importance_service = ImportanceService()
