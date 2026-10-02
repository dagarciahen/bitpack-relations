"""Tests for the TX, VALTX and RX generators."""

import json

import pandas as pd
import pytest

from bitpack_relations import rx, tx, valtx
from bitpack_relations.config import Schema

SCHEMA = {
    "schema_version": 1,
    "bitpacking": {"byte_start": 2, "byte_limit": 1024},
    "columns": {
        "index": "IND_TX",
        "offset_byte": "OFF_BYTE",
        "offset_bit": "OFF_BIT",
        "width_bits": "NBIT",
        "station_id": "IDSTAZ",
        "device_type": "TIPO_ENTE",
        "device_code": "ID_ENTE",
        "signal_code": "ID_CAMPO",
        "description": "DESCRIZION",
        "type_code": "ID_TIPOENT",
        "type_name": "NOME_SIMBO",
        "state_code": "PROG_STATO",
        "state_name": "NOME_SIMBO",
        "state_initial": "STATOINIZ",
        "signal_prog": "PROG_CAMPO",
        "value": "VALORE_TX",
        "state_label": "VAL_STATO",
        "safety": "SICURO",
        "default": "DEFAULT",
    },
    "project": {},
    "tables": {"device_types": {"path": "data/x.dbf"}},
    "generation": {
        "tx": {
            "group_order": ["$STATION", "$SIGNAL"],
            "prompt_groups": ["$SIGNAL"],
        },
        "rx": {
            "renames": [
                {"from": "DISC", "to": "DISCONN",
                 "description": "disconnection rx"}
            ]
        },
    },
    "outputs": {
        "tables": {
            "tx": "T_TX",
            "valtx": "T_VALTX",
            "rx": "T_RX",
            "valrx": "T_VALRX",
        }
    },
}


@pytest.fixture
def schema(tmp_path):
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(SCHEMA), encoding="utf-8")
    return Schema.load(path)


@pytest.fixture
def device_types():
    return pd.DataFrame(
        {"ID_TIPOENT": [1, 2], "NOME_SIMBO": ["$STATION", "$SIGNAL"]}
    )


@pytest.fixture
def catalog():
    return pd.DataFrame(
        {
            "ID_TIPOENT": [1, 2],
            "NOME_SIMBO": ["DEV_A", "SIG_A"],
        }
    )


@pytest.fixture
def mapping():
    return pd.DataFrame(
        {
            "ID_TIPOENT": [1, 2],
            "NOME_SIMBO": ["FIELD_X", "DISC"],
            "DESCRIZION": ["field x", "disconnect"],
        }
    )


def test_build_rows_crosses_catalog_and_mapping(
    schema, catalog, mapping, device_types
):
    rows = tx.build_rows(
        catalog, mapping, device_types, "ST01", schema, 1
    )

    assert len(rows) == 2
    assert {r["ID_CAMPO"] for r in rows} == {"FIELD_X", "DISC"}
    assert {r["TIPO_ENTE"] for r in rows} == {"$STATION", "$SIGNAL"}
    assert all(r["IDSTAZ"] == "ST01" for r in rows)


def test_sort_rows_uses_the_configured_group_order(
    schema, catalog, mapping, device_types
):
    rows = tx.build_rows(
        catalog, mapping, device_types, "ST01", schema, 1
    )
    ordered = tx.sort_rows(pd.DataFrame(rows), schema)

    assert list(ordered["TIPO_ENTE"]) == ["$STATION", "$SIGNAL"]


def test_assign_bitpack_writes_addresses(schema):
    frame = pd.DataFrame(
        {
            "ID_CAMPO": ["A", "B"],
            "NBIT": [3, 3],
            "OFF_BYTE": [0, 0],
            "OFF_BIT": [0, 0],
            "IND_TX": [0, 0],
        }
    )
    packed, _ = tx.assign_bitpack(frame, schema, 1)

    assert list(packed["OFF_BYTE"]) == [2, 2]
    assert list(packed["OFF_BIT"]) == [5, 2]
    assert list(packed["IND_TX"]) == [1, 1]


def test_apply_prompts_overrides_the_group_index(schema):
    frame = pd.DataFrame(
        {"TIPO_ENTE": ["$STATION", "$SIGNAL"], "IND_TX": [1, 1]}
    )
    asked = []

    def prompt(group):
        asked.append(group)
        return 42

    result = tx.apply_prompts(frame, schema, prompt, 1)

    assert asked == ["$SIGNAL"]
    assert list(result["IND_TX"]) == [1, 42]


def test_valtx_expands_each_signal_into_states(schema):
    tx_frame = pd.DataFrame(
        {
            "IND_TX": [1],
            "TIPO_ENTE": ["$SIGNAL"],
            "ID_CAMPO": ["SIG_A"],
            "IDSTAZ": ["ST01"],
            "DESCRIZION": ["signal"],
        }
    )
    catalog = pd.DataFrame(
        {
            "ID_TIPOENT": [2],
            "NOME_SIMBO": ["SIG_A"],
            "PROG_CAMPO": [10],
            "STATOINIZ": [1],
        }
    )
    states = pd.DataFrame(
        {
            "ID_TIPOENT": [2, 2],
            "NOME_SIMBO": ["off", "on"],
            "PROG_CAMPO": [10, 10],
            "PROG_STATO": [1, 2],
        }
    )

    result = valtx.build_rows(tx_frame, catalog, states, schema)

    assert len(result) == 2
    assert list(result["VALORE_TX"]) == ["0", "1"]
    assert list(result["SICURO"]) == [1, 0]
    assert list(result["DEFAULT"]) == [1, 0]


def test_rx_applies_the_declared_rename(schema):
    frame = pd.DataFrame(
        {"ID_CAMPO": ["DISC", "OTHER"], "DESCRIZION": ["a", "b"]}
    )
    result = rx.apply_renames(frame, schema)

    assert list(result["ID_CAMPO"]) == ["DISCONN", "OTHER"]
    assert result.loc[0, "DESCRIZION"] == "disconnection rx"


def test_rx_ignores_a_rename_that_does_not_match(schema):
    frame = pd.DataFrame({"ID_CAMPO": ["OTHER"]})
    result = rx.apply_renames(frame, schema)

    assert list(result["ID_CAMPO"]) == ["OTHER"]


def test_rx_requires_the_signal_column(schema):
    with pytest.raises(Exception):
        rx.apply_renames(pd.DataFrame({"NOPE": [1]}), schema)
