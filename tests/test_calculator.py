import datetime
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.calculator_prescription import calculate_prescription


def test_calculate_prescription(tmp_path):
    settings_path = tmp_path / 'settings.yaml'
    settings_path.write_text(
        'infraction_delays:\n  delit: 6\nrecidive_multiplier: 2\nnear_threshold_days: 30\n'
    )
    date_faits = datetime.date(2020, 1, 1)
    dernier_acte = datetime.date(2022, 1, 1)
    result = calculate_prescription(date_faits, dernier_acte, 'delit', False, str(settings_path))
    assert result.date_limite.year == 2028
    assert result.couleur in {'green', 'orange', 'red'}
