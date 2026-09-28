/// Parsing helpers for timestamps coming from the backend.
///
/// The API emits offset-bearing ISO strings (e.g. `2026-09-13T15:39:30+05:30`).
/// Dart's [DateTime.parse] converts any offset-bearing string to UTC and sets
/// `isUtc = true`; formatting that value directly then renders UTC, showing a
/// time several hours off from the wall clock the record was actually created
/// at. Everything the user sees must therefore go through [toLocal].
library;

DateTime? parseServerTime(dynamic value) {
  if (value == null) return null;
  if (value is DateTime) return value.toLocal();
  final parsed = DateTime.tryParse(value.toString());
  return parsed?.toLocal();
}

/// Same as [parseServerTime] but never null — falls back to "now" for fields
/// the API declares non-nullable.
DateTime parseServerTimeOr(dynamic value, [DateTime? fallback]) =>
    parseServerTime(value) ?? (fallback ?? DateTime.now());
