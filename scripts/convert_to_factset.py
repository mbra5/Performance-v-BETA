#!/usr/bin/env python3
"""
Convert Bloomberg formulas to FactSet formulas in Performance vs. Beta xlsx.
Creates a versioned v2 file. Run from the project root directory.

Bloomberg formulas replaced:
  _xll.BDH(E6,E$1,$E$4,$E$5,"sort=d","Period","D") in D21  → D21 becomes date value, E21-E767 get FDS price
  _xll.BDH($E$6,"PX LAST",{date})  → _xll.FDS($E$7,"P_PRICE("&{date}&",0,D,D)")
  _xll.BDH($E$8,"PX LAST",{date})  → _xll.FDS($E$9,"P_PRICE("&{date}&",0,D,D)")
  E6 CELL("filename") formula       → =$E$3&" US Equity"
  E7 CELL("filename") formula       → =$E$3&"-US"
  E8 BDP formula                    → ="SPX Index"

New: E3 = ticker input cell (default "CRH"), D3 = label
"""

import zipfile
import re
import shutil
from pathlib import Path

BASE = Path(r"c:\Users\mbra\OneDrive - PointState Capital\Cowork (MB)\7. Visual Studio\Performance-v-BETA")
INPUT  = BASE / "xls" / "Performance vs. Beta Over Time_Coverage_v1.xlsx"
OUTPUT = BASE / "xls" / "Performance vs. Beta Over Time_Coverage_v2.xlsx"

SHEET_KEY   = "xl/worksheets/sheet2.xml"   # CRH sheet
CALC_CHAIN  = "xl/calcChain.xml"


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def convert():
    print(f"Reading: {INPUT.name}")

    # Load all files from the xlsx zip
    with zipfile.ZipFile(INPUT, "r") as zin:
        file_names = zin.namelist()
        files = {name: zin.read(name) for name in file_names}

    # Transform the CRH sheet
    xml = files[SHEET_KEY].decode("utf-8")
    xml, stats = transform_sheet(xml)
    files[SHEET_KEY] = xml.encode("utf-8")

    # Remove calcChain.xml — Excel rebuilds it on open
    files.pop(CALC_CHAIN, None)

    # Write output xlsx
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for name, data in files.items():
            zout.writestr(name, data)

    print(f"Saved:   {OUTPUT.name}")
    print()
    print("=== Conversion summary ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")


# ---------------------------------------------------------------------------
# Sheet transformation
# ---------------------------------------------------------------------------

def transform_sheet(xml: str):
    stats = {}

    # 1. Add D3 label + E3 ticker input (default = "CRH")
    xml = add_ticker_cells(xml)
    stats["E3 ticker input added"] = "CRH US Equity -> type new base symbol in E3"

    # 2. Replace E6 (Bloomberg stock ticker) → dynamic reference to E3
    xml, n = replace_cell_formula(
        xml,
        cell_ref="E6",
        old_formula=(
            'RIGHT(CELL("filename", A1), LEN(CELL("filename", A1)) - FIND("]", CELL("filename", A1)))&amp;" US Equity"'
        ),
        new_formula='=$E$3&amp;" US Equity"',
    )
    stats["E6 Bloomberg ticker formula"] = "replaced" if n else "NOT FOUND — check manually"

    # 3. Replace E7 (FactSet stock ticker) → dynamic reference to E3
    xml, n = replace_cell_formula(
        xml,
        cell_ref="E7",
        old_formula=(
            'RIGHT(CELL("filename", A1), LEN(CELL("filename", A1)) - FIND("]", CELL("filename", A1)))&amp;"-US"'
        ),
        new_formula='=$E$3&amp;"-US"',
    )
    stats["E7 FactSet ticker formula"] = "replaced" if n else "NOT FOUND — check manually"

    # 4. Replace E8 (BDP index lookup) → hardcoded "SPX Index"
    xml, n = replace_cell_formula(
        xml,
        cell_ref="E8",
        old_formula='_xll.BDP($E$6,"BETA_OVERRIDE_REL_INDEX")',
        new_formula='="SPX Index"',
    )
    stats["E8 BDP index formula"] = "replaced" if n else "NOT FOUND — check manually"

    # 5. Replace D21 bulk BDH (date+price pull) → plain cached value (remove formula)
    #    The Bloomberg array formula D21:E767 is replaced: D column keeps cached dates,
    #    E column cells get individual FDS price formulas (handled in step 6).
    xml = replace_d21_bulk_bdh(xml)
    stats["D21 bulk BDH array formula"] = "removed (cached dates preserved)"

    # 6. Replace E21:E767 spill cells → individual FDS price formulas
    xml, n = replace_price_column_e(xml)
    stats["E column price cells (FDS)"] = f"{n} cells updated"

    # 7. Replace individual stock BDH (columns S-W) → FDS
    xml, n_stock = re.subn(
        r'_xll\.BDH\(\$E\$6,"PX LAST",([A-Z\$]+\d+)\)',
        r'_xll.FDS($E$7,"P_PRICE("&amp;\1&amp;",0,D,D)")',
        xml,
    )
    stats["BDH stock price -> FDS (S-W cols)"] = f"{n_stock} formulas"

    # 8. Replace individual index BDH (columns AB-AF) -> FDS
    xml, n_index = re.subn(
        r'_xll\.BDH\(\$E\$8,"PX LAST",([A-Z\$]+\d+)\)',
        r'_xll.FDS($E$9,"P_PRICE("&amp;\1&amp;",0,D,D)")',
        xml,
    )
    stats["BDH index price -> FDS (AB-AF cols)"] = f"{n_index} formulas"

    # Sanity check
    bdh_remaining = xml.count("_xll.BDH")
    fds_total = xml.count("_xll.FDS")
    stats["Bloomberg BDH remaining"] = bdh_remaining
    stats["FactSet FDS total"] = fds_total

    return xml, stats


# ---------------------------------------------------------------------------
# Helper: Replace a specific cell's formula
# ---------------------------------------------------------------------------

def replace_cell_formula(xml: str, cell_ref: str, old_formula: str, new_formula: str):
    """Find <c r="{cell_ref}" ...><f ...>old_formula</f>... and replace formula text.
    Returns (modified_xml, count_replaced).
    """
    # Match the full cell element, capture everything up to and including <f...>
    # then the formula text, then </f>
    pattern = (
        r'(<c r="' + re.escape(cell_ref) + r'"[^>]*>)'
        r'(<f[^>]*>)'
        + re.escape(old_formula)
        + r'(</f>)'
    )

    def repl(m):
        cell_open = m.group(1)
        # Strip array-formula attributes — new formula is a simple formula
        simple_f = "<f>"
        return cell_open + simple_f + new_formula + m.group(3)

    new_xml, count = re.subn(pattern, repl, xml)
    return new_xml, count


# ---------------------------------------------------------------------------
# Helper: Remove D21 bulk BDH, preserve cached date value
# ---------------------------------------------------------------------------

def replace_d21_bulk_bdh(xml: str) -> str:
    """Remove the Bloomberg array formula from D21 (ref D21:E767).
    The cached date value stays so the date column remains intact.
    D22:D767 spill cells already have cached dates — they are unchanged.
    """
    pattern = (
        r'<c r="D21"([^>]*)>'
        r'<f t="array" aca="1" ref="D21:E767" ca="1">'
        r'_xll\.BDH\(E6,E\$1, \$E\$4,\$E\$5,"sort=d","Period", "D"\)'
        r'</f>'
        r'(<v>[^<]*</v>)'
        r'</c>'
    )

    def repl(m):
        # Keep the style attribute and cached value, remove the formula
        attrs = m.group(1)
        value = m.group(2)
        # Remove cm="1" attribute (formula group marker) since formula is gone
        attrs = re.sub(r'\s*cm="1"', "", attrs)
        return f'<c r="D21"{attrs}>{value}</c>'

    new_xml = re.sub(pattern, repl, xml)
    if new_xml == xml:
        print("  WARNING: D21 bulk BDH pattern not matched — check manually")
    return new_xml


# ---------------------------------------------------------------------------
# Helper: Replace E21:E767 empty-formula cells with FDS price formulas
# ---------------------------------------------------------------------------

def replace_price_column_e(xml: str):
    """Replace <c r="E{N}" ...><f ca="1"/><v>...</v></c>  (Bloomberg spill cells)
    with proper FactSet FDS price formulas referencing D{N} for the date.
    """
    count = 0

    def repl(m):
        nonlocal count
        row = m.group(1)
        style_attrs = m.group(2)   # e.g. s="28"
        cached_val = m.group(3)    # existing cached price value

        fds_formula = f'_xll.FDS($E$7,"P_PRICE("&amp;D{row}&amp;",0,D,D)")'
        count += 1
        return (
            f'<c r="E{row}"{style_attrs} cm="1">'
            f'<f t="array" aca="1" ref="E{row}" ca="1">{fds_formula}</f>'
            f'<v>{cached_val}</v></c>'
        )

    # Match pattern: <c r="E{digits}" style_attrs><f ca="1"/><v>value</v></c>
    # Only for rows >= 21 (data rows, not header/settings rows)
    pattern = r'<c r="E(\d{2,})"( [^>]*)><f ca="1"/><v>([^<]*)</v></c>'
    new_xml = re.sub(pattern, lambda m: repl(m) if int(m.group(1)) >= 21 else m.group(0), xml)

    return new_xml, count


# ---------------------------------------------------------------------------
# Helper: Add D3 (label) and E3 (ticker input) cells to row 3
# ---------------------------------------------------------------------------

def add_ticker_cells(xml: str) -> str:
    label_cell = '<c r="D3" t="inlineStr"><is><t>Ticker (base symbol):</t></is></c>'
    value_cell = '<c r="E3" t="inlineStr"><is><t>CRH</t></is></c>'
    new_cells  = label_cell + value_cell

    # Try to insert into existing row 3
    row3 = re.search(r'(<row r="3"[^>]*>)(.*?)(</row>)', xml, re.DOTALL)
    if row3:
        inner = row3.group(2)
        if 'r="E3"' not in inner:
            # Insert at the start of the row (D and E columns come early)
            xml = xml[:row3.start(2)] + new_cells + xml[row3.start(2):]
        return xml

    # Row 3 doesn't exist — insert a new row before row 4
    row4_pos = xml.find('<row r="4"')
    if row4_pos != -1:
        new_row = f'<row r="3">{new_cells}</row>'
        xml = xml[:row4_pos] + new_row + xml[row4_pos:]
    else:
        print("  WARNING: Could not find row 3 or row 4 to insert ticker cell")

    return xml


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    convert()
