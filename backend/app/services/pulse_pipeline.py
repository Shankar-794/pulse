"""
Pulse End-to-End Pipeline Orchestrator (Phase 8.1).
Connects the discrete Pulse intelligence services in a deterministic, robust,
idempotent sequence:
1. Ingestion: Ingests news from registered feeds with source failure isolation.
2. Clustering: Clusters articles into canonical stories using hybrid similarity.
3. Story Analysis: Synthesizes grounded AI story understanding and claims.
4. Global Importance: Deterministically calculates objective global importance (0-100).
5. Story Evolution: Computes lifecycle states, breaking news scores, timelines, and perspectives.
6. Personal Relevance: Evaluates personalized interest alignment and affinities.
7. Feed Readiness: Runs composite ranking and category interleaving for feed delivery.

Safety & Resilience:
- Safe to run repeatedly (idempotent).
- Source and article failures are isolated and never crash the pipeline.
- Returns detailed stage-level metrics and overall duration.
"""
import time
import uuid
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from backend.app.core.db_repository import db_repository
from backend.app.services.ingestion_service import ingestion_service
from backend.app.services.clustering_service import clustering_service
from backend.app.services.story_analysis_service import story_analysis_service
from backend.app.services.importance_service import importance_service
from backend.app.services.story_evolution_service import story_evolution_service
from backend.app.services.personal_relevance_service import personal_relevance_service
from backend.app.services.feed_ranking_service import feed_ranking_service

logger = logging.getLogger("pulse.pipeline")


class PulsePipeline:
    """
    End-to-End Pipeline Orchestrator with persistent execution history (Phase 8.2).
    """

    def __init__(
        self,
        ingestion_svc=None,
        clustering_svc=None,
        analysis_svc=None,
        importance_svc=None,
        evolution_svc=None,
        relevance_svc=None,
        feed_svc=None,
        db_repo=None
    ):
        self.ingestion = ingestion_svc or ingestion_service
        self.clustering = clustering_svc or clustering_service
        self.analysis = analysis_svc or story_analysis_service
        self.importance = importance_svc or importance_service
        self.evolution = evolution_svc or story_evolution_service
        self.relevance = relevance_svc or personal_relevance_service
        self.feed = feed_svc or feed_ranking_service
        self.db = db_repo or db_repository
        self._last_run: Optional[Dict[str, Any]] = None

    async def run_pipeline(
        self,
        skip_ingestion: bool = False,
        time_window_hours: Optional[int] = None,
        analysis_limit: int = 50,
        importance_limit: int = 100,
        evolution_limit: int = 100,
        feed_limit: int = 50,
        user_id: str = "default_user",
        trigger_type: str = "manual",
        run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes the complete 7-stage Pulse pipeline in strict sequence.
        Persists run metadata, metrics, and stage status for full auditability.
        Returns structured stage-level metrics and total duration.
        """
        start_time = time.time()
        start_dt = datetime.now(timezone.utc).isoformat()
        existing_record = self.db.get_pipeline_run(run_id) if run_id else None
        run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        logger.info(f"[PIPELINE] Starting Pulse end-to-end pipeline run [{run_id}].")

        initial_stages = {
            "ingestion": {"status": "pending" if not skip_ingestion else "skipped"},
            "clustering": {"status": "pending"},
            "story_analysis": {"status": "pending"},
            "global_importance": {"status": "pending"},
            "story_evolution": {"status": "pending"},
            "personal_relevance": {"status": "pending"},
            "feed_readiness": {"status": "pending"}
        }

        # 1. Ensure run record is in DB with status 'running' and initial stage states
        if existing_record:
            self.db.update_pipeline_run(run_id, {
                "status": "running",
                "started_at": start_dt,
                "stages": initial_stages
            })
        else:
            self.db.create_pipeline_run(
                run_id=run_id,
                status="running",
                started_at=start_dt,
                trigger_type=trigger_type,
                user_id=user_id,
                skip_ingestion=skip_ingestion,
                stages=initial_stages
            )

        stages: Dict[str, Any] = dict(initial_stages)

        try:
            # =====================================================================
            # Stage 1: Ingestion
            # =====================================================================
            s1_start = time.time()
            if not skip_ingestion:
                stages["ingestion"] = {"status": "running"}
                self.db.update_pipeline_run(run_id, {"stages": stages})
                try:
                    ingestion_summary = await self.ingestion.run_ingestion_cycle()
                    stages["ingestion"] = {
                        "status": "success",
                        "duration_seconds": round(time.time() - s1_start, 3),
                        "sources_checked": ingestion_summary.get("sources_checked", 0),
                        "articles_seen": ingestion_summary.get("articles_seen", 0),
                        "new_articles": ingestion_summary.get("new_articles", 0),
                        "duplicates": ingestion_summary.get("duplicates", 0),
                        "failed_sources": ingestion_summary.get("failed_sources", 0)
                    }
                except Exception as err:
                    logger.error(f"[PIPELINE] Ingestion stage error (isolated): {err}")
                    stages["ingestion"] = {
                        "status": "partial_failure",
                        "error": str(err),
                        "duration_seconds": round(time.time() - s1_start, 3)
                    }
            else:
                stages["ingestion"] = {
                    "status": "skipped",
                    "duration_seconds": 0.0
                }
            self.db.update_pipeline_run(run_id, {"stages": stages})

            # =====================================================================
            # Stage 2: Clustering
            # =====================================================================
            stages["clustering"] = {"status": "running"}
            self.db.update_pipeline_run(run_id, {"stages": stages})
            s2_start = time.time()
            try:
                clustering_metrics = self.clustering.run_clustering(time_window_hours=time_window_hours)
                stages["clustering"] = {
                    "status": "success",
                    "duration_seconds": round(time.time() - s2_start, 3),
                    "articles_processed": clustering_metrics.get("articles_processed", 0),
                    "stories_created": clustering_metrics.get("stories_created", 0),
                    "multi_source_stories": clustering_metrics.get("multi_source_stories", 0),
                    "singleton_stories": clustering_metrics.get("singleton_stories", 0),
                    "largest_cluster_size": clustering_metrics.get("largest_cluster_size", 0)
                }
            except Exception as err:
                logger.error(f"[PIPELINE] Clustering stage error: {err}")
                stages["clustering"] = {
                    "status": "failed",
                    "error": str(err),
                    "duration_seconds": round(time.time() - s2_start, 3)
                }
            self.db.update_pipeline_run(run_id, {"stages": stages})

            # =====================================================================
            # Stage 3: Story Analysis
            # =====================================================================
            stages["story_analysis"] = {"status": "running"}
            self.db.update_pipeline_run(run_id, {"stages": stages})
            s3_start = time.time()
            try:
                analysis_metrics = self.analysis.analyze_batch(limit=analysis_limit)
                stages["story_analysis"] = {
                    "status": "success",
                    "duration_seconds": round(time.time() - s3_start, 3),
                    "stories_evaluated": analysis_metrics.get("total_evaluated", 0),
                    "analyzed_count": analysis_metrics.get("success_count", 0),
                    "failed_count": analysis_metrics.get("failure_count", 0)
                }
            except Exception as err:
                logger.error(f"[PIPELINE] Story Analysis stage error: {err}")
                stages["story_analysis"] = {
                    "status": "failed",
                    "error": str(err),
                    "duration_seconds": round(time.time() - s3_start, 3)
                }
            self.db.update_pipeline_run(run_id, {"stages": stages})

            # =====================================================================
            # Stage 4: Global Importance
            # =====================================================================
            stages["global_importance"] = {"status": "running"}
            self.db.update_pipeline_run(run_id, {"stages": stages})
            s4_start = time.time()
            try:
                importance_metrics = self.importance.calculate_batch_importance(limit=importance_limit)
                stages["global_importance"] = {
                    "status": "success",
                    "duration_seconds": round(time.time() - s4_start, 3),
                    "scored_count": importance_metrics.get("processed_count", 0),
                    "version": importance_metrics.get("version", "v1")
                }
            except Exception as err:
                logger.error(f"[PIPELINE] Global Importance stage error: {err}")
                stages["global_importance"] = {
                    "status": "failed",
                    "error": str(err),
                    "duration_seconds": round(time.time() - s4_start, 3)
                }
            self.db.update_pipeline_run(run_id, {"stages": stages})

            # =====================================================================
            # Stage 5: Story Evolution
            # =====================================================================
            stages["story_evolution"] = {"status": "running"}
            self.db.update_pipeline_run(run_id, {"stages": stages})
            s5_start = time.time()
            try:
                evolution_metrics = self.evolution.evolve_all_stories(limit=evolution_limit)
                stages["story_evolution"] = {
                    "status": "success",
                    "duration_seconds": round(time.time() - s5_start, 3),
                    "stories_evolved": evolution_metrics.get("stories_evolved", 0),
                    "breaking_stories": evolution_metrics.get("breaking_stories", 0),
                    "version": evolution_metrics.get("version", "v1")
                }
            except Exception as err:
                logger.error(f"[PIPELINE] Story Evolution stage error: {err}")
                stages["story_evolution"] = {
                    "status": "failed",
                    "error": str(err),
                    "duration_seconds": round(time.time() - s5_start, 3)
                }
            self.db.update_pipeline_run(run_id, {"stages": stages})

            # =====================================================================
            # Stage 6: Personal Relevance
            # =====================================================================
            stages["personal_relevance"] = {"status": "running"}
            self.db.update_pipeline_run(run_id, {"stages": stages})
            s6_start = time.time()
            try:
                user_profile = self.db.get_user_preferences(user_id)
                candidate_stories = self.db.get_stories(limit=feed_limit)
                relevance_scores = []
                for s in candidate_stories:
                    bd = self.relevance.compute_relevance(s, user_profile)
                    relevance_scores.append(bd.personal_relevance_score)

                avg_score = round(sum(relevance_scores) / max(len(relevance_scores), 1), 1)
                stages["personal_relevance"] = {
                    "status": "success",
                    "duration_seconds": round(time.time() - s6_start, 3),
                    "user_id": user_id,
                    "stories_evaluated": len(relevance_scores),
                    "average_relevance": avg_score
                }
            except Exception as err:
                logger.error(f"[PIPELINE] Personal Relevance stage error: {err}")
                stages["personal_relevance"] = {
                    "status": "failed",
                    "error": str(err),
                    "duration_seconds": round(time.time() - s6_start, 3)
                }
            self.db.update_pipeline_run(run_id, {"stages": stages})

            # =====================================================================
            # Stage 7: Feed Ranking / Readiness
            # =====================================================================
            stages["feed_readiness"] = {"status": "running"}
            self.db.update_pipeline_run(run_id, {"stages": stages})
            s7_start = time.time()
            try:
                feed_items = self.feed.rank_feed(user_id=user_id, limit=feed_limit)
                cats = sorted(list({item.get("category") for item in feed_items if item.get("category")}))
                overrides = sum(1 for item in feed_items if item.get("is_global_override"))

                stages["feed_readiness"] = {
                    "status": "success",
                    "duration_seconds": round(time.time() - s7_start, 3),
                    "feed_items_count": len(feed_items),
                    "top_story_id": feed_items[0].get("id") if feed_items else None,
                    "top_story_title": feed_items[0].get("title") if feed_items else None,
                    "categories_represented": cats,
                    "global_overrides_active": overrides
                }
            except Exception as err:
                logger.error(f"[PIPELINE] Feed readiness stage error: {err}")
                stages["feed_readiness"] = {
                    "status": "failed",
                    "error": str(err),
                    "duration_seconds": round(time.time() - s7_start, 3)
                }
            self.db.update_pipeline_run(run_id, {"stages": stages})

            # =====================================================================
            # Orchestration Summary & Persistence
            # =====================================================================
            total_duration = round(time.time() - start_time, 3)
            end_dt = datetime.now(timezone.utc).isoformat()

            # Check for any stage failures
            failed_stages = [
                k for k, stg in stages.items()
                if stg.get("status") in ("failed", "partial_failure")
            ]
            status = "partial_failure" if failed_stages else "success"

            # Extract summary counts across stages
            total_articles = self.db.get_total_count()
            new_articles = stages.get("ingestion", {}).get("new_articles", 0)
            total_stories = self.db.get_total_story_count()
            stories_created = stages.get("clustering", {}).get("stories_created", 0)
            stories_analyzed = stages.get("story_analysis", {}).get("analyzed_count", 0)
            stories_scored = stages.get("global_importance", {}).get("scored_count", 0)
            stories_evolved = stages.get("story_evolution", {}).get("stories_evolved", 0)
            feed_items = stages.get("feed_readiness", {}).get("feed_items_count", 0)

            # Update persistent DB record
            self.db.update_pipeline_run(run_id, {
                "status": status,
                "completed_at": end_dt,
                "duration_seconds": total_duration,
                "total_articles": total_articles,
                "new_articles": new_articles,
                "total_stories": total_stories,
                "stories_created": stories_created,
                "stories_analyzed": stories_analyzed,
                "stories_scored": stories_scored,
                "stories_evolved": stories_evolved,
                "feed_items": feed_items,
                "failed_stages": failed_stages,
                "stages": stages,
                "error_message": None
            })

            summary = {
                "run_id": run_id,
                "status": status,
                "total_duration_seconds": total_duration,
                "duration_seconds": total_duration,
                "started_at": start_dt,
                "completed_at": end_dt,
                "trigger_type": trigger_type,
                "user_id": user_id,
                "skip_ingestion": skip_ingestion,
                "total_articles": total_articles,
                "new_articles": new_articles,
                "total_stories": total_stories,
                "stories_created": stories_created,
                "stories_analyzed": stories_analyzed,
                "stories_scored": stories_scored,
                "stories_evolved": stories_evolved,
                "feed_items": feed_items,
                "failed_stages": failed_stages,
                "error_message": None,
                "stages": stages
            }

            self._last_run = summary
            stage_summary_str = ", ".join(f"{k}={v.get('status')}" for k, v in stages.items())
            logger.info(
                f"[PIPELINE] Complete in {total_duration}s. Run ID={run_id}. Status={summary['status']}. "
                f"Stages: {stage_summary_str}"
            )

            return summary

        except Exception as fatal_err:
            logger.critical(f"[PIPELINE] Unrecoverable pipeline failure: {fatal_err}", exc_info=True)
            total_duration = round(time.time() - start_time, 3)
            end_dt = datetime.now(timezone.utc).isoformat()
            error_message = str(fatal_err)
            failed_stages = list(stages.keys()) if stages else ["orchestration"]

            self.db.update_pipeline_run(run_id, {
                "status": "failed",
                "completed_at": end_dt,
                "duration_seconds": total_duration,
                "failed_stages": failed_stages,
                "error_message": error_message,
                "stages": stages
            })

            summary = {
                "run_id": run_id,
                "status": "failed",
                "total_duration_seconds": total_duration,
                "duration_seconds": total_duration,
                "started_at": start_dt,
                "completed_at": end_dt,
                "trigger_type": trigger_type,
                "user_id": user_id,
                "skip_ingestion": skip_ingestion,
                "failed_stages": failed_stages,
                "error_message": error_message,
                "stages": stages
            }
            self._last_run = summary
            return summary

    def get_last_run(self) -> Optional[Dict[str, Any]]:
        """Returns metadata and metrics of the last pipeline run from database or cache."""
        latest_db = self.db.get_latest_pipeline_run()
        if latest_db:
            return latest_db
        return self._last_run


pulse_pipeline = PulsePipeline()
