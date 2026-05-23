"""Tests unitarios — US-1B-03-01 Channel estados operacionales.

Verifican el modelo Channel + ChannelStateHistory sin tocar la BD.
"""

from __future__ import annotations

import pytest
from sqlalchemy import CheckConstraint, Index

pytestmark = pytest.mark.unit


def test_channel_state_check_constraint() -> None:
    """El CHECK constraint ck_channels_state debe estar en Channel.__table_args__."""
    from app.db.models.channels import Channel

    check_names = [arg.name for arg in Channel.__table_args__ if isinstance(arg, CheckConstraint)]
    assert "ck_channels_state" in check_names, (
        "Channel.__table_args__ debe contener CheckConstraint(name='ck_channels_state')"
    )


def test_channel_states_constant() -> None:
    """CHANNEL_STATES debe tener exactamente 6 valores."""
    from app.db.models.channels import CHANNEL_STATES

    assert len(CHANNEL_STATES) == 6, (
        f"Se esperaban 6 estados, se encontraron {len(CHANNEL_STATES)}: {CHANNEL_STATES}"
    )
    expected = {"inactive", "pre_launch", "pilot", "live", "paused", "deprecated"}
    assert set(CHANNEL_STATES) == expected, f"Estados inesperados: {set(CHANNEL_STATES) - expected}"


def test_channel_state_history_importable() -> None:
    """ChannelStateHistory debe ser importable desde app.db.models."""
    from app.db.models import ChannelStateHistory

    assert ChannelStateHistory.__tablename__ == "channel_state_history"


def test_channel_code_index_present() -> None:
    """Channel debe tener índice idx_channels_code en __table_args__."""
    from app.db.models.channels import Channel

    index_names = [arg.name for arg in Channel.__table_args__ if isinstance(arg, Index)]
    assert "idx_channels_code" in index_names
