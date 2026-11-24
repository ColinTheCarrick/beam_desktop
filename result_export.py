"""Export the sampled beam diagrams as an Excel-compatible CSV."""
import csv
import os
from pathlib import Path
import tempfile


def export_results(path, result):
    columns = [result[key] for key in ("xs", "shear", "moment", "deflection")]
    if not columns[0] or any(len(column) != len(columns[0]) for column in columns):
        raise ValueError("The analysis results are incomplete.")
    target = Path(path)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="",
                                         dir=target.parent, prefix=".beam-results-",
                                         suffix=".tmp", delete=False) as stream:
            temp_name = stream.name
            writer = csv.writer(stream)
            writer.writerow(["x (ft)", "V (kip, positive upward)",
                             "M (kip-ft, positive sagging)",
                             "Deflection (in, positive downward)"])
            writer.writerows(zip(*columns))
        os.replace(temp_name, target)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
