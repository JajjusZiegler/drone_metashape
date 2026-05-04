import builtins
from pathlib import Path

import numpy as np

from ret_micasense_pos_exiftool import parse_mrk


def test_parse_mrk_quality_check(tmp_path: Path):
    mrk = tmp_path / "test.MRK"
    # Two lines, one good 50,Q and one bad 1,Q
    mrk.write_text(
        "0 100 [1] 0 0 0 47.0, 8.0, 500.0 50,Q\n"
        "0 200 [1] 0 0 0 47.1, 8.1, 501.0 1,Q\n"
    )
    ts, pos, ok = parse_mrk(tmp_path)
    assert len(ts) == 2
    assert len(pos) == 2
    assert ok is False


def test_parse_mrk_all_good(tmp_path: Path):
    mrk = tmp_path / "test.MRK"
    mrk.write_text(
        "0 100 [1] 0 0 0 47.0, 8.0, 500.0 50,Q\n"
        "0 200 [1] 0 0 0 47.1, 8.1, 501.0 50,Q\n"
    )
    ts, pos, ok = parse_mrk(tmp_path)
    assert len(ts) == 2
    assert len(pos) == 2
    assert ok is True
