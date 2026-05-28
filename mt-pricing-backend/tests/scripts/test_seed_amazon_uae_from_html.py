"""Test parsing of the Pricing Desk standalone HTML."""
from pathlib import Path

import pytest

from app.scripts.seed_amazon_uae_from_html import extract_data_array


HTML_SAMPLE = """<html><body><script>
const DATA = [{"s":"4222015","n":"VALVE","f":"LATON","pe":3.07,"v":41.82,"peso":0.21,"fba_env":1.5,"fba_alm":0.028,"fba_fee":7.2,"rec":"fba"},
{"s":"5120020","n":"JOINT","f":"MANGUITOS","pe":7.81,"v":77.97,"peso":0.7,"fba_env":1.8,"fba_alm":112.08,"fba_fee":8.5,"rec":"easyship"}];
const FAMS=[];
</script></body></html>"""


def test_extract_data_array_returns_list_of_dicts():
    rows = extract_data_array(HTML_SAMPLE)
    assert len(rows) == 2
    assert rows[0]["s"] == "4222015"
    assert rows[0]["pe"] == 3.07
    assert rows[0]["rec"] == "fba"


def test_extract_data_array_raises_when_const_missing():
    with pytest.raises(ValueError, match="DATA"):
        extract_data_array("<html>no script here</html>")
