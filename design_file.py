"""Read and validate portable Beam Designer files."""
import json
import math
from pathlib import Path


def validate_design(data, sections):
    if not isinstance(data, dict) or data.get("version") != 1 or isinstance(data.get("version"), bool):
        raise ValueError("This is not a supported Beam Designer file (version 1 required).")
    def number(value, label, minimum, maximum=None):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{label} must be a finite number.")
        if value < minimum or (maximum is not None and value > maximum):
            raise ValueError(f"{label} is outside the supported range.")
        return value
    support = data.get("support")
    if support not in ("Simply supported", "Cantilever"):
        raise ValueError("Unknown support type.")
    section = data.get("section")
    if not isinstance(section, str) or section not in sections:
        raise ValueError("Unknown section.")
    span = number(data.get("span_ft"), "Span", 0, 100)
    divisor = number(data.get("deflection_divisor"), "Deflection divisor", 0)
    if divisor == 0:
        raise ValueError("Deflection divisor must be positive.")
    allowable = data.get("allowable_stress_ksi")
    if allowable is not None:
        allowable = number(allowable, "Allowable stress", 0)
        if allowable == 0:
            raise ValueError("Allowable stress must be positive.")
    points, uniforms = data.get("point_loads"), data.get("uniform_loads")
    if not isinstance(points, list) or not isinstance(uniforms, list):
        raise ValueError("Point and uniform loads must be lists.")
    def load_list(items, kind):
        result = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"Each {kind} load must be an object.")
            if kind == "point":
                result.append([number(item.get("magnitude_kip"), "Point load", -20, 20),
                               number(item.get("position_ft"), "Point position", 0, span)])
            else:
                magnitude = number(item.get("magnitude_kip_per_ft"), "Uniform load", -5, 5)
                start = number(item.get("start_ft"), "Uniform start", 0, span)
                end = number(item.get("end_ft"), "Uniform end", 0, span)
                if start > end:
                    raise ValueError("Uniform load start must not exceed its end.")
                result.append([magnitude, start, end])
        return result
    return dict(version=1, support=support, span_ft=span, section=section,
                deflection_divisor=divisor, allowable_stress_ksi=allowable,
                point_loads=load_list(points, "point"), uniform_loads=load_list(uniforms, "uniform"))


def read_design(path, sections):
    with Path(path).open("r", encoding="utf-8") as stream:
        return validate_design(json.load(stream), sections)


def write_design(path, data, sections):
    # Validate before opening the destination so invalid inputs cannot truncate it.
    normalized = validate_design(data, sections)
    points = [dict(magnitude_kip=p, position_ft=x) for p, x in normalized["point_loads"]]
    uniforms = [dict(magnitude_kip_per_ft=w, start_ft=a, end_ft=b) for w, a, b in normalized["uniform_loads"]]
    normalized.update(point_loads=points, uniform_loads=uniforms)
    import os
    import tempfile
    target = Path(path)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                         prefix=".beam-", suffix=".tmp", delete=False) as stream:
            temp_name = stream.name
            json.dump(normalized, stream, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temp_name, target)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
