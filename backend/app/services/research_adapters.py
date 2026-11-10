"""Optional typed integration seams; INT24 never imports unfinished branches."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ResearchCitation:
    title: str
    canonical_url: str
    excerpt: str


@dataclass(frozen=True)
class ResearchBrief:
    student_id: str
    question: str
    language: str
    citations: tuple[ResearchCitation, ...]


@runtime_checkable
class TeachingIntelligenceAdapter(Protocol):
    def lesson_plan(self, brief: ResearchBrief) -> dict: ...


@runtime_checkable
class PersonalAssistantAdapter(Protocol):
    def prepare_follow_up(self, brief: ResearchBrief, task_type: str) -> dict: ...


@runtime_checkable
class CareerRoadmapAdapter(Protocol):
    def relate_to_goal(self, brief: ResearchBrief, goal_key: str) -> dict: ...


@runtime_checkable
class StudentCommandCenterAdapter(Protocol):
    def publish_research_reference(self, brief: ResearchBrief) -> str: ...


@runtime_checkable
class KnowledgeStudioAdapter(Protocol):
    def connect_public_sources(self, brief: ResearchBrief) -> dict: ...


@dataclass(frozen=True)
class OptionalResearchAdapters:
    teaching: TeachingIntelligenceAdapter | None = None  # INT16
    assistant: PersonalAssistantAdapter | None = None  # INT17
    career: CareerRoadmapAdapter | None = None  # INT21
    command_center: StudentCommandCenterAdapter | None = None  # INT22
    knowledge: KnowledgeStudioAdapter | None = None  # INT23
