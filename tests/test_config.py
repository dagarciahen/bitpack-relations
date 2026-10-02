"""Tests for schema loading and validation."""

import json

import pytest

from bitpack_relations.config import Schema, SchemaError

MINIMAL = {
    "schema_version": 1,
    "bitpacking": {"byte_start": 2},
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
        "value": "VALORE_TX",
        "state_label": "VAL_STATO",
    },
    "project": {},
    "tables": {"device_types": {"path": "data/x.dbf"}},
    "generation": {},
    "outputs": {
        "tables": {
            "tx": "T_TX",
            "valtx": "T_VALTX",
            "rx": "T_RX",
            "valrx": "T_VALRX",
        }
    },
}


def write(tmp_path, document, name="schema.json"):
    path = tmp_path / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_minimal_schema_loads(tmp_path):
    schema = Schema.load(write(tmp_path, MINIMAL))

    assert schema.column("index") == "IND_TX"
    assert schema.bitpack.byte_start == 2


def test_missing_section_is_reported(tmp_path):
    document = json.loads(json.dumps(MINIMAL))
    del document["outputs"]

    with pytest.raises(SchemaError, match="missing section"):
        Schema.load(write(tmp_path, document))


def test_missing_column_is_reported(tmp_path):
    document = json.loads(json.dumps(MINIMAL))
    del document["columns"]["signal_code"]

    with pytest.raises(SchemaError, match="column mapping is missing"):
        Schema.load(write(tmp_path, document))


def test_unknown_column_role_raises(tmp_path):
    schema = Schema.load(write(tmp_path, MINIMAL))

    with pytest.raises(SchemaError, match="unknown logical column"):
        schema.column("nope")


def test_invalid_json_is_reported(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{ not json", encoding="utf-8")

    with pytest.raises(SchemaError, match="not valid JSON"):
        Schema.load(path)


def test_missing_file_is_reported(tmp_path):
    with pytest.raises(SchemaError, match="schema not found"):
        Schema.load(tmp_path / "absent.json")


def test_output_path_uses_the_configured_directory(tmp_path):
    schema = Schema.load(write(tmp_path, MINIMAL))
    path = schema.output_path("tx", "csv", base=tmp_path)

    assert path.name == "T_TX.csv"
    assert path.parent.name == "out"


def test_table_path_is_relative_to_the_project_root(tmp_path):
    schema = Schema.load(write(tmp_path, MINIMAL))
    path = schema.table_path("device_types", base=tmp_path)

    assert path.parent.name == "data"


def test_group_order_defaults_to_empty(tmp_path):
    schema = Schema.load(write(tmp_path, MINIMAL))

    assert schema.group_order("tx") == []
    assert schema.prompt_groups("tx") == []
