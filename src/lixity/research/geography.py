"""Read-time descriptions of authored geography, independent of stored encodings."""

import math
from typing import Any

from .models import (
    GeographicFeatureCollection,
    GeographicLineString,
    GeographicPoint,
    GeographicPolygon,
)

EARTH_RADIUS_KM = 6371.0088


def _segment_km(start: list[float], end: list[float]) -> float:
    """Measure the shortest spherical segment; altitude and routing are unknown."""
    if start[1] == end[1] and abs(start[1]) == 90:
        return 0.0  # All longitudes identify the same point at each pole.
    longitude_delta = math.radians((end[0] - start[0] + 180) % 360 - 180)
    latitude_delta = math.radians(end[1] - start[1])
    latitude_start, latitude_end = math.radians(start[1]), math.radians(end[1])
    haversine = (math.sin(latitude_delta / 2) ** 2
                 + math.cos(latitude_start) * math.cos(latitude_end) * math.sin(longitude_delta / 2) ** 2)
    # Rounding around antipodes must not put asin outside its defined interval.
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, max(0.0, haversine))))


def summarize_geography(value: GeographicFeatureCollection | None) -> dict[str, Any] | None:
    """Describe the selected revision without inferring places, chronology or roads.

    Distances sum the shortest great-circle segment between each pair of route
    vertices on a sphere. Positions include repeated vertices and closed rings;
    their count does not represent distinct places. Polygon areas are not measured.
    """
    if value is None:
        return None
    counts = {"Point": 0, "LineString": 0, "Polygon": 0, "unknown": 0}
    features: list[dict[str, Any]] = []
    route_lengths: list[float] = []
    for index, feature in enumerate(value.features):
        geometry = feature.geometry
        geometry_type = geometry.type if geometry else "unknown"
        counts[geometry_type] += 1
        position_count = 0
        segment_count = None
        route_length = None
        if isinstance(geometry, GeographicPoint):
            position_count = 1
        elif isinstance(geometry, GeographicLineString):
            position_count = len(geometry.coordinates)
            segment_count = position_count - 1
            route_length = math.fsum(_segment_km(start, end)
                for start, end in zip(geometry.coordinates, geometry.coordinates[1:], strict=False))
            route_lengths.append(route_length)
        elif isinstance(geometry, GeographicPolygon):
            position_count = sum(len(ring) for ring in geometry.coordinates)
        features.append({
            "index": index, "geometry_type": geometry_type, "position_count": position_count,
            "segment_count": segment_count, "named_waypoint_count": len(feature.properties.waypoint_labels),
            "route_length_km": route_length, **feature.properties.model_dump(mode="json", exclude={"description"}),
        })
    return {
        "schema_version": "research-geography-summary-local/1",
        "feature_count": len(features), "located_feature_count": len(features) - counts["unknown"],
        "unlocated_feature_count": counts["unknown"], "geometry_counts": counts,
        "route_length_km": math.fsum(route_lengths) if route_lengths else None,
        "features": features, "distance_method": "haversine_sphere", "earth_radius_km": EARTH_RADIUS_KM,
        "limitations": ["authored_coordinates", "shortest_great_circle_segments", "not_road_routing",
                        "not_travel_time", "not_historical_verification", "no_elevation"],
    }
