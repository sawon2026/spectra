"""Task classification — provider-agnostic interface with deterministic implementation."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from spectra.intelligence.task import (
    ArtifactType,
    Task,
    TaskCreate,
    TaskType,
)


class TaskClassifier(ABC):
    """Convert natural-language (or structured) input into a Task."""

    @abstractmethod
    def classify(self, data: TaskCreate) -> Task:
        ...


class DeterministicClassifier(TaskClassifier):
    """Rule-based classifier for offline tests and fallback.

    Does not call any LLM. Patterns are intentionally simple and explicit.
    """

    _RULES: list[tuple[TaskType, ArtifactType, list[str], list[str], str]] = [
        (
            TaskType.ANDROID,
            ArtifactType.APK,
            [r"\bapk\b", r"android", r"jadx", r"manifest", r"smali"],
            ["file-info", "hash-compute"],
            "low",
        ),
        (
            TaskType.BINARY,
            ArtifactType.BINARY,
            [r"\bbinary\b", r"\belf\b", r"\bpe\b", r"disassembl", r"\bida\b", r"ghidra", r"radare"],
            ["file-info", "hash-compute", "strings-extract"],
            "low",
        ),
        (
            TaskType.MALWARE,
            ArtifactType.FILE,
            [r"malware", r"yara", r"ransomware", r"sample"],
            ["file-info", "hash-compute"],
            "medium",
        ),
        (
            TaskType.WEB_API,
            ArtifactType.URL,
            [r"\bapi\b", r"graphql", r"endpoint", r"http", r"web.?secur"],
            ["file-info"],
            "medium",
        ),
        (
            TaskType.CODE_SECURITY,
            ArtifactType.SOURCE,
            [r"sast", r"semgrep", r"code.?audit", r"source.?review"],
            ["file-info"],
            "low",
        ),
        (
            TaskType.NETWORK,
            ArtifactType.PCAP,
            [r"pcap", r"wireshark", r"network.?captur", r"traffic"],
            ["file-info"],
            "low",
        ),
        (
            TaskType.REVERSE_ENGINEERING,
            ArtifactType.FILE,
            [r"reverse", r"decompile", r"strings", r"analyze"],
            ["file-info", "hash-compute", "strings-extract"],
            "low",
        ),
    ]

    def classify(self, data: TaskCreate) -> Task:
        text = data.text.lower()
        task_type = TaskType.GENERAL
        artifact_type = ArtifactType.UNKNOWN
        capabilities: list[str] = ["file-info", "hash-compute"]
        risk = "low"
        confidence = 0.4
        objectives: list[str] = []

        for ttype, atype, patterns, caps, risk_level in self._RULES:
            if any(re.search(p, text, re.I) for p in patterns):
                task_type = ttype
                artifact_type = atype
                capabilities = list(caps)
                risk = risk_level
                confidence = 0.85
                break

        for path in data.artifact_paths:
            lower = path.lower()
            if lower.endswith(".apk"):
                artifact_type = ArtifactType.APK
                task_type = TaskType.ANDROID if task_type == TaskType.GENERAL else task_type
            elif lower.endswith((".exe", ".dll", ".so", ".elf", ".bin")):
                artifact_type = ArtifactType.BINARY
            elif lower.endswith((".pcap", ".pcapng")):
                artifact_type = ArtifactType.PCAP

        if "hash" in text or "checksum" in text:
            objectives.append("compute_hashes")
            if "hash-compute" not in capabilities:
                capabilities.append("hash-compute")
        if "string" in text:
            objectives.append("extract_strings")
            if "strings-extract" not in capabilities:
                capabilities.append("strings-extract")
        if "type" in text or "identify" in text or "file info" in text or "metadata" in text:
            objectives.append("identify_file")
        if not objectives:
            objectives.append("inspect_artifact")

        network_required = bool(re.search(r"\b(scan|fetch|download|remote|http)\b", text, re.I))

        return Task(
            case_id=data.case_id,
            text=data.text,
            task_type=task_type,
            artifact_type=artifact_type,
            objectives=objectives,
            requested_capabilities=capabilities,
            risk_level=risk,
            scope_required=True,
            authorization_required=True,
            network_required=network_required,
            confidence=confidence,
            metadata={"classifier": "deterministic", **data.metadata},
        )
