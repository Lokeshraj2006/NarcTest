/// Tiny fuzzy matcher used by the field extractor.
///
/// Provides approximate string matching so that OCR variations like
/// "Nett Wt.", "NetWt", "Net-Weight" are all treated as the same keyword.
///
/// This is intentionally simple: Levenshtein distance with a small
/// threshold. It does not replace regex; it helps regex find keywords
/// that OCR slightly misread.
///
/// Ported from the legal_metrology_compliance_scanner prototype.
library;

class FuzzyMatch {
  FuzzyMatch._();

  /// Returns true if [candidate] is within [maxDistance] edits of [target].
  static bool close(
    String candidate,
    String target, {
    int maxDistance = 1,
  }) {
    return distance(candidate.toLowerCase(), target.toLowerCase()) <=
        maxDistance;
  }

  /// Standard Levenshtein distance between two strings.
  static int distance(String a, String b) {
    if (a == b) return 0;
    if (a.isEmpty) return b.length;
    if (b.isEmpty) return a.length;

    final List<int> prev = List<int>.generate(b.length + 1, (i) => i);
    final List<int> curr = List<int>.filled(b.length + 1, 0);

    for (int i = 1; i <= a.length; i++) {
      curr[0] = i;
      for (int j = 1; j <= b.length; j++) {
        final int cost = a[i - 1] == b[j - 1] ? 0 : 1;
        curr[j] = _min3(
          curr[j - 1] + 1,
          prev[j] + 1,
          prev[j - 1] + cost,
        );
      }
      for (int j = 0; j <= b.length; j++) {
        prev[j] = curr[j];
      }
    }
    return prev[b.length];
  }

  static int _min3(int a, int b, int c) {
    final int m = a < b ? a : b;
    return m < c ? m : c;
  }
}
