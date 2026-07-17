"""Stage → numbered-section maps for sliced Admin Knowledge articles.

Co-located with seed content (not buried only in knowledge_packs). Numeric
ids remain the stable contract; optional `{#anchor}` suffixes on `## N. Title`
headers are indexed for future named lookups without breaking packing.
"""

from __future__ import annotations

from app.prompts.prompt_registry import PipelineStage

# Numbered sections from INTERPRETATION_GUARDRAILS.
INTERPRETATION_SECTIONS_BY_STAGE: dict[PipelineStage, tuple[int, ...]] = {
    PipelineStage.BUILD_COURSE_MAP: (10, 11, 15, 16, 17, 25),
    PipelineStage.WRITE_SINGLE_REEL: (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 21, 22, 23, 24),
    PipelineStage.REVIEW_SINGLE_REEL: (12, 13, 14, 23),
    PipelineStage.REVIEW_FIVE_REELS: (12, 13, 14, 23),
    PipelineStage.REVIEW_MODULE: (12, 13, 14, 15, 23),
    PipelineStage.REVIEW_TWO_MODULES: (12, 13, 14, 15, 23),
    PipelineStage.FINAL_REVIEW: (19, 2, 3, 9, 24, 25, 20),
    PipelineStage.REBUILD_FINAL_COURSE: (19, 1, 2, 3, 9, 23, 24, 25, 20),
}

EDUCATIONAL_CREATOR_SECTIONS_BY_STAGE: dict[PipelineStage, tuple[int, ...]] = {
    PipelineStage.BUILD_COURSE_MAP: (1, 8, 13),
    PipelineStage.WRITE_SINGLE_REEL: (11, 4, 3, 1, 2, 5, 9, 10, 6),
    PipelineStage.REVIEW_SINGLE_REEL: (2, 7, 9, 12),
    PipelineStage.REVIEW_FIVE_REELS: (2, 7, 9, 12),
    PipelineStage.REVIEW_MODULE: (2, 7, 8, 9, 12),
    PipelineStage.REVIEW_TWO_MODULES: (2, 7, 8, 9, 12),
    PipelineStage.FINAL_REVIEW: (5, 6, 7, 9, 11, 12),
    PipelineStage.REBUILD_FINAL_COURSE: (1, 4, 5, 6, 7, 9, 11, 12),
}

SOURCE_DISTILLATION_SECTIONS_BY_STAGE: dict[PipelineStage, tuple[int, ...]] = {
    PipelineStage.BUILD_COURSE_MAP: (1, 2, 6, 7),
    PipelineStage.WRITE_SINGLE_REEL: (1, 2, 3, 4, 5, 6, 7),
    PipelineStage.REVIEW_SINGLE_REEL: (1, 2, 3, 7, 8),
    PipelineStage.REVIEW_FIVE_REELS: (1, 2, 7, 8),
    PipelineStage.REVIEW_MODULE: (1, 2, 7, 8),
    PipelineStage.REVIEW_TWO_MODULES: (1, 2, 7, 8),
    PipelineStage.FINAL_REVIEW: (1, 2, 3, 5, 6, 7, 8),
    PipelineStage.REBUILD_FINAL_COURSE: (1, 2, 3, 5, 6, 7, 8),
}

TRANSCRIPT_TOPIC_RELEVANCE_SECTIONS_BY_STAGE: dict[PipelineStage, tuple[int, ...]] = {
    PipelineStage.BUILD_COURSE_MAP: (1, 2, 3, 6),
    PipelineStage.WRITE_SINGLE_REEL: (1, 2, 3, 4, 5, 6, 7),
    PipelineStage.REVIEW_SINGLE_REEL: (1, 2, 3, 5, 7, 8),
    PipelineStage.REVIEW_FIVE_REELS: (1, 2, 5, 8),
    PipelineStage.REVIEW_MODULE: (1, 2, 5, 8),
    PipelineStage.REVIEW_TWO_MODULES: (1, 2, 5, 8),
    PipelineStage.FINAL_REVIEW: (1, 2, 3, 5, 7, 8),
    PipelineStage.REBUILD_FINAL_COURSE: (1, 2, 3, 5, 7, 8),
}

ANTI_PATTERNS_SECTIONS_BY_STAGE: dict[PipelineStage, tuple[int, ...]] = {
    PipelineStage.REVIEW_SINGLE_REEL: (1, 2),
    PipelineStage.REVIEW_FIVE_REELS: (1, 2),
    PipelineStage.REVIEW_MODULE: (1, 2),
    PipelineStage.REVIEW_TWO_MODULES: (1, 2),
    PipelineStage.FINAL_REVIEW: (1, 3, 4),
    PipelineStage.REBUILD_FINAL_COURSE: (1, 2, 3),
}
