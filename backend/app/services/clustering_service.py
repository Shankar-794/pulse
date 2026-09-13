"""
Story Intelligence Clustering Service (Phase 3B Upgrade).
Provides hybrid semantic clustering combining lexical TF-IDF representations
and precision-gated entity overlap, with pluggable similarity providers
and comprehensive diagnostics.
"""
import re
import time
import hashlib
import logging
from typing import List, Dict, Any, Tuple, Optional, Set
from datetime import datetime
import numpy as np

from backend.app.core.config import settings
from backend.app.core.db_repository import db_repository
from backend.app.services.similarity_provider import TextSimilarityProvider, TFIDFSimilarityProvider
from backend.app.services.entity_extractor import entity_extractor

logger = logging.getLogger("pulse.services.clustering")

HIGH_IMPACT_KEYWORDS = {
    "vulnerability", "zero-day", "breach", "cve", "ransomware", "outage",
    "breakthrough", "quantum", "critical", "discovery", "launch", "exploit",
    "antitrust", "fda", "sec", "emergency", "crisis", "investigation"
}


class ClusteringService:
    def __init__(
        self,
        similarity_threshold: Optional[float] = None,
        time_window_hours: Optional[int] = None,
        lexical_weight: Optional[float] = None,
        entity_weight: Optional[float] = None,
        similarity_provider: Optional[TextSimilarityProvider] = None,
        db_repo: Optional[Any] = None
    ):
        self.similarity_threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else getattr(settings, "CLUSTER_SIMILARITY_THRESHOLD", 0.32)
        )
        self.time_window_hours = (
            time_window_hours
            if time_window_hours is not None
            else getattr(settings, "CLUSTER_TIME_WINDOW_HOURS", 72)
        )
        self.lexical_weight = (
            lexical_weight
            if lexical_weight is not None
            else getattr(settings, "CLUSTER_LEXICAL_WEIGHT", 0.65)
        )
        self.entity_weight = (
            entity_weight
            if entity_weight is not None
            else getattr(settings, "CLUSTER_ENTITY_WEIGHT", 0.35)
        )
        self.similarity_provider = similarity_provider or TFIDFSimilarityProvider()
        self.db_repo = db_repo or db_repository
        self.last_metrics: Dict[str, Any] = {}

    def get_category_relationships(self) -> Dict[str, List[str]]:
        return getattr(settings, "CATEGORY_RELATIONSHIPS", {
            "technology": ["ai", "cybersecurity", "software engineering", "semiconductors", "science", "space", "world"],
            "ai": ["technology", "software engineering", "science", "world"],
            "cybersecurity": ["technology", "software engineering", "world"],
            "space": ["science", "technology"],
            "science": ["space", "technology", "ai"],
            "world": ["technology", "ai", "cybersecurity", "general"]
        })

    def is_candidate_pair(self, cat1: str, cat2: str) -> bool:
        """
        Determines whether two articles are eligible for clustering comparison based on category.
        """
        c1 = (cat1 or "general").lower()
        c2 = (cat2 or "general").lower()
        if c1 == c2:
            return True
        rel = self.get_category_relationships()
        return c2 in rel.get(c1, []) or c1 in rel.get(c2, [])

    def build_article_representation(self, article: Dict[str, Any]) -> str:
        """
        Creates weighted text representation for vectorization.
        Uses clean headline (doubled for headline focus), topic, and leading summary.
        """
        clean_title = entity_extractor.clean_headline(article.get("title") or "")
        topic = (article.get("primary_topic") or "").strip()
        raw_desc = (article.get("description") or "").strip()

        # Strip recurring boilerplate (e.g. daily astronomy picture boilerplate)
        desc = re.sub(
            r"Each day a different image or photograph.*?written by a professional astronomer\.",
            "",
            raw_desc,
            flags=re.DOTALL
        )
        clean_desc = re.sub(r"<[^>]+>", " ", desc).strip()[:200]

        return f"{clean_title} {clean_title} {topic} {clean_desc}".strip()

    def compute_pair_similarity(
        self,
        article_a: Dict[str, Any],
        article_b: Dict[str, Any],
        title_sim: float,
        full_sim: float,
        entities_a: Set[str],
        entities_b: Set[str]
    ) -> Tuple[float, float, float, Set[str]]:
        """
        Computes the hybrid similarity between two candidate articles.
        Returns (hybrid_score, lexical_score, entity_score, common_entities).
        """
        # Entity overlap score
        ent_score, common_entities = entity_extractor.compute_overlap(
            entities_a, entities_b, title_similarity=title_sim
        )

        # Lexical score combines title similarity (60%) and full representation (40%)
        lex_score = 0.60 * title_sim + 0.40 * full_sim

        # Guard against zero title similarity (e.g. cross-topic descriptions or boilerplate leaks)
        if title_sim < 0.10 and ent_score == 0:
            hybrid_score = 0.0
        else:
            hybrid_score = (self.lexical_weight * lex_score) + (self.entity_weight * ent_score)

        return round(float(hybrid_score), 4), round(float(lex_score), 4), round(float(ent_score), 4), common_entities

    def compute_diagnostics(self, time_window_hours: Optional[int] = None) -> Dict[str, Any]:
        """
        Diagnostic inspection on the actual dataset.
        Calculates similarity distribution, candidate counts, and top pair details.
        """
        window_hours = time_window_hours or self.time_window_hours
        articles = self.db_repo.get_articles_in_window(hours=window_hours)
        if not articles:
            articles = self.db_repo.get_articles(limit=200)

        n = len(articles)
        if n == 0:
            return {
                "articles": 0,
                "candidate_pairs": 0,
                "similarity": {"min": 0, "max": 0, "mean": 0, "median": 0, "p90": 0},
                "thresholds": {"0.20": 0, "0.30": 0, "0.40": 0, "0.50": 0, "0.60": 0, "0.70": 0},
                "top_pairs": []
            }

        # Vector representations
        clean_titles = [entity_extractor.clean_headline(a.get("title") or "") for a in articles]
        title_sim_mat = self.similarity_provider.compute_similarity_matrix(clean_titles)

        full_reps = [self.build_article_representation(a) for a in articles]
        full_sim_mat = self.similarity_provider.compute_similarity_matrix(full_reps)

        entities_list = [
            entity_extractor.extract_entities(a.get("title") or "", a.get("description") or "")
            for a in articles
        ]

        candidate_scores: List[float] = []
        detailed_pairs: List[Dict[str, Any]] = []

        for i in range(n):
            cat_i = articles[i].get("category") or ""
            for j in range(i + 1, n):
                cat_j = articles[j].get("category") or ""
                if not self.is_candidate_pair(cat_i, cat_j):
                    continue

                t_sim = float(title_sim_mat[i, j])
                f_sim = float(full_sim_mat[i, j])
                hybrid, lex, ent, common = self.compute_pair_similarity(
                    articles[i], articles[j], t_sim, f_sim, entities_list[i], entities_list[j]
                )

                candidate_scores.append(hybrid)

                if hybrid >= 0.15:
                    detailed_pairs.append({
                        "similarity": hybrid,
                        "lexical_similarity": lex,
                        "entity_overlap": ent,
                        "title_similarity": round(t_sim, 4),
                        "common_entities": sorted(list(common)),
                        "article_a": {
                            "id": articles[i]["id"],
                            "title": articles[i].get("title"),
                            "source": articles[i].get("source_name"),
                            "category": articles[i].get("category"),
                            "representation": full_reps[i][:150] + "..."
                        },
                        "article_b": {
                            "id": articles[j]["id"],
                            "title": articles[j].get("title"),
                            "source": articles[j].get("source_name"),
                            "category": articles[j].get("category"),
                            "representation": full_reps[j][:150] + "..."
                        }
                    })

        scores_arr = np.array(candidate_scores) if candidate_scores else np.array([0.0])
        detailed_pairs.sort(key=lambda x: x["similarity"], reverse=True)

        return {
            "articles": n,
            "candidate_pairs": len(candidate_scores),
            "similarity": {
                "min": round(float(np.min(scores_arr)), 4),
                "max": round(float(np.max(scores_arr)), 4),
                "mean": round(float(np.mean(scores_arr)), 4),
                "median": round(float(np.median(scores_arr)), 4),
                "p90": round(float(np.percentile(scores_arr, 90)), 4)
            },
            "thresholds": {
                "0.20": int(np.sum(scores_arr >= 0.20)),
                "0.30": int(np.sum(scores_arr >= 0.30)),
                "0.40": int(np.sum(scores_arr >= 0.40)),
                "0.50": int(np.sum(scores_arr >= 0.50)),
                "0.60": int(np.sum(scores_arr >= 0.60)),
                "0.70": int(np.sum(scores_arr >= 0.70))
            },
            "top_pairs": detailed_pairs[:10]
        }

    def cluster_candidates(
        self,
        articles: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Clusters articles using graph connected components over hybrid similarity matrix.
        """
        n = len(articles)
        if n == 0:
            return []
        if n == 1:
            return [[articles[0]]]

        clean_titles = [entity_extractor.clean_headline(a.get("title") or "") for a in articles]
        title_sim_mat = self.similarity_provider.compute_similarity_matrix(clean_titles)

        full_reps = [self.build_article_representation(a) for a in articles]
        full_sim_mat = self.similarity_provider.compute_similarity_matrix(full_reps)

        entities_list = [
            entity_extractor.extract_entities(a.get("title") or "", a.get("description") or "")
            for a in articles
        ]

        adj: Dict[int, Set[int]] = {i: set() for i in range(n)}

        for i in range(n):
            cat_i = articles[i].get("category") or ""
            for j in range(i + 1, n):
                cat_j = articles[j].get("category") or ""
                if not self.is_candidate_pair(cat_i, cat_j):
                    continue

                t_sim = float(title_sim_mat[i, j])
                f_sim = float(full_sim_mat[i, j])
                hybrid, _, _, _ = self.compute_pair_similarity(
                    articles[i], articles[j], t_sim, f_sim, entities_list[i], entities_list[j]
                )

                if hybrid >= self.similarity_threshold:
                    adj[i].add(j)
                    adj[j].add(i)

        # Find connected components
        visited = set()
        clusters: List[List[Dict[str, Any]]] = []

        for i in range(n):
            if i in visited:
                continue

            component_indices = []
            queue = [i]
            visited.add(i)

            while queue:
                curr = queue.pop(0)
                component_indices.append(curr)
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

            cluster_articles = [articles[idx] for idx in component_indices]
            clusters.append(cluster_articles)

        return clusters

    def generate_canonical_story(
        self,
        cluster_articles: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Synthesizes a canonical story from a cluster of articles.
        """
        sorted_articles = sorted(
            cluster_articles,
            key=lambda a: a.get("published_at", ""),
            reverse=True
        )

        canonical_article = max(
            sorted_articles,
            key=lambda a: len(a.get("description") or "") + len(a.get("title") or "")
        )

        # Deterministic story ID based on sorted canonical URLs
        sorted_urls = sorted([
            a.get("canonical_url") or a.get("url") or a["id"]
            for a in cluster_articles
        ])
        seed = "|".join(sorted_urls)
        story_id = f"story_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"

        unique_sources = set(a.get("source_name") for a in cluster_articles if a.get("source_name"))
        source_count = max(len(unique_sources), 1)
        article_count = len(cluster_articles)

        base_importance = 50
        # Multi-source verification boost: +15 points per distinct additional source
        source_boost = (source_count - 1) * 15

        text_content = f"{canonical_article.get('title', '')} {canonical_article.get('description', '')}".lower()
        impact_boost = 10 if any(kw in text_content for kw in HIGH_IMPACT_KEYWORDS) else 0

        importance_score = min(98, max(25, base_importance + source_boost + impact_boost))
        relevance_score = min(95, 60 + (source_count * 5))
        freshness_score = 95

        pub_dates = [a.get("published_at") for a in cluster_articles if a.get("published_at")]
        first_pub = min(pub_dates) if pub_dates else datetime.utcnow().isoformat()
        last_pub = max(pub_dates) if pub_dates else datetime.utcnow().isoformat()

        if source_count > 1:
            sources_str = ", ".join(sorted(unique_sources)[:3])
            why_it_matters = (
                f"Cross-verified by {source_count} independent outlets ({sources_str}). "
                f"Multi-source coverage confirms broad industry impact."
            )
        else:
            source_name = canonical_article.get("source_name") or "Direct Wire"
            why_it_matters = (
                f"Reported directly by {source_name}. "
                f"Ongoing development in {canonical_article.get('category', 'Technology')}."
            )

        now_str = datetime.utcnow().isoformat()

        return {
            "id": story_id,
            "title": canonical_article.get("title"),
            "summary": canonical_article.get("description") or canonical_article.get("title"),
            "why_it_matters": why_it_matters,
            "category": canonical_article.get("category", "Technology"),
            "primary_topic": canonical_article.get("primary_topic", "Technology"),
            "importance_score": importance_score,
            "relevance_score": relevance_score,
            "freshness_score": freshness_score,
            "source_count": source_count,
            "article_count": article_count,
            "first_published_at": first_pub,
            "last_published_at": last_pub,
            "created_at": now_str,
            "updated_at": now_str
        }

    def run_clustering(
        self,
        time_window_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes the clustering pipeline over candidate articles.
        Idempotent: cleans up previous story associations before re-clustering.
        """
        start_time = time.time()
        window_hours = time_window_hours or self.time_window_hours

        articles = self.db_repo.get_articles_in_window(hours=window_hours)
        if not articles:
            articles = self.db_repo.get_articles(limit=500)

        article_ids = [a["id"] for a in articles]
        logger.info(f"Clustering candidate selection: {len(articles)} articles found.")

        # Reset prior story links for clean idempotency
        self.db_repo.reset_story_links(article_ids)

        # Cluster articles with candidate relationship filtering & hybrid similarity
        all_clusters = self.cluster_candidates(articles)

        stories_created = 0
        multi_source_stories = 0
        singleton_stories = 0
        largest_cluster = 1
        max_sources = 1

        for cluster in all_clusters:
            story_data = self.generate_canonical_story(cluster)
            self.db_repo.upsert_story(story_data)

            cluster_article_ids = [a["id"] for a in cluster]
            self.db_repo.link_articles_to_story(story_data["id"], cluster_article_ids)

            stories_created += 1
            if story_data["source_count"] > 1:
                multi_source_stories += 1
            else:
                singleton_stories += 1

            if len(cluster) > largest_cluster:
                largest_cluster = len(cluster)
            if story_data["source_count"] > max_sources:
                max_sources = story_data["source_count"]

        duration = round(time.time() - start_time, 3)
        avg_cluster_size = round(len(articles) / max(stories_created, 1), 2)

        self.last_metrics = {
            "status": "success",
            "articles_processed": len(articles),
            "stories_created": stories_created,
            "multi_source_stories": multi_source_stories,
            "singleton_stories": singleton_stories,
            "largest_cluster_size": largest_cluster,
            "average_cluster_size": avg_cluster_size,
            "max_sources_in_story": max_sources,
            "similarity_threshold": self.similarity_threshold,
            "lexical_weight": self.lexical_weight,
            "entity_weight": self.entity_weight,
            "time_window_hours": window_hours,
            "duration_seconds": duration,
            "timestamp": datetime.utcnow().isoformat()
        }

        logger.info(
            f"Clustering complete: {len(articles)} articles -> {stories_created} stories "
            f"({multi_source_stories} multi-source, largest {largest_cluster}) in {duration}s."
        )

        return self.last_metrics

    def get_metrics(self) -> Dict[str, Any]:
        return self.last_metrics or {
            "status": "idle",
            "articles_processed": 0,
            "stories_created": 0,
            "multi_source_stories": 0,
            "singleton_stories": 0,
            "similarity_threshold": self.similarity_threshold,
            "time_window_hours": self.time_window_hours
        }


clustering_service = ClusteringService()
