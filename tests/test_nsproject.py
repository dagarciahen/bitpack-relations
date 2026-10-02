"""Tests for the project file parser."""

import json

import pytest

from bitpack_relations.config import Schema
from bitpack_relations.nsproject import ProjectError, ProjectLayout

SCHEMA = {
    "schema_version": 1,
    "bitpacking": {},
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
    "project": {
        "station_count_key": "NSTAZIONILINEA",
        "station_key_template": "STAZ{n}",
        "station_id_key": "IDSTAZIONE",
        "catalog_dir": "DBI",
        "catalog_file_name": "ELENTI.DBF",
    },
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


@pytest.fixture
def schema(tmp_path):
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(SCHEMA), encoding="utf-8")
    return Schema.load(path)


def build_station(tmp_path, name, station_id="ST01", catalog=True):
    folder = tmp_path / name
    (folder / "DBI").mkdir(parents=True, exist_ok=True)
    project = folder / f"{name}.ns"
    project.write_text(
        f"IDSTAZIONE = {station_id}\n", encoding="utf-8"
    )
    if catalog:
        (folder / "DBI" / "ELENTI.DBF").write_bytes(b"")
    return project


def test_discovers_every_station(tmp_path, schema):
    first = build_station(tmp_path, "A", "ST01")
    second = build_station(tmp_path, "B", "ST02")

    project_file = tmp_path / "main.ns"
    project_file.write_text(
        "NSTAZIONILINEA=2\n"
        f"STAZ1={first}\n"
        f"STAZ2={second}\n",
        encoding="utf-8",
    )

    layout = ProjectLayout.discover(project_file, schema)

    assert len(layout) == 2
    assert [s.station_id for s in layout] == ["ST01", "ST02"]
    assert all(s.ready for s in layout)


def test_station_without_catalog_is_incomplete(tmp_path, schema):
    station = build_station(tmp_path, "A", catalog=False)
    project_file = tmp_path / "main.ns"
    project_file.write_text(
        f"NSTAZIONILINEA=1\nSTAZ1={station}\n", encoding="utf-8"
    )

    layout = ProjectLayout.discover(project_file, schema)

    assert len(layout.ready) == 0
    assert layout.stations[0].catalog_path is None


def test_missing_count_key_is_reported(tmp_path, schema):
    project_file = tmp_path / "main.ns"
    project_file.write_text("STAZ1=whatever.ns\n", encoding="utf-8")

    with pytest.raises(ProjectError, match="not found"):
        ProjectLayout.discover(project_file, schema)


def test_non_numeric_count_is_reported(tmp_path, schema):
    project_file = tmp_path / "main.ns"
    project_file.write_text(
        "NSTAZIONILINEA=many\n", encoding="utf-8"
    )

    with pytest.raises(ProjectError, match="not a number"):
        ProjectLayout.discover(project_file, schema)


def test_missing_project_file_is_reported(tmp_path, schema):
    with pytest.raises(ProjectError, match="not found"):
        ProjectLayout.discover(tmp_path / "absent.ns", schema)


def test_as_dict_serialises_the_layout(tmp_path, schema):
    station = build_station(tmp_path, "A", "ST01")
    project_file = tmp_path / "main.ns"
    project_file.write_text(
        f"NSTAZIONILINEA=1\nSTAZ1={station}\n", encoding="utf-8"
    )

    layout = ProjectLayout.discover(project_file, schema)
    payload = layout.as_dict()

    assert payload["STAZ1"]["STATION_ID"] == "ST01"
    assert payload["STAZ1"]["CATALOG_PATH"].endswith("ELENTI.DBF")
