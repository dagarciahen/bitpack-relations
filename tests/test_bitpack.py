"""Tests for the bit packing engine."""

import pytest

from bitpack_relations.bitpack import (
    BitPackConfig,
    BitPackError,
    pack,
    render,
)


def test_first_field_starts_at_the_reserved_offset():
    placements = pack([1], BitPackConfig())

    assert placements[0].byte == 2
    assert placements[0].bit == 7


def test_fields_share_a_byte_when_they_fit():
    placements = pack([3, 3, 4], BitPackConfig())

    assert [p.byte for p in placements] == [2, 2, 3]
    assert [(p.bit, p.width) for p in placements] == [
        (5, 3),
        (2, 3),
        (4, 4),
    ]


def test_field_moves_to_the_next_byte_when_it_does_not_fit():
    placements = pack([6, 4, 8], BitPackConfig())

    assert [p.byte for p in placements] == [2, 3, 4]
    assert [p.bit for p in placements] == [2, 4, 0]


def test_masks_show_the_occupied_bits():
    placements = pack([3, 3, 4], BitPackConfig())
    masks = [p.mask() for p in placements]

    assert masks == ["XXX-----", "---XXX--", "XXXX----"]


def test_index_is_carried_on_every_placement():
    placements = pack([2] * 4, BitPackConfig(index_start=7))

    assert {p.index for p in placements} == {7}


def test_index_advances_once_the_byte_limit_is_crossed():
    cfg = BitPackConfig(byte_start=2, byte_limit=3)
    placements = pack([8] * 5, cfg)

    assert [p.index for p in placements] == [1, 1, 2, 2, 2]


def test_rollover_restart_starts_the_buffer_again():
    cfg = BitPackConfig(byte_limit=3, rollover="restart")
    placements = pack([8] * 4, cfg)

    assert placements[2].byte == 2
    assert placements[2].index == 2


def test_rollover_reject_raises():
    cfg = BitPackConfig(byte_limit=2, rollover="reject")

    with pytest.raises(BitPackError):
        pack([8] * 3, cfg)


def test_width_larger_than_a_byte_is_rejected():
    with pytest.raises(BitPackError):
        pack([9], BitPackConfig())


def test_negative_width_is_rejected():
    with pytest.raises(BitPackError):
        pack([-1], BitPackConfig())


def test_custom_geometry_is_honoured():
    cfg = BitPackConfig(bits_per_byte=16, byte_start=0, byte_limit=8)
    placements = pack([10, 10], cfg)

    assert placements[0].byte == 0
    assert placements[0].bit == 6
    assert placements[1].byte == 1


def test_render_lists_one_line_per_field():
    lines = render([3, 3], BitPackConfig()).splitlines()

    assert len(lines) == 2
    assert "XXX-----" in lines[0]


def test_config_from_dict_ignores_unknown_keys():
    cfg = BitPackConfig.from_dict(
        {"byte_start": 4, "not_a_setting": True}
    )

    assert cfg.byte_start == 4


def test_invalid_fill_order_is_rejected():
    with pytest.raises(BitPackError):
        BitPackConfig(fill_order="middle")
