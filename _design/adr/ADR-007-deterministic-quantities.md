# ADR-007: Integer basis points and content-derived IDs

**Status:** Accepted, 2026-10-20

Represent contract weights with integers and use integer basis points for ratios. Hash canonical UTF-8 JSON with sorted keys and compact separators; derive event IDs from content and position without a clock or random source. Golden vectors run in the Python CI matrix on macOS, Linux, and Windows.
