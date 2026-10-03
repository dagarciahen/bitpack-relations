# bitpack-relations
This is a personal tool I built in 2024 while working at a railway company, to solve a problem I hit in my own daily work. The tool reads a small text file describing a set of stations, plus a few DBF tables that describe the entities present in each station, such as points (switches) and signals, and writes the TX, VALTX,
RX and VALRX relations. These tables are necessary for thesignalling system to exchange field data.

The project file is a plain text file with a `.ns` extension. It holds `key = value` lines rather than a binary format, so it opens
in any editor. It works at two levels: the main file states how many stations there are (`NSTAZIONILINEA`) and points at the
project file of each one (`STAZ1`, `STAZ2`), and every station file in turn gives its own `IDSTAZIONE` and the path to its
`TABLE_OF_ENTITIES.DBF` catalog. The tool follows that chain to know which
catalogs to read before generating anything.

## What the DBF tables contain

| Table | Contents |
|---|---|
| `TABLE_OF_ENTITIES.DBF` | Every entity of a station, with its type and id. |
| `TABLE_OF_SIGNALS.DBF` | The fields that each signal can expose. |
| `TABLE_OF_ENTITY_TYPES.DBF` | The entity types, used to group entities. |
| `TABLE_OF_SIGNAL_STATES.DBF` | The states of each signal, such as open or closed. |
| `MAPPING.DBF` | The template that maps an entity field to a relation. |

## Example rows

The rows below are illustrative. They follow the real column
layout, but the values are invented for obvious reasons.

**Entity types** - groups the entities of a station

```
type_code  type_name   description
1          $POINT      point machine
2          $SIGNAL     signal
3          $TRACK      track section
```

**Signal catalogue** - the fields a signal can expose

```
type_code  signal_prog  signal_code   description    initial  bits
2          1            SSIGSTACOM    command state  1        2
2          2            SSIGPOSREQ    requested pos  1        3
2          3            SSIGOCCUP     occupancy      2        1
```

**Signal states** - the states of one field

```
type_code  signal_prog  state_code  state_name  value
2          1            1           idle        1
2          1            2           commanded   2
2          1            3           active      3
```

**Station entities**

```
type_code  device_code  device_name  description
1          PNT_201      PNT201       point machine
2          SIG_101      SIG101       main signal
2          SIG_102      SIG102       shunting signal
```

**Generated TX rows** - note the address of each field

```
index  byte  bit  width  station  group    device  signal
1      2     6    2      ST01     $SIGNAL  SIG101  SSIGSTACOM
1      2     3    3      ST01     $SIGNAL  SIG101  SSIGPOSREQ
1      2     2    1      ST01     $SIGNAL  SIG101  SSIGOCCUP
```

The first three fields share byte 2: the 2 bit field sits at bit
6, the 3 bit field at bit 3, and the 1 bit field at bit 2. That is
the packing in action.

## What it is for

The TX and VALTX tables describe what the system transmits, and
the RX and VALRX tables mirror them for what it receives. Each row
carries the byte and the bit where a value lives, so the field
equipment knows exactly where to read or write it.

## What it saves the signalling engineer

Doing this by hand means computing the byte and bit offset of
every field, for every entity of every station, and keeping all of
them consistent in a spreadsheet. A single added signal shifts the
layout of everything that follows it, so the work has to be redone
and rechecked from scratch.

The tool does that packing automatically: it lists the entities of
each station, assigns every field its width and address, and
flags the initial and default state of each signal. What used to
be hours of manual offset arithmetic becomes one run, which removes
the copying mistakes that are hardest to trace back later.
## How it works

```
  schema.json  +  project file  +  tables
                     |
                     v
                  pipeline
                     |
        +------------+------------+
        v            v            v
       TX         VALTX        RX / VALRX
        |
        v
   bit packing
```

1. The schema says which tables to read and how to name the
   columns.
2. The project file lists the stations.
3. Each station is crossed with a mapping template to build the
   TX rows.
4. Every TX row is expanded into all of its allowed states for
   VALTX.
5. RX and VALRX mirror TX and VALTX with the declared renames
   applied.

## Bit packing

Each field takes `NBIT` bits. Fields are packed one after another
starting at a reserved byte offset, filling each byte from the top
bit downwards. A field that does not fit in the bits left of the
current byte moves to the top of the next byte. The layout is
capped, and going past the cap starts a new exchange index.

```
widths 3, 3, 4
  byte 2   XXX-----   field 1
  byte 2   ---XXX--   field 2
  byte 3   XXXX----   field 3
```

That map is what the field equipment needs: `OFF_BYTE` and
`OFF_BIT` give the exact bit address of every value.

## Install

```bash
python -m pip install -r requirements.txt
```

## Usage

Copy the example schema and adapt it:

```bash
cp config/schema.example.json config/schema.json
```

List the stations first:

```bash
python -m bitpack_relations.cli --project main.ns --inspect
```

Generate the tables:

```bash
python -m bitpack_relations.cli --project main.ns --index 1
```

Draw a packing layout while tuning the schema:

```bash
python -m bitpack_relations.diagram 3 3 4 2 8
```

## Schema

`config/schema.example.json` has six sections:

| Section | Purpose |
|---|---|
| `bitpacking` | byte offsets, bit order, index start, rollover |
| `columns` | logical role to physical column name |
| `project` | keys used to parse the project file |
| `tables` | input tables, format and encoding |
| `generation` | group order, prompt groups, renames |
| `outputs` | output names, directory and formats |

Because the column names live in `columns`, renaming a field or
switching convention is a config edit, not a code change.

## Layout

```
bitpack-relations/
|-- config/
|   `-- schema.example.json
|-- src/bitpack_relations/
|   |-- bitpack.py      packing engine
|   |-- config.py       schema loader
|   |-- tables.py       DBF and CSV input, DBF/CSV/pickle output
|   |-- nsproject.py    project file parser
|   |-- tx.py           TX rows and addresses
|   |-- valtx.py        state expansion
|   |-- rx.py           reception side renames
|   |-- pipeline.py     runs the whole chain
|   |-- cli.py          command line entry point
|   `-- diagram.py      layout preview
|-- tests/
|-- requirements.txt
`-- pyproject.toml
```

## Tests

```bash
python -m pytest
```
