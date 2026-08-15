"""Evidence and fixity tests."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from spectra.evidence.service import EvidenceService, compute_file_hash
from spectra.models.evidence import EvidenceCreate, EvidenceSourceType


def test_compute_hash(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("spectra")
    h = compute_file_hash(f)
    assert len(h) == 64


def test_record_and_list(evidence_service: EvidenceService):
    cid = uuid4()
    ev = evidence_service.record(
        EvidenceCreate(
            case_id=cid,
            title="test observation",
            source_type=EvidenceSourceType.MANUAL,
            raw_excerpt="hello",
        )
    )
    assert ev.title == "test observation"
    items = evidence_service.list_for_case(cid)
    assert len(items) == 1
    assert items[0].id == ev.id


def test_path_traversal_rejected_in_create():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        EvidenceCreate(
            case_id=uuid4(),
            title="evil",
            artifact_path="../../etc/passwd",
        )
