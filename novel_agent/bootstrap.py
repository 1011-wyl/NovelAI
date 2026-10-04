from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from novel_agent.api import AppContext
from novel_agent.config import Settings
from novel_agent.features.analytics.service import AnalyticsService
from novel_agent.features.opening_repair.service import OpeningRepairService
from novel_agent.features.projects.detail_reader import AggregatingProjectDetailReader
from novel_agent.features.projects.service import ProjectService
from novel_agent.features.story_design.service import StoryDesignService
from novel_agent.integrations.factories import (
    build_embedding_gateway,
    build_search_adapter,
)
from novel_agent.features.llm_settings.factory import LLMClientFactory
from novel_agent.features.llm_settings.repository import LLMSettingsRepository
from novel_agent.features.llm_settings.resolver import EffectiveLLMConfigResolver
from novel_agent.features.llm_settings.runtime import SnapshotLLMGateway
from novel_agent.features.llm_settings.secret_store import build_secret_store
from novel_agent.features.llm_settings.service import LLMSettingsService
from novel_agent.memory_manager import MemoryManager
from novel_agent.repository import SQLiteRepository
from novel_agent.service import NovelAgentService
from novel_agent.story_skills import StorySkillsRuntime
from novel_agent.writing_skills import OhStoryWritingRuntime


def create_context(root: Path | None = None, database_path: Path | None = None) -> AppContext:
    root = (root or Path.cwd()).resolve()
    settings = Settings.load(root)
    if database_path is not None:
        settings = replace(settings, database_path=database_path)
    repository = SQLiteRepository(settings.database_path)
    analytics_store = repository.analytics
    analytics_service = AnalyticsService(analytics_store)
    secrets = build_secret_store()
    llm_repo = LLMSettingsRepository(repository)
    llm_resolver = EffectiveLLMConfigResolver(settings, llm_repo, secrets)
    llm_factory = LLMClientFactory(
        reasoning_budget_factor=settings.llm_reasoning_budget_factor,
        on_call=analytics_store.save_token_usage,
    )
    gateway = SnapshotLLMGateway(llm_resolver, llm_factory)
    llm_settings = LLMSettingsService(
        llm_repo,
        secrets,
        llm_resolver,
        llm_factory,
        on_change=gateway.invalidate,
    )
    search = build_search_adapter(settings)
    embedding = build_embedding_gateway(settings)
    story_skills = StorySkillsRuntime.load(
        root,
        enabled=settings.story_skills_enabled,
    )
    writing_skills = OhStoryWritingRuntime.load(
        root,
        enabled=settings.oh_story_enabled,
    )
    memory_manager = MemoryManager(
        hot_budget_tokens=settings.memory_budget_tokens,
        character_chapter_gap=settings.memory_character_gap,
        world_fact_chapter_gap=settings.memory_world_fact_gap,
        timeline_chapter_gap=settings.memory_timeline_gap,
        research_chapter_gap=settings.memory_research_gap,
        research_reliability_min=settings.memory_research_reliability,
    )
    story_design = StoryDesignService(
        store=repository,
        gateway=gateway,
    )
    service = NovelAgentService(
        repository=repository,
        gateway=gateway,
        search=search,
        embedding=embedding,
        max_revision_attempts=settings.max_revision_attempts,
        semantic_retrieval_limit=settings.semantic_retrieval_limit,
        story_skills=story_skills,
        writing_skills=writing_skills,
        memory_manager=memory_manager,
        story_design=story_design,
    )
    projects = ProjectService(
        store=repository,
        detail_reader=AggregatingProjectDetailReader(
            repository,
            story_skills,
            writing_skills,
        ),
        recover_handler=service.recover_known_issue,
    )
    service.projects = projects
    return AppContext(
        settings,
        service,
        repository,
        root / "apps" / "web" / "dist",
        analytics=analytics_service,
        projects=projects,
        story_design=story_design,
        opening_repair=OpeningRepairService(repository, repository.opening_repair),
        llm_settings=llm_settings,
    )
