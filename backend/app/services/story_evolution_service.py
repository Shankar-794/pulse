"""
Dedicated Story Evolution, Breaking News & Event Lifecycle Service (Phase 7).

Provides:
1. Deterministic Story Lifecycle Engine:
   NEW -> DEVELOPING -> ACTIVE -> STABLE -> RESOLVED
   ACTIVE -> ESCALATING
2. Incremental Story Update Classification:
   NEW_STORY, SAME_REPORTING, MEANINGFUL_UPDATE, ESCALATION, CONTRADICTION, CORRECTION
3. Persistent Grounded Timeline Event Synthesis (story_events table).
4. Deterministic Breaking News Engine (0-100 score and level thresholds).
5. Cross-Source Perspective & Contradiction Detection.
6. Latest Development Grounded Extraction.
"""
import re
import uuid
import json
import logging
from typing import List, Dict, Any, Tuple, Optional, Set
from datetime import datetime, timezone

from backend.app.core.config import settings
from backend.app.core.db_repository import db_repository
from backend.app.services.entity_extractor import entity_extractor

logger = logging.getLogger("pulse.services.evolution")

MILESTONE_KEYWORDS = {
    "confirms", "confirmed", "identifies", "identified", "releases", "released",
    "patches", "patched", "arrests", "arrested", "charges", "charged",
    "approves", "approved", "announces", "announced", "deploys", "deployed",
    "signs", "signed", "files", "filed", "sues", "sued", "unveils", "unveiled"
}


class StoryEvolutionService:
    def __init__(self, db_repo: Optional[Any] = None):
        self.db = db_repo or db_repository
        self.version = getattr(settings, "EVOLUTION_VERSION", "v1")
        self.breaking_weights = getattr(settings, "BREAKING_NEWS_WEIGHTS", {
            "recency": 0.25,
            "urgency": 0.20,
            "severity": 0.20,
            "velocity": 0.15,
            "escalation": 0.10,
            "source_diversity": 0.05,
            "novelty": 0.05
        })
        self.breaking_thresholds = getattr(settings, "BREAKING_LEVEL_THRESHOLDS", {
            "BREAKING": 75,
            "DEVELOPING": 55,
            "UPDATED": 35,
            "STABLE": 0
        })
        self.escalation_keywords = getattr(settings, "ESCALATION_KEYWORDS", [
            "death toll", "emergency declared", "critical severity", "spreads",
            "exploited in the wild", "ransom demanded", "nationwide outage",
            "flights grounded", "evacuation", "fatal", "casualties", "breach expands"
        ])
        self.contradiction_keywords = getattr(settings, "CONTRADICTION_KEYWORDS", [
            "denies", "disputes", "contradicts", "refutes", "refuses to acknowledge",
            "claims otherwise", "conflicting reports", "denied allegation", "disputed claims"
        ])
        self.correction_keywords = getattr(settings, "CORRECTION_KEYWORDS", [
            "correction", "retracts", "clarifies", "walks back", "statement amended",
            "previously reported incorrectly", "retraction", "erratum"
        ])
        self.resolution_keywords = getattr(settings, "RESOLUTION_KEYWORDS", [
            "resolved", "patch released", "service restored", "containment achieved",
            "all clear", "settlement reached", "verdict reached", "fix deployed", "mitigated"
        ])

    def _parse_iso(self, date_str: Optional[str]) -> datetime:
        """Safe ISO timestamp parser defaulting to UTC now."""
        if not date_str:
            return datetime.now(timezone.utc)
        try:
            cleaned = date_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return datetime.now(timezone.utc)

    # =========================================================================
    # 1. Update Detection & Classification
    # =========================================================================
    def classify_article_update(
        self,
        article: Dict[str, Any],
        story: Dict[str, Any],
        cluster_articles: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Classifies an article against an existing canonical story.
        Returns:
            {
                "classification": "SAME_REPORTING" | "MEANINGFUL_UPDATE" | "ESCALATION" | "CONTRADICTION" | "CORRECTION" | "NEW_STORY",
                "reason": str,
                "is_meaningful": bool,
                "confidence": float
            }
        """
        from backend.app.services.clustering_service import clustering_service

        cluster_articles = cluster_articles or []
        art_title = article.get("title") or ""
        art_desc = article.get("description") or ""
        art_text = f"{art_title} {art_desc}".lower()

        story_title = story.get("title") or ""
        story_summary = story.get("summary") or ""
        story_text = f"{story_title} {story_summary}".lower()

        # Check category alignment first
        if not clustering_service.is_candidate_pair(article.get("category", ""), story.get("category", "")):
            return {
                "classification": "NEW_STORY",
                "reason": "Different topic category, no semantic relationship.",
                "is_meaningful": False,
                "confidence": 0.95
            }

        # Check lexical and entity similarity
        clean_art = entity_extractor.clean_headline(art_title)
        clean_story = entity_extractor.clean_headline(story_title)
        title_sim = float(clustering_service.similarity_provider.compute_pairwise(clean_art, clean_story))

        rep_art = clustering_service.build_article_representation(article)
        rep_story = clustering_service.build_article_representation({
            "title": story_title,
            "description": story_summary,
            "primary_topic": story.get("primary_topic") or story.get("category", "")
        })
        full_sim = float(clustering_service.similarity_provider.compute_pairwise(rep_art, rep_story))

        ents_art = entity_extractor.extract_entities(art_title, art_desc)
        ents_story = entity_extractor.extract_entities(story_title, story_summary)
        hybrid_sim, _, ent_score, common_ents = clustering_service.compute_pair_similarity(
            article, story, title_sim, full_sim, ents_art, ents_story
        )

        # Check against story and any cluster articles if provided
        max_hybrid = hybrid_sim
        best_common = common_ents
        best_ent_score = ent_score

        for cluster_art in cluster_articles:
            ca_title = cluster_art.get("title") or ""
            ca_desc = cluster_art.get("description") or ""
            ca_clean = entity_extractor.clean_headline(ca_title)
            ca_t_sim = float(clustering_service.similarity_provider.compute_pairwise(clean_art, ca_clean))
            ca_rep = clustering_service.build_article_representation(cluster_art)
            ca_f_sim = float(clustering_service.similarity_provider.compute_pairwise(rep_art, ca_rep))
            ca_ents = entity_extractor.extract_entities(ca_title, ca_desc)
            ca_hyb, _, ca_ent_sc, ca_comm = clustering_service.compute_pair_similarity(
                article, cluster_art, ca_t_sim, ca_f_sim, ents_art, ca_ents
            )
            if ca_hyb > max_hybrid:
                max_hybrid = ca_hyb
                best_common = ca_comm
                best_ent_score = ca_ent_sc

        REPORTING_NOISE = {
            "reported", "reports", "reporting", "says", "said", "according",
            "stated", "details", "article", "new", "latest", "vulnerability",
            "day", "breaking", "update", "coverage", "earlier", "advisory"
        }
        story_tokens = set(re.findall(r"\b[a-z0-9]{3,}\b", story_text.replace("-", " "))) - REPORTING_NOISE
        art_tokens = set(re.findall(r"\b[a-z0-9]{3,}\b", art_text.replace("-", " "))) - REPORTING_NOISE
        common_tokens = story_tokens & art_tokens

        is_story_match = (
            max_hybrid >= 0.22 or
            (title_sim >= 0.20 and len(best_common) >= 1) or
            (len(best_common) >= 2 or best_ent_score >= 0.25) or
            len(common_tokens) >= 3
        )

        # Threshold check for story membership
        if not is_story_match:
            return {
                "classification": "NEW_STORY",
                "reason": f"Hybrid similarity ({max_hybrid:.2f}) below threshold and insufficient shared entities.",
                "is_meaningful": False,
                "confidence": 0.90
            }

        # Check for Correction signal
        if any(kw in art_text for kw in self.correction_keywords):
            return {
                "classification": "CORRECTION",
                "reason": "Article contains explicit clarification or correction language.",
                "is_meaningful": True,
                "confidence": 0.92
            }

        # Check for Contradiction signal
        if any(kw in art_text for kw in self.contradiction_keywords):
            return {
                "classification": "CONTRADICTION",
                "reason": "Article reports dispute, refutation, or contradictory claims.",
                "is_meaningful": True,
                "confidence": 0.88
            }

        # Check for Escalation signal
        if any(kw in art_text for kw in self.escalation_keywords):
            return {
                "classification": "ESCALATION",
                "reason": "Article reports escalating impacts, spread, casualties, or emergency declaration.",
                "is_meaningful": True,
                "confidence": 0.90
            }

        # Check for Meaningful Update vs Duplicate Reporting
        REPORTING_NOISE = {
            "reported", "reports", "reporting", "says", "said", "according",
            "stated", "details", "article", "new", "latest", "vulnerability",
            "day", "breaking", "update", "coverage"
        }
        story_tokens = set(re.findall(r"\b[a-z0-9]{3,}\b", story_text.replace("-", " ")))
        
        # Substantive new entities: extracted entities whose core tokens aren't already in story text
        substantive_new_ents = set()
        for ent in (ents_art - ents_story):
            ent_tokens = set(re.findall(r"\b[a-z0-9]{3,}\b", ent.lower().replace("-", " "))) - REPORTING_NOISE
            if ent_tokens - story_tokens:
                substantive_new_ents.add(ent)

        has_new_substantive_entity = len(substantive_new_ents) >= 1
        has_milestone_action = any(re.search(r"\b" + re.escape(kw) + r"\b", art_text) for kw in MILESTONE_KEYWORDS)

        # Text expansion: does the new article add notable novel phrases not in existing cluster?
        art_tokens = set(re.findall(r"\b[a-z0-9]{3,}\b", art_text.replace("-", " "))) - REPORTING_NOISE
        new_tokens = art_tokens - story_tokens
        novel_content_ratio = len(new_tokens) / max(len(art_tokens), 1)

        if has_new_substantive_entity or (has_milestone_action and novel_content_ratio > 0.15) or novel_content_ratio > 0.35:
            return {
                "classification": "MEANINGFUL_UPDATE",
                "reason": (
                    f"Introduces new entities ({', '.join(sorted(substantive_new_ents)[:2])}) "
                    f"or substantive milestone progression."
                    if substantive_new_ents else "Introduces concrete milestone action and new facts."
                ),
                "is_meaningful": True,
                "confidence": 0.85
            }

        # Default to additional reporting / same story coverage
        return {
            "classification": "SAME_REPORTING",
            "reason": "Corroborating reporting covering already-reported facts and entities.",
            "is_meaningful": False,
            "confidence": 0.88
        }

    # =========================================================================
    # 2. Breaking News Engine
    # =========================================================================
    def compute_breaking_score(
        self,
        story: Dict[str, Any],
        articles: List[Dict[str, Any]]
    ) -> Tuple[int, str, Dict[str, float]]:
        """
        Calculates a deterministic Breaking News score (0-100) and level.
        Signals:
        - recency: age of latest article / update
        - urgency: immediacy and active timeliness
        - severity: impact and consequence scale
        - reporting_velocity: volume of coverage in recent hours
        - escalation: intensifiers and widening scope
        - source_diversity: verification breadth
        - novelty: newness vs settled topic

        Guarantees:
        - A routine release 5 mins ago does NOT become BREAKING.
        - High-severity rapidly developing crises CAN become BREAKING even with few articles.
        - Completely independent from Global Importance.
        """
        now = datetime.now(timezone.utc)
        pub_dates = []
        for a in articles:
            dt = self._parse_iso(a.get("published_at") or a.get("created_at"))
            pub_dates.append(dt)

        if pub_dates:
            newest_pub = max(pub_dates)
            oldest_pub = min(pub_dates)
        else:
            newest_pub = self._parse_iso(story.get("last_published_at") or story.get("created_at"))
            oldest_pub = newest_pub

        hours_since_latest = max(0.0, (now - newest_pub).total_seconds() / 3600.0)

        # 1. Recency Signal (0.0 to 1.0)
        if hours_since_latest <= 1.0:
            recency = 1.0
        elif hours_since_latest <= 3.0:
            recency = 0.85
        elif hours_since_latest <= 6.0:
            recency = 0.65
        elif hours_since_latest <= 12.0:
            recency = 0.40
        elif hours_since_latest <= 24.0:
            recency = 0.20
        elif hours_since_latest <= 48.0:
            recency = 0.10
        else:
            recency = 0.02

        # 2. Urgency Signal (0.0 to 1.0)
        urgency = float(story.get("urgency_score") if story.get("urgency_score") is not None else 0.40)

        # 3. Severity Signal (0.0 to 1.0)
        severity = float(story.get("severity_score") if story.get("severity_score") is not None else (story.get("importance_score", 50) / 100.0))

        # 4. Reporting Velocity Signal (0.0 to 1.0)
        recent_article_count = sum(1 for dt in pub_dates if (now - dt).total_seconds() / 3600.0 <= 12.0)
        if recent_article_count >= 5:
            velocity = 1.0
        elif recent_article_count >= 3:
            velocity = 0.80
        elif recent_article_count >= 2:
            velocity = 0.60
        elif recent_article_count == 1:
            velocity = 0.35
        else:
            velocity = 0.10

        # 5. Escalation Signal (0.0 to 1.0)
        escalation = float(story.get("escalation_score") if story.get("escalation_score") is not None else 0.10)
        story_text = f"{story.get('title', '')} {story.get('summary', '')}".lower()
        if any(kw in story_text for kw in self.escalation_keywords):
            escalation = max(escalation, 0.80)

        # 6. Source Diversity Signal (0.0 to 1.0)
        unique_sources = set(a.get("source_name") for a in articles if a.get("source_name"))
        src_count = max(len(unique_sources), story.get("source_count", 1))
        if src_count >= 3:
            source_diversity = 1.0
        elif src_count == 2:
            source_diversity = 0.70
        else:
            source_diversity = 0.40

        # 7. Novelty Signal (0.0 to 1.0)
        novelty = float(story.get("novelty_score") if story.get("novelty_score") is not None else 0.80)

        # Weighted raw composite
        w = self.breaking_weights
        raw_composite = (
            w.get("recency", 0.25) * recency +
            w.get("urgency", 0.20) * urgency +
            w.get("severity", 0.20) * severity +
            w.get("velocity", 0.15) * velocity +
            w.get("escalation", 0.10) * escalation +
            w.get("source_diversity", 0.05) * source_diversity +
            w.get("novelty", 0.05) * novelty
        )

        score = int(round(raw_composite * 100))

        # Critical Guardrail: Routine non-urgent release published recently cannot be BREAKING
        # If severity < 0.40 and urgency < 0.45, clamp breaking_score to <= 50 (DEVELOPING or UPDATED max)
        if severity < 0.40 and urgency < 0.45 and escalation < 0.40:
            score = min(score, 45)

        # Recency Guardrail: Stale stories (> 24h) cannot be BREAKING
        if hours_since_latest > 24.0:
            score = min(score, 40)

        score = min(100, max(0, score))

        # Assign breaking level
        if score >= self.breaking_thresholds["BREAKING"]:
            level = "BREAKING"
        elif score >= self.breaking_thresholds["DEVELOPING"]:
            level = "DEVELOPING"
        elif score >= self.breaking_thresholds["UPDATED"]:
            level = "UPDATED"
        else:
            level = "STABLE"

        signals = {
            "recency": round(recency, 3),
            "urgency": round(urgency, 3),
            "severity": round(severity, 3),
            "velocity": round(velocity, 3),
            "escalation": round(escalation, 3),
            "source_diversity": round(source_diversity, 3),
            "novelty": round(novelty, 3),
            "hours_since_latest": round(hours_since_latest, 1)
        }

        return score, level, signals

    # =========================================================================
    # 3. Deterministic Story Lifecycle Model
    # =========================================================================
    def determine_lifecycle_state(
        self,
        story: Dict[str, Any],
        articles: List[Dict[str, Any]],
        timeline_events: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Determines the deterministic lifecycle state of a story:
        NEW -> DEVELOPING -> ACTIVE -> STABLE -> RESOLVED
        ACTIVE -> ESCALATING
        """
        now = datetime.now(timezone.utc)
        timeline_events = timeline_events or []
        story_text = f"{story.get('title', '')} {story.get('summary', '')}".lower()

        # 1. Check for explicit RESOLVED state
        has_resolution_kw = any(kw in story_text for kw in self.resolution_keywords)
        has_resolution_event = any(ev.get("event_type") == "RESOLUTION" for ev in timeline_events)
        if has_resolution_kw or has_resolution_event:
            return "RESOLVED"

        pub_dates = [self._parse_iso(a.get("published_at") or a.get("created_at")) for a in articles]
        if pub_dates:
            newest_pub = max(pub_dates)
            oldest_pub = min(pub_dates)
        else:
            newest_pub = self._parse_iso(story.get("last_published_at"))
            oldest_pub = newest_pub

        hours_since_latest = max(0.0, (now - newest_pub).total_seconds() / 3600.0)
        story_age_hours = max(0.0, (now - oldest_pub).total_seconds() / 3600.0)
        article_count = len(articles) or story.get("article_count", 1)

        # 2. Check for ESCALATING state
        # Active/developing story where escalation signals are prominent
        has_escalation_kw = any(kw in story_text for kw in self.escalation_keywords)
        has_escalation_event = any(ev.get("event_type") == "ESCALATION" for ev in timeline_events)
        escalation_score = float(story.get("escalation_score") or 0.0)
        if (has_escalation_kw or has_escalation_event or escalation_score >= 0.70) and hours_since_latest <= 24.0:
            return "ESCALATING"

        # 3. Check for STABLE state
        # No updates for > 36 hours and age > 48 hours
        if hours_since_latest > 36.0 and story_age_hours > 48.0:
            return "STABLE"

        # 4. Check for DEVELOPING state
        # Rapid ongoing reporting, multiple recent updates or high urgency
        recent_updates_count = sum(1 for dt in pub_dates if (now - dt).total_seconds() / 3600.0 <= 12.0)
        urgency = float(story.get("urgency_score") or 0.0)
        if (recent_updates_count >= 2 and hours_since_latest <= 12.0) or (urgency >= 0.70 and hours_since_latest <= 6.0):
            return "DEVELOPING"

        # 5. Check for NEW state
        # Brand new story (< 6 hours old, singleton)
        if story_age_hours <= 6.0 and article_count <= 1 and len(timeline_events) <= 1:
            return "NEW"

        # 6. Default healthy state: ACTIVE
        return "ACTIVE"

    # =========================================================================
    # 4. Grounded Timeline Event Synthesis
    # =========================================================================
    def generate_timeline_events(
        self,
        story: Dict[str, Any],
        articles: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Synthesizes chronological timeline events grounded in real articles.
        Guarantees:
        - Every event cites actual article IDs.
        - Initial report is anchored to the earliest article.
        - Updates, escalations, or corrections are created only when supported.
        """
        if not articles:
            return []

        sorted_articles = sorted(
            articles,
            key=lambda a: self._parse_iso(a.get("published_at") or a.get("created_at"))
        )

        events: List[Dict[str, Any]] = []

        # 1. Initial Report Event
        first_art = sorted_articles[0]
        first_id = str(first_art.get("id") or first_art.get("article_id") or "art_1")
        first_source = first_art.get("source_name") or "News Wire"
        first_time = first_art.get("published_at") or first_art.get("created_at") or datetime.utcnow().isoformat()

        events.append({
            "id": f"ev_{story['id'][:10]}_initial",
            "story_id": story["id"],
            "event_type": "INITIAL_REPORT",
            "title": f"Initial report by {first_source}",
            "summary": first_art.get("title") or "Event initially reported.",
            "article_ids": [first_id],
            "occurred_at": first_time,
            "significance": 0.60,
            "event_version": "v1"
        })

        if len(sorted_articles) == 1:
            return events

        # 2. Process subsequent articles to identify grounded update events
        seen_entities: Set[str] = entity_extractor.extract_entities(
            first_art.get("title") or "", first_art.get("description") or ""
        )

        for idx, art in enumerate(sorted_articles[1:], start=2):
            art_id = str(art.get("id") or art.get("article_id") or f"art_{idx}")
            art_source = art.get("source_name") or "Reporting Outlet"
            art_time = art.get("published_at") or art.get("created_at") or datetime.utcnow().isoformat()
            art_title = art.get("title") or ""
            art_desc = art.get("description") or ""
            art_text = f"{art_title} {art_desc}".lower()

            ents = entity_extractor.extract_entities(art_title, art_desc)
            new_ents = ents - seen_entities
            seen_entities.update(ents)

            # Classify event type
            if any(kw in art_text for kw in self.resolution_keywords):
                ev_type = "RESOLUTION"
                title = f"Resolution reported by {art_source}"
                significance = 0.85
            elif any(kw in art_text for kw in self.escalation_keywords):
                ev_type = "ESCALATION"
                title = f"Escalation reported by {art_source}"
                significance = 0.85
            elif any(kw in art_text for kw in self.correction_keywords):
                ev_type = "CORRECTION"
                title = f"Correction issued by {art_source}"
                significance = 0.70
            elif any(kw in art_text for kw in self.contradiction_keywords):
                ev_type = "CONTRADICTION"
                title = f"Conflicting statement by {art_source}"
                significance = 0.75
            elif len(new_ents) > 0 or any(kw in art_text for kw in MILESTONE_KEYWORDS):
                ev_type = "DEVELOPMENT"
                title = f"New development confirmed by {art_source}"
                significance = 0.70
            else:
                # Corroborating coverage
                ev_type = "UPDATE"
                title = f"Corroborating reporting by {art_source}"
                significance = 0.50

            events.append({
                "id": f"ev_{story['id'][:10]}_{idx}",
                "story_id": story["id"],
                "event_type": ev_type,
                "title": title,
                "summary": art_title,
                "article_ids": [art_id],
                "occurred_at": art_time,
                "significance": significance,
                "event_version": "v1"
            })

        return events

    # =========================================================================
    # 5. Contradiction & Perspective Detection
    # =========================================================================
    def detect_perspectives(
        self,
        story: Dict[str, Any],
        articles: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detects conflicting grounded perspectives across distinct reporting sources.
        Example: Source A denies allegation vs Source B researchers present evidence.
        Never manufactures artificial controversy.
        """
        if len(articles) < 2:
            return []

        perspectives: List[Dict[str, Any]] = []

        sources_map: Dict[str, List[Dict[str, Any]]] = {}
        for a in articles:
            s_name = a.get("source_name") or "Source"
            sources_map.setdefault(s_name, []).append(a)

        if len(sources_map) < 2:
            return []

        denial_articles: List[Dict[str, Any]] = []
        assertion_articles: List[Dict[str, Any]] = []

        denial_patterns = [r"\b(?:denies|denied|refutes|disputes|dismisses|rejects|claims false)\b"]
        assertion_patterns = [r"\b(?:reveals|uncovers|demonstrates|presents evidence|claims that|accuses|confirms attack)\b"]

        for a in articles:
            text = f"{a.get('title', '')} {a.get('description', '')}".lower()
            if any(re.search(p, text) for p in denial_patterns):
                denial_articles.append(a)
            elif any(re.search(p, text) for p in assertion_patterns):
                assertion_articles.append(a)

        if denial_articles and assertion_articles:
            denial_source = denial_articles[0].get("source_name", "Source A")
            assertion_source = assertion_articles[0].get("source_name", "Source B")

            if denial_source != assertion_source:
                perspectives.append({
                    "topic_or_issue": story.get("primary_topic") or story.get("title", "Event Investigation"),
                    "status": "Conflicting reporting",
                    "sources": [
                        {
                            "source_name": denial_source,
                            "stance": "denies allegations / disputed claims",
                            "article_id": str(denial_articles[0].get("id") or denial_articles[0].get("article_id", "")),
                            "claim_text": denial_articles[0].get("title", "")
                        },
                        {
                            "source_name": assertion_source,
                            "stance": "presents evidence / asserts report",
                            "article_id": str(assertion_articles[0].get("id") or assertion_articles[0].get("article_id", "")),
                            "claim_text": assertion_articles[0].get("title", "")
                        }
                    ],
                    "detected_at": datetime.utcnow().isoformat()
                })

        return perspectives

    # =========================================================================
    # 6. Story Evolution Orchestrator
    # =========================================================================
    def evolve_story(self, story_id: str) -> Optional[Dict[str, Any]]:
        """
        Executes complete deterministic story evolution calculation for a single story.
        Persists timeline events and updates story evolution fields.
        """
        story = self.db.get_story_by_id(story_id)
        if not story:
            return None

        articles = self.db.get_articles_for_story(story_id)
        if not articles:
            articles = story.get("articles") or []

        # 1. Synthesize grounded timeline events
        events = self.generate_timeline_events(story, articles)
        for ev in events:
            self.db.insert_story_event(ev)

        # 2. Breaking score & level
        breaking_score, breaking_level, _ = self.compute_breaking_score(story, articles)

        # 3. Deterministic lifecycle state
        story_status = self.determine_lifecycle_state(story, articles, events)

        # 4. Conflicting perspectives
        perspectives = self.detect_perspectives(story, articles)

        # 5. Latest Development
        update_events = [ev for ev in events if ev["event_type"] in {"DEVELOPMENT", "ESCALATION", "CORRECTION", "RESOLUTION"}]
        if update_events:
            latest_ev = update_events[-1]
            latest_development = f"{latest_ev['title']}: {latest_ev['summary']}"
            latest_updated_at = latest_ev.get("occurred_at") or latest_ev.get("detected_at")
        elif len(events) > 1:
            latest_ev = events[-1]
            latest_development = f"{latest_ev['title']}: {latest_ev['summary']}"
            latest_updated_at = latest_ev.get("occurred_at") or latest_ev.get("detected_at")
        else:
            latest_development = story.get("why_it_matters") or story.get("summary")
            latest_updated_at = story.get("last_published_at") or story.get("created_at")

        update_count = max(0, len(articles) - 1)

        evolution_data = {
            "story_status": story_status,
            "breaking_score": breaking_score,
            "breaking_level": breaking_level,
            "latest_development": latest_development,
            "latest_updated_at": latest_updated_at,
            "update_count": update_count,
            "perspectives": perspectives,
            "evolution_version": self.version
        }

        self.db.save_story_evolution(story_id, evolution_data)

        # Return updated story representation
        return self.db.get_story_by_id(story_id)

    def evolve_all_stories(self, limit: int = 100) -> Dict[str, Any]:
        """
        Batch executes story evolution across stories in the database.
        """
        stories = self.db.get_stories(limit=limit)
        evolved_count = 0
        breaking_count = 0

        for s in stories:
            updated = self.evolve_story(s["id"])
            if updated:
                evolved_count += 1
                if updated.get("breaking_level") == "BREAKING":
                    breaking_count += 1

        return {
            "status": "success",
            "stories_evolved": evolved_count,
            "breaking_stories": breaking_count,
            "version": self.version,
            "timestamp": datetime.utcnow().isoformat()
        }


story_evolution_service = StoryEvolutionService()
