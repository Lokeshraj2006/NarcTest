/// Extracts structured Legal Metrology fields from OCR output.
///
/// Strategy:
///   1. Strict regex for well-known label patterns in the flattened text
///   2. When ML Kit line positions are supplied, pair declaration headings
///      with values printed beside them — often in a separate column
///   3. Fuzzy keyword matching when both miss
///
/// Fully offline, no ML model, deterministic. Returns null for fields it
/// cannot confidently detect. Makes no compliance decision — the backend
/// server's compliance rules do that.
///
/// Ported from the legal_metrology_compliance_scanner prototype, with
/// GSTIN and manufacturer-address extraction added for the FieldProof
/// backend (GSTIN feeds rule 13; address feeds the registry cross-check).
library;

import 'dart:math' as math;

import '../models/extracted_fields.dart';
import '../models/scan_models.dart';
import '../utils/fuzzy_match.dart';

class FieldExtractor {
  /// [lines] are ML Kit text lines with pixel boxes. Without them only the
  /// flattened text is used.
  ExtractedFields extract(
    String rawText, {
    List<OcrTextBlockGeometry> lines = const [],
  }) {
    final textLines = rawText
        .split(RegExp(r'\r?\n'))
        .map((l) => l.trim())
        .where((l) => l.isNotEmpty)
        .toList();

    final flat = rawText.replaceAll(RegExp(r'\s+'), ' ').trim();
    final company = _companyBlock(textLines);
    final manufacturerBlock =
        company == null ? _extractManufacturer(flat) : null;
    final panel = _DeclarationPanel(lines);

    return ExtractedFields(
      rawText: rawText,
      productName:
          lines.isEmpty ? _firstPlausibleName(textLines) : _prominentName(lines),
      manufacturer: company?.name ?? _manufacturerName(manufacturerBlock),
      manufacturerAddress:
          company?.address ?? _manufacturerAddress(manufacturerBlock),
      countryOfOrigin: _extractCountryOfOrigin(textLines, flat),
      netQuantity: _netQuantityLabelled(flat) ??
          panel.value(_Declaration.netQuantity) ??
          _netQuantityNearKeyword(flat),
      mrp: _mrp(flat, textLines, panel),
      mfgDate: _extractMfgDate(flat) ?? panel.manufactureDate,
      expiryDate: _extractExpiryDate(flat) ?? panel.expiryDate,
      batchNumber:
          _extractBatchNumber(flat) ?? panel.value(_Declaration.batch),
      fssaiNumber: _extractFssai(textLines, flat),
      gstNumber: _extractGstin(flat),
      lmpcNumber: _extractLmpc(flat),
      consumerCarePhone: _extractPhone(flat, textLines),
      consumerCareEmail: _extractEmail(flat),
      ingredients: _extractIngredients(flat),
    );
  }

  // ── Product name ─────────────────────────────────────────────────────
  static final _skipPrefix = RegExp(
    r'^(ingredients|nutrition|mrp|net\s*qty|net\s*wt|batch|mfg|use\s*by|allergen|fssai|ssai|lic\.?\s*no|manufactured|packed|marketed|imported|for\s+feedback|consumer|gstin|gst\s*no)',
    caseSensitive: false,
  );

  // Label text that is never the product's name: instructions, addresses,
  // company lines, web and social handles.
  static final _notAName = RegExp(
    r'\b(?:store|storage|keep|container|place|opened|packaged|packed|atmosphere|material|feedback|quer(?:y|ies)|write|consumer|customer|manufactured|marketed|ingredients?|nutrition(?:al)?|allergen|contains|best\s+before|use\s+by|batch|mrp|net\s+(?:qty|quantity|wt|weight)|favourites|find\s+mor\w*|product\s+of|india|trade\s*mark|copyright|limited|ltd|pvt|private|www|com|\w*ormation|rda|approx|calculated|serving|apprec\w*)\b|@',
    caseSensitive: false,
  );

  // A cross-sell list heading ("Find more favourites"). The singular
  // "favourite" is left out: it appears on brand badges beside the title.
  static final _crossSellHeading = RegExp(
    r'find\s+mor|favourites|also\s+(?:try|available)|more\s+from',
    caseSensitive: false,
  );

  bool _looksLikeNonProductKeyword(String line) {
    final lower = line.toLowerCase();
    for (final keyword in const [
      'ingredients',
      'nutrition',
      'allergen',
      'manufactured',
      'marketed',
      'consumer',
      'feedback',
      'fssai',
      'batch',
      'net qty',
      'net wt',
    ]) {
      final firstWord = lower.split(' ').first;
      if (FuzzyMatch.close(firstWord, keyword.split(' ').first)) {
        return true;
      }
    }
    return false;
  }

  bool _isPlausibleName(String line) {
    if (line.length < 3 || line.length > 60 || line.endsWith('.')) return false;
    if (_skipPrefix.hasMatch(line) || _notAName.hasMatch(line)) return false;
    if (_looksLikeNonProductKeyword(line)) return false;
    if (line.replaceAll(RegExp(r'[^A-Za-z]'), '').length < 3) return false;
    if (RegExp(r'\d').allMatches(line).length > 2) return false;
    return line.split(RegExp(r'\s+')).length <= 6;
  }

  /// Text-only fallback: the first plausible line near the top, skipping the
  /// short product list that follows a "find more favourites" heading.
  String? _firstPlausibleName(List<String> lines) {
    final int scanLimit = lines.length < 12 ? lines.length : 12;
    int skipThrough = -1;
    for (int i = 0; i < scanLimit; i++) {
      final line = lines[i];
      if (_crossSellHeading.hasMatch(line)) {
        skipThrough = i + 4;
        continue;
      }
      if (i <= skipThrough || !_isPlausibleName(line)) continue;
      final words = line.split(RegExp(r'\s+'));
      if (words.length == 1 && line == line.toUpperCase() && line.length < 6) {
        continue;
      }
      return line;
    }
    return null;
  }

  /// With positions: the tallest multi-word line clearly larger than the
  /// label's body text. A lone brand word or a cross-sell list doesn't count.
  String? _prominentName(List<OcrTextBlockGeometry> lines) {
    final heights = lines.map((l) => l.height).where((h) => h > 0).toList()
      ..sort();
    if (heights.isEmpty) return null;
    final bodyHeight = heights[heights.length ~/ 2];

    OcrTextBlockGeometry? best;
    String? bestName;
    for (final line in lines) {
      final text = _stripPromoWords(line.text.trim());
      if (line.height < bodyHeight * 1.6) continue;
      if (text.split(RegExp(r'\s+')).length < 2 || !_isPlausibleName(text)) {
        continue;
      }
      if (_inCrossSellList(line, lines)) continue;
      if (best == null || line.height > best.height) {
        best = line;
        bestName = text;
      }
    }
    return _clean(bestName);
  }

  static const _promoWords = [
    'favourite', 'favorite', 'aapka', 'offer', 'free', 'extra', 'save', 'new',
  ];

  /// Badge words OCR merges onto the ends of the title line, including ones
  /// cut short at either end ("…SEV FAVOURIT", "…SSV VOURITE").
  String _stripPromoWords(String text) {
    final words = text.split(RegExp(r'\s+'));
    bool isPromo(String word) {
      final letters = word.toLowerCase().replaceAll(RegExp(r'[^a-z]'), '');
      if (letters.length < 3) return false;
      return _promoWords.any((promo) =>
          promo == letters ||
          (letters.length >= 5 &&
              (promo.startsWith(letters) || promo.endsWith(letters))));
    }

    while (words.isNotEmpty && isPromo(words.last)) {
      words.removeLast();
    }
    while (words.isNotEmpty && isPromo(words.first)) {
      words.removeAt(0);
    }
    return words.join(' ');
  }

  bool _inCrossSellList(
    OcrTextBlockGeometry line,
    List<OcrTextBlockGeometry> lines,
  ) {
    for (final heading in lines) {
      if (identical(heading, line) ||
          !_crossSellHeading.hasMatch(heading.text)) {
        continue;
      }
      final below = line.y > heading.y + heading.height * 0.5 &&
          line.y < heading.y + heading.height * 8;
      final alongside = line.x < heading.x + heading.width * 1.5 &&
          line.x + line.width > heading.x - heading.width * 0.5;
      if (below && alongside) return true;
    }
    return false;
  }

  // ── Manufacturer ─────────────────────────────────────────────────────
  // OCR returns a label's columns in no reliable order: on a real pack the
  // line after "MARKETED BY:" was a nutrition footnote. So the block is found
  // by its shape: a company line ("… PRIVATE LIMITED") followed by address
  // lines ending in a six-digit PIN code, preferring one under a heading.
  static final _byHeading = RegExp(
    r'(?:manufactured|mfd\.?|packed|marketed|imported)\s*(?:(?:and|&)\s*\w+\s*)?by\b\s*[:\-]?\s*',
    caseSensitive: false,
  );
  static final _contactHeading = RegExp(
    r'consumer|customer|feedback|quer(?:y|ies)|write\s+to',
    caseSensitive: false,
  );
  // Nutrition and ingredient text OCR interleaves with address lines.
  static final _notAddress = RegExp(
    r'%|\brda\b|per\s*serv|kcal|per\s*100|ingredients?|allergen|nutrition',
    caseSensitive: false,
  );
  // Six digits, sometimes printed with a space ("Anand - 388 001").
  static final _pinCode = RegExp(r'(?<!\d)[1-8]\d{2} ?\d{3}(?!\d)');

  /// "Pvt", "Ltd", or "Private"/"Limited" as OCR misreads them ("PRVATE",
  /// "LUMITED", "LIMİTED", "PRIVATELM"). Short words get one edit, so
  /// "listed" and "limits" don't count.
  static bool _namesCompany(String text) => RegExp(r'[a-z]+')
      .allMatches(_ltdMisreads(text).replaceAll(RegExp('[İı]'), 'i').toLowerCase())
      .map((m) => m.group(0)!)
      .any((w) =>
          w == 'pvt' ||
          w == 'ltd' ||
          w == 'llp' ||
          w.startsWith('privatel') ||
          (w.length >= 6 &&
              ['private', 'limited'].any((form) => FuzzyMatch.close(w, form,
                  maxDistance: w.length >= 7 ? 2 : 1))));

  /// "Ltd" with its t read as a capital I, an l or a 1 ("P} LId", scan #32).
  /// Case-sensitive, so a lowercase "lid" ("see lid") is left alone.
  static String _ltdMisreads(String text) =>
      text.replaceAll(RegExp(r'\bL[Il1|]d\b'), 'Ltd');

  ({String name, String? address})? _companyBlock(List<String> lines) {
    ({String name, String? address})? best;
    var bestRank = 3;
    for (var i = 0; i < lines.length; i++) {
      final segments = lines[i].split(',');
      final k = segments.indexWhere(_namesCompany);
      if (k < 0) continue;

      final rest = segments.sublist(k + 1).join(',').trim();
      final address = [if (rest.isNotEmpty) rest];
      var hasPin = _pinCode.hasMatch(rest);
      var kept = 0;
      for (var j = i + 1; !hasPin && j < lines.length && kept < 6; j++) {
        final next = lines[j];
        if (_byHeading.hasMatch(next) || _namesCompany(next)) break;
        hasPin = _pinCode.hasMatch(next);
        final noise = _notAddress.hasMatch(next) ||
            !RegExp(r'[A-Za-z]{3}').hasMatch(next);
        if (noise && !hasPin) continue;
        address.add(next);
        kept++;
      }
      if (!hasPin) continue;

      // A heading just above wins; the consumer-feedback address comes last.
      final context = [
        if (i > 1) lines[i - 2],
        if (i > 0) lines[i - 1],
        segments.sublist(0, k + 1).join(','),
      ].join(' ');
      final rank = _byHeading.hasMatch(context)
          ? 0
          : _contactHeading.hasMatch(context)
              ? 2
              : 1;
      if (rank >= bestRank) continue;

      final heading = _byHeading.firstMatch(segments[k]);
      final name = _clean(
        (heading == null ? segments[k] : segments[k].substring(heading.end))
            .replaceFirst(RegExp(r'^[^A-Za-z(]+'), ''),
      );
      if (name == null) continue;
      best = (name: name, address: _clean(address.join(' ')));
      bestRank = rank;
    }
    return best;
  }

  /// Fallback when no company block carries a PIN code: the text after a
  /// manufacturer heading, only if it names a company or has a PIN code.
  String? _extractManufacturer(String flat) {
    final match = RegExp(
      r'(?:manufactured|mfd\.?|packed|marketed|imported)\s+by\s*[:\-]?\s*(.{10,200}?)(?=\s*(?:s+a+i*|fssai|ssai|lic\.?\s*no|gstin|gst\s*no|net\s*qty|nett?\s*wt|net\s*weight|mrp|batch|b\.?\s*no|mfg\.?\s*date|mfd\.?\s*dt|use\s*by|for\s+feedback|consumer|barcode|$))',
      caseSensitive: false,
      dotAll: true,
    ).firstMatch(flat);

    if (match == null) return null;
    var v = _clean(match.group(1));
    if (v == null) return null;
    if (!_namesCompany(v) && !_pinCode.hasMatch(v)) return null;
    if (v.length > 200) v = '${v.substring(0, 200)}...';
    return v;
  }

  /// The portion before the first comma is usually the company name;
  /// everything after it is the address.
  String? _manufacturerName(String? block) {
    if (block == null) return null;
    final idx = block.indexOf(',');
    if (idx <= 0) return block;
    return _clean(block.substring(0, idx));
  }

  String? _manufacturerAddress(String? block) {
    if (block == null) return null;
    final idx = block.indexOf(',');
    if (idx <= 0 || idx + 1 >= block.length) return null;
    return _clean(block.substring(idx + 1));
  }

  // ── Country of origin ────────────────────────────────────────────────
  static final _countryLabel = RegExp(
    r'(?:country\s+of\s+origin|country\s+of\s+manufacture|made\s+in|product\s+of)\s*[:\-]?\s*',
    caseSensitive: false,
  );

  String? _extractCountryOfOrigin(List<String> lines, String flat) {
    // Prefer the rest of the labelled line: in flattened text, a title printed
    // just below "PRODUCT OF INDIA" would be read as part of the country.
    for (final line in lines) {
      final label = _countryLabel.firstMatch(line);
      if (label == null) continue;
      final rest = line
          .substring(label.end)
          .replaceAll(RegExp(r'[^A-Za-z ]'), '  ')
          .trim();
      final country = rest.split(RegExp(r'\s{2,}')).first.trim();
      if (country.length >= 2) return _clean(country);
    }

    // Non-greedy with a terminator lookahead: the flattened text has no line
    // breaks, so a greedy [A-Za-z ]+ would run past the country into whatever
    // label section follows it.
    final match = RegExp(
      r'(?:country\s+of\s+origin|country\s+of\s+manufacture|made\s+in|product\s+of)\s*[:\-]?\s*([A-Za-z][A-Za-z ]{1,40}?)(?=\s*(?:for\s+feedback|consumer|customer|mrp|m\.r\.p|net\s|nett?\s|batch|b\.?\s*no|mfg|mfd|packed|marketed|manufactured|imported|fssai|ssai|lic\.?\s*no|gstin|gst\s*no|best\s+before|use\s+by|expiry|exp\.?\s*date|ingredients|nutrition|$))',
      caseSensitive: false,
    ).firstMatch(flat);
    if (match == null) return null;
    return _clean(match.group(1));
  }

  // ── Net quantity ─────────────────────────────────────────────────────
  static const _quantityValue =
      r'(\d+(?:\.\d+)?\s*(?:kg|mg|gms|gm|grams?|mls|ml|litres?|liters?|l|g))';
  // OCR-tolerant: an accented E ("NĚT"), a letter misread inside QUANTITY
  // ("QUAWTITY") and a cut-off end ("QUANTIT") all still count.
  static const _netKeyword =
      r'(?:n[eéèêëěēėęEÉÈÊËĚĒĖĘ]t\s*(?:[qo0]u[a-z]{3,6}y?|qty|wt|weight|volume|contents?)|nett?\s*(?:wt|weight|qty))';

  String? _netQuantityLabelled(String flat) {
    final strict = RegExp(
      [_netKeyword, r'\.?\s*[:\-]?\s*', _quantityValue].join(),
      caseSensitive: false,
    ).firstMatch(flat);
    if (strict != null) return _clean(strict.group(1));

    final keyword = RegExp(_netKeyword, caseSensitive: false).firstMatch(flat);
    if (keyword == null) return null;
    final int end =
        (keyword.end + 40) > flat.length ? flat.length : keyword.end + 40;
    final m = RegExp(_quantityValue, caseSensitive: false)
        .firstMatch(flat.substring(keyword.end, end));
    return m == null ? null : _clean(m.group(1));
  }

  String? _netQuantityNearKeyword(String flat) {
    final quantity =
        RegExp(_quantityValue, caseSensitive: false).allMatches(flat);
    for (final m in quantity) {
      final int start = m.start;
      final int from = start - 30 < 0 ? 0 : start - 30;
      final String window = flat.substring(from, start).toLowerCase();
      if (window.contains('net') ||
          window.contains('nett') ||
          window.contains('qty') ||
          window.contains('wt')) {
        return _clean(m.group(1));
      }
    }
    return null;
  }

  // ── MRP ──────────────────────────────────────────────────────────────
  // Thousands separators (1,299.50) are kept, and a decimal point OCR read
  // as a comma ("Rs.109,00") becomes 109.00. The lookahead refuses a date
  // ("08/02/27") or a unit price ("0.31 per g") that follows the MRP heading
  // in the flattened text.
  static const _amount =
      r'(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:[.,]\d{1,2})?)(?!\d|,\d|\.\d|[\/\-]\d|\s*per\b)';

  String? _mrp(String flat, List<String> textLines, _DeclarationPanel panel) {
    var labelled = _mrpLabelled(flat);
    // "MRP:₹" with the price in another column reads as "MRP:3" (scans #4,
    // #30): a lone digit loses to a currency amount printed elsewhere.
    if (labelled != null && RegExp(r'^\d$').hasMatch(labelled)) {
      final currency = _mrpByCurrency(flat);
      if (currency != null && double.tryParse(currency) != double.parse(labelled)) {
        labelled = null;
      }
    }
    final strong = labelled ?? panel.value(_Declaration.mrp);
    if (strong != null) return _reconcileWithUnitPrice(strong, flat, weak: false);
    final standalone = _mrpStandalone(textLines);
    if (standalone != null) {
      return _reconcileWithUnitPrice(standalone, flat, weak: true);
    }
    // An MRP heading with no amount beside it: the price is covered or
    // unreadable. Any other amount on the label is more likely the unit price
    // or a nutrition figure (scan #43), so the field is left blank.
    if (panel.hasHeading(_Declaration.mrp)) return null;
    final byCurrency = _mrpByCurrency(flat);
    return byCurrency == null
        ? null
        : _reconcileWithUnitPrice(byCurrency, flat, weak: false);
  }

  /// Packs print a unit sale price ("USP ₹1.29/g") that must equal the MRP
  /// divided by the net quantity. OCR reads the ₹ sign as a digit ("345.00"
  /// for ₹45.00, scan #35), so a price that disagrees with USP × quantity but
  /// agrees once its first digit is dropped is corrected. A weakly placed
  /// price that agrees neither way is left blank rather than filled wrong.
  String? _reconcileWithUnitPrice(String mrp, String flat, {required bool weak}) {
    final usp = RegExp(
      r'\busp\s*[:\-]?\s*(?:₹|rs\.?|r|&)?\s*(\d+(?:\.\d+)?)\s*/\s*(kg|ml|[g9l])\b',
      caseSensitive: false,
    ).firstMatch(flat);
    final qty = RegExp(
      '$_netKeyword[^\\d]{0,20}$_quantityValue',
      caseSensitive: false,
    ).firstMatch(flat);
    final price = double.tryParse(mrp.replaceAll(',', ''));
    if (usp == null || qty == null || price == null) return mrp;

    final unitPrice = double.parse(usp.group(1)!);
    var uspUnit = usp.group(2)!.toLowerCase();
    if (uspUnit == '9') uspUnit = 'g';
    final amount = RegExp(r'(\d+(?:\.\d+)?)\s*([a-z]+)', caseSensitive: false)
        .firstMatch(qty.group(1)!);
    if (amount == null) return mrp;
    var quantity = double.parse(amount.group(1)!);
    final qtyUnit = amount.group(2)!.toLowerCase();
    // Express the quantity in the USP's unit.
    const toBase = {'kg': 1000.0, 'g': 1.0, 'gm': 1.0, 'gms': 1.0, 'l': 1000.0, 'ml': 1.0};
    final from = toBase[qtyUnit], to = toBase[uspUnit];
    if (from == null || to == null) return mrp;
    quantity = quantity * from / to;
    final expected = unitPrice * quantity;
    if (expected <= 0) return mrp;

    bool agrees(double p) => (p - expected).abs() / expected <= 0.05;
    if (agrees(price)) return mrp;
    if (mrp.length > 1) {
      final dropped = mrp.substring(1);
      final p = double.tryParse(dropped.replaceAll(',', ''));
      if (p != null && agrees(p)) return dropped;
    }
    return weak ? null : mrp;
  }

  String? _mrpLabelled(String flat) {
    final strict = RegExp(
      // OCR reads the ₹ sign as "&" or "?" ("MRP.:&250.00", scan #32).
      r'(?:mrp|m\.r\.p\.?|maximum\s+retail\s+price)\s*[:\-]?\s*[₹&?rs\.\s:]*' +
          _amount,
      caseSensitive: false,
    ).firstMatch(flat);
    return strict == null ? null : _clean(_normaliseAmount(strict.group(1)!));
  }

  /// "For MRP (incl. of all taxes) … see below" with the price printed alone
  /// in a block further down ("45.00;", scan #34 — its ₹ sign went unread).
  /// Only a line that is nothing but a two-decimal amount, after an MRP line.
  String? _mrpStandalone(List<String> textLines) {
    // "MRP" can be read as "MP"; then only with the tax wording after it
    // ("For MP (nd. ef all taves)", scan #35), since "MP" is also a state.
    final mrpHeading = RegExp(
      r'\bm\.?\s?r\.?\s?p\b|\bm\.?\s?p\b[^\n]{0,25}(?:incl|nd\.|all\s+ta)',
      caseSensitive: false,
    );
    final heading = textLines.indexWhere(mrpHeading.hasMatch);
    if (heading < 0) return null;
    // Only when the label says the price is printed elsewhere ("see below"),
    // and only just after: on Haldiram's panel the first lone amounts after
    // "MRP" are nutrition values (11.19, 4.40), a false tampering flag.
    final redirect = RegExp(r'\bsee\b|\bbelow\b', caseSensitive: false);
    final near = textLines.skip(heading).take(3);
    if (!near.any(redirect.hasMatch)) return null;
    final alone = RegExp(r'^(?:[₹&?]|rs\.?)?\s*(\d{1,5}\.\d{2})\s*[;:,.]?$',
        caseSensitive: false);
    for (final line in textLines.skip(heading + 1).take(5)) {
      final m = alone.firstMatch(line);
      if (m != null) return m.group(1);
    }
    return null;
  }

  String? _mrpByCurrency(String flat) {
    final rupee = RegExp(r'(?:₹|rs\.?)\s*' + _amount, caseSensitive: false)
        .firstMatch(flat);
    return rupee == null ? null : _clean(_normaliseAmount(rupee.group(1)!));
  }

  // ── Dates ────────────────────────────────────────────────────────────
  // Numeric, "06 July 2026", or a month abbreviation between separators
  // ("11/JUN/26", Amul).
  static const _dateValue =
      // The separator before the year can go unread ("Pkd.11/JUN25", scan #35).
      '($_numericDate|\\d{1,2}\\s+[A-Za-z]{3,9}\\s+\\d{4}|\\d{1,2}\\s?[\\/\\-\\. ]\\s?[A-Za-z]{3}\\s?[\\/\\-\\. ]?\\s?\\d{2,4}\\b)';

  String? _extractMfgDate(String flat) {
    final match = RegExp(
      [
        // A bare "MFD:" or "MFD 27/08/26" (lid and seal prints) counts too;
        // the lookahead keeps the date's first digit inside the value.
        // Lid prints often render the colon as "!" or "|" ("MFD!27/08/26").
        r'(?:mfg[.,]?\s*date|mfd[.,]?\s*dt\.?|mf[dg]\.?(?=\s*[:\-!|;]?\s*\d)|manufactured\s+on|pkd\.?|packed\s+on)\s*[:\-!|;]?\s*',
        _dateValue,
      ].join(),
      caseSensitive: false,
    ).firstMatch(flat);
    if (match == null) return null;
    return _clean(_compactDate(match.group(1)!));
  }

  String? _extractExpiryDate(String flat) {
    final match = RegExp(
      [
        // "USE BU" / "USE BV": the Y of a dot-matrix lid print misread.
        r'(?:use\s*b[yuv]|best\s*before|expiry|exp[.,]?\s*date|exp\.?(?=\s*[:\-]?\s*\d)|expires?\s+on)\s*[:\-!|;]?\s*',
        _dateValue,
      ].join(),
      caseSensitive: false,
    ).firstMatch(flat);
    if (match == null) return null;
    return _clean(_compactDate(match.group(1)!));
  }

  // ── Batch number ─────────────────────────────────────────────────────
  String? _extractBatchNumber(String flat) {
    final match = RegExp(
      // Word boundaries: "see belot" (a misread "below") once gave "lot"
      // and took the price after it as the batch (scan #35). "BN" is
      // Amul's heading ("BN KIF1621").
      r'\b(?:batch\s*(?:n[o0]|number)?|b\.?\s*n[o0]\.?|bn\b|lot\s*(?:n[o0]|number)?)\.?\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9\.\-/]{3,30})',
      caseSensitive: false,
    ).firstMatch(flat);
    if (match == null) return null;

    var v = _clean(match.group(1));
    if (v == null) return null;

    v = v.replaceFirst(RegExp(r'^B\.?\s*NO\.?\s*', caseSensitive: false), '');
    // Batch codes carry digits; a word here is the next heading ("MFG. DATE").
    if (v.trim().isEmpty || !RegExp(r'\d').hasMatch(v)) return null;
    // A price ("345.00") is never a batch code.
    if (RegExp(r'^\d+[.,]\d{2}$').hasMatch(v)) return null;
    return v;
  }

  // ── FSSAI ────────────────────────────────────────────────────────────
  // A licence is always 14 digits. OCR sometimes puts a space inside one
  // ("10014011 001919"), so a space is allowed within a line, never across
  // lines where it would join the next number. Shorter reads are misreads.
  static const _licenceLabel =
      r'(?:fssai|ssai|lic\.?\s*no\.?|license\s*no\.?)\s*[:\-]?\s*';

  String? _extractFssai(List<String> lines, String flat) {
    final spaced = RegExp(
      [_licenceLabel, r'(\d{3,11} ?\d{3,11})(?!\d)'].join(),
      caseSensitive: false,
    );
    for (final line in lines) {
      final digits = spaced.firstMatch(line)?.group(1)!.replaceAll(' ', '');
      if (digits != null && digits.length == 14) return digits;
    }
    // The label can sit on the line above its number.
    return RegExp([_licenceLabel, r'(\d{14})(?!\d)'].join(), caseSensitive: false)
        .firstMatch(flat)
        ?.group(1);
  }

  // ── GSTIN (added for FieldProof rule 13) ───────────────────────────────────
  String? _extractGstin(String flat) {
    // Labelled form first: "GSTIN: 27AAPFU0939F1ZV".
    final labelled = RegExp(
      r'(?:gstin|gst\s*(?:no|number)?|g\.?s\.?t\.?)\s*[:\-]?\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z])',
      caseSensitive: false,
    ).firstMatch(flat.toUpperCase());
    if (labelled != null) return _clean(labelled.group(1));

    // Bare 15-char GSTIN anywhere on the label.
    final bare = RegExp(
      r'\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z])\b',
    ).firstMatch(flat.toUpperCase());
    if (bare != null) return _clean(bare.group(1));

    return null;
  }

  // ── LMPC registration (Rule 27) ──────────────────────────────────────
  /// Formats vary by state (e.g. "LMPC/HR/1234", "IMP-1234567"), so this
  /// anchors on the label keyword rather than trying to match a structure.
  String? _extractLmpc(String flat) {
    final match = RegExp(
      r'(?:lmpc|l\.m\.p\.c\.?|legal\s+metrology)\s*(?:reg(?:n|istration)?\.?)?\s*(?:no\.?|number)?\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9\/\-\.]{3,30})',
      caseSensitive: false,
    ).firstMatch(flat);
    if (match != null) return _clean(match.group(1));

    // Importer registration is sometimes labelled without "LMPC".
    final importer = RegExp(
      r'(?:importer|import)\s*(?:reg(?:n|istration)?\.?)\s*(?:no\.?|number)?\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9\/\-\.]{3,30})',
      caseSensitive: false,
    ).firstMatch(flat);
    if (importer != null) return _clean(importer.group(1));

    return null;
  }

  // ── Consumer care ────────────────────────────────────────────────────
  // Digit look-arounds keep a phone number from being cut out of a longer
  // number: every real scan once read one from the FSSAI licence
  // ("10014011001919" gave "4011001919").
  String? _extractPhone(String flat, List<String> textLines) {
    final tollFree = RegExp(
      r'(?<!\d)(1800[\s\-]?\d{2,4}[\s\-]?\d{3,4})(?!\d)',
    ).firstMatch(flat);
    if (tollFree != null) return _clean(tollFree.group(1));

    final indian = RegExp(
      r'(?<!\d)(\+91[\s\-]?\d{5}[\s\-]?\d{5}|[6-9]\d{9})(?!\d)',
    ).firstMatch(flat);
    if (indian != null) return _clean(indian.group(1));

    // Landline with its STD code ("0120-2400286"). The phone icon printed
    // beside it is often read as a leading digit ("90120-2400286").
    final landline = RegExp(
      r'(?<!\d)\d?(0\d{2,4}[\s\-]\d{6,8})(?!\d)',
    ).firstMatch(flat);
    if (landline != null) return _clean(landline.group(1));

    // Line by line: two nutrition values on consecutive lines ("48.00" /
    // "142.92" read as "4800" / "14292", scan #32) are not a phone number.
    final loose = RegExp(r'(?<!\d)(\d{4}[ \t\-]?\d{2}[ \t\-]?\d{3,4})(?!\d)');
    for (final line in textLines) {
      final m = loose.firstMatch(line);
      if (m != null) return _clean(m.group(1));
    }

    return null;
  }

  String? _extractEmail(String flat) {
    final strict = RegExp(
      r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})',
    ).firstMatch(flat);
    if (strict != null) return _clean(strict.group(1))?.replaceAll(' ', '');

    // OCR often reads "CONSUMER FEEDBACK@PEPSICO COM" with a space.
    final loose = RegExp(
      r'([A-Za-z0-9._%+\-]+)\s*@\s*([A-Za-z0-9.\-]+)\s*[\.,]\s*([A-Za-z]{2,})',
    ).firstMatch(flat);
    if (loose != null) {
      final local = loose.group(1) ?? '';
      final domain = loose.group(2) ?? '';
      final tld = loose.group(3) ?? '';
      return _clean('$local@$domain.$tld');
    }

    return null;
  }

  // ── Ingredients ──────────────────────────────────────────────────────
  String? _extractIngredients(String flat) {
    final match = RegExp(
      r'ingredients?\s*[:\-]\s*(.+?)(?=\s*(?:allergen\s*advice|allergen|nutrition(?:al)?\s*information|mrp|net\s*qty|nett?\s*wt|for\s+feedback|consumer\s+services|manufactured\s+by|$))',
      caseSensitive: false,
      dotAll: true,
    ).firstMatch(flat);
    if (match == null) return null;
    return _clean(match.group(1));
  }

  // ── Helper: trim, collapse whitespace, strip trailing punctuation ────
  String? _clean(String? input) {
    if (input == null) return null;
    var s = input.trim().replaceAll(RegExp(r'\s+'), ' ');
    s = s.replaceAll(RegExp(r'[,;\.\s]+$'), '');
    if (s.isEmpty) return null;
    if (s.length > 200) s = '${s.substring(0, 200)}...';
    return s;
  }
}

/// "109,00" is a decimal comma; "1,299" stays a thousands separator.
String _normaliseAmount(String amount) =>
    RegExp(r'^\d+,\d{1,2}$').hasMatch(amount)
        ? amount.replaceFirst(',', '.')
        : amount;

/// A numeric day-month-year date, allowing the spaces OCR puts inside one:
/// "06.07. 26", and "06.07 26" where the second dot was lost (scan #29). A
/// lone space before the year must not be followed by a dot, digit or colon,
/// so nutrition figures ("16.42 14.93") and times ("06.07 12:36") are refused.
const _numericDate =
    r'\d{1,2}\s?[\/\-\.]\s?\d{1,2}(?:\s?[\/\-\.]\s?\d{2,4}\b|\s\d{2,4}(?![.\d:]))';

/// "06.07. 26" and "06.07 26" → "06.07.26"; a written-out month is unchanged.
String _compactDate(String date) {
  final m = RegExp(
    r'^(\d{1,2})\s?([\/\-\.])\s?(\d{1,2})(?:\s?[\/\-\.]\s?|\s)(\d{2,4})$',
  ).firstMatch(date.trim());
  return m == null ? date : '${m[1]}${m[2]}${m[3]}${m[2]}${m[4]}';
}

/// Dates printed with no headings, as on an ink-jet seal or lid ("27/08/26
/// 26/05/27 A276"). With exactly two different dates, the earlier is the
/// manufacture date and the later the expiry; anything else gives null,
/// because nothing tells the dates apart. Only for a photo of the surface the
/// label itself names for its dates ("USE BY: SEE SEAL"); the user checks
/// the result on Review Details.
({String made, String expires})? unlabelledDatePair(String text) {
  final found = <DateTime, String>{};
  for (final m in RegExp(r'(?<![\d.\/\-])' + _numericDate).allMatches(text)) {
    final written = _compactDate(m.group(0)!);
    final date = _parseLabelDate(written);
    if (date != null) found.putIfAbsent(date, () => written);
  }
  if (found.length != 2) return null;
  final ordered = found.keys.toList()..sort();
  return (made: found[ordered.first]!, expires: found[ordered.last]!);
}

/// Indian labels print day first: 06.07.26, 13/07/2026.
DateTime? _parseLabelDate(String text) {
  final parts = _compactDate(text).split(RegExp(r'[\/\-\.]'));
  if (parts.length != 3) return null;
  final day = int.tryParse(parts[0]);
  final month = int.tryParse(parts[1]);
  var year = int.tryParse(parts[2]);
  if (day == null || month == null || year == null) return null;
  if (year < 100) year += 2000;
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  return DateTime(year, month, day);
}

enum _Declaration { netQuantity, mrp, batch }

/// Pairs declaration headings with the values printed beside them.
///
/// Labels often print headings in one column and values in another, and a
/// separately printed value column can sit a row above or below its
/// headings. A value is accepted only when it lies to the right, within a
/// row or so, and has the shape its heading demands — so a date is never
/// taken as a price. Dates are told apart by value instead: the manufacture
/// date is always earlier than the expiry date.
class _DeclarationPanel {
  _DeclarationPanel(List<OcrTextBlockGeometry> lines)
      : _lines = lines
            .where((l) => l.text.trim().isNotEmpty && l.height > 0)
            .toList();

  final List<OcrTextBlockGeometry> _lines;
  final Set<OcrTextBlockGeometry> _used = {};

  bool _datesResolved = false;
  String? _manufactureDate;
  String? _expiryDate;

  static final Map<_Declaration, RegExp> _headings = {
    _Declaration.netQuantity: RegExp(
      r'^n[eéèêëěēėęEÉÈÊËĚĒĖĘ]t\s*(?:[qo0]u[a-z]{3,6}y?|qty|wt|weight|vol(?:ume)?|contents?)\b',
      caseSensitive: false,
    ),
    _Declaration.mrp: RegExp(
      r'^(?:m\.?\s?r\.?\s?p|maximum\s+retail\s+price)\b',
      caseSensitive: false,
    ),
    _Declaration.batch: RegExp(
      r'^(?:b?atch|lot)\b(?:[.,]?\s*(?:n[o0]?|number)\b\.?)?',
      caseSensitive: false,
    ),
  };
  static final _mfgHeading = RegExp(
    r'^(?:(?:m[fg]{1,2}|mfd|pkd|packed)[.,]?\s*(?:date|dt|on)|date\s+of\s+(?:mfg|manufacture|packing))\b',
    caseSensitive: false,
  );
  // USE BY is often read cut short ("E BY:").
  static final _expiryHeading = RegExp(
    r'^(?:u?s?e\s*by|best\s*before|expiry|exp[.,]?\s*date)\b',
    caseSensitive: false,
  );

  static final _quantity = RegExp(
    r'^(\d+(?:\.\d+)?)\s*(kg|mg|gms|gm|grams?|mls|ml|litres?|liters?|l|g)\b',
    caseSensitive: false,
  );
  static final _date = RegExp('^($_numericDate)');
  // OCR reads "Rs." as "Re" and drops decimal points ("Re60 00").
  static final _price = RegExp(
    r'^(rs|re|₹|inr)?\.?\s*(\d[\d,]*)(?:[.\s](\d{2}))?$',
    caseSensitive: false,
  );
  static final _batchCode = RegExp(r'^[A-Za-z0-9][A-Za-z0-9\-\/]{3,20}$');

  // The unit sale price is printed a row below the MRP ("USP (₹ Per g):").
  // With the MRP's own amount covered, its value was the nearest price left
  // and was taken as the MRP (scan #43: "Rs 9.31", a misread "Rs 0.31"), a
  // false tampering flag against the registry's ₹109.
  static final _unitPriceHeading = RegExp(
    r'^(?:u\.?\s?s\.?\s?p\b|unit\s+(?:sale\s+)?price\b)',
    caseSensitive: false,
  );

  /// A price line that sits nearer a unit-price heading than [heading], when
  /// that heading has no "… per g" value of its own. On scan #11 the whole
  /// value column sat lower, so the MRP's own "Re60 00" was nearer "USP" —
  /// but the USP's value, "30 per 9", was there too.
  bool _belongsToUnitPrice(OcrTextBlockGeometry line, OcrTextBlockGeometry heading) {
    final centre = line.y + line.height / 2;
    final toHeading = (centre - (heading.y + heading.height / 2)).abs();
    return _headingLines(_unitPriceHeading).any((u) =>
        (centre - (u.y + u.height / 2)).abs() < toHeading &&
        !_lines.any((l) =>
            !identical(l, u) &&
            _inRow(l, u) &&
            RegExp(r'\d.*\bper\b', caseSensitive: false).hasMatch(l.text)));
  }

  String? get manufactureDate {
    _resolveDates();
    return _manufactureDate;
  }

  String? get expiryDate {
    _resolveDates();
    return _expiryDate;
  }

  List<OcrTextBlockGeometry> _headingLines(RegExp pattern) => _lines
      .where((l) => l.text.trim().length <= 32 && pattern.hasMatch(l.text.trim()))
      .toList();

  bool hasHeading(_Declaration kind) => _headingLines(_headings[kind]!).isNotEmpty;

  bool _inRow(OcrTextBlockGeometry line, OcrTextBlockGeometry heading) {
    final centre = line.y + line.height / 2;
    return line.x >= heading.x + heading.width * 0.6 &&
        centre >= heading.y - heading.height * 1.5 &&
        centre <= heading.y + heading.height * 2.5;
  }

  String? value(_Declaration kind) {
    for (final heading in _headingLines(_headings[kind]!)) {
      final headingCentre = heading.y + heading.height / 2;
      OcrTextBlockGeometry? best;
      String? bestValue;
      double bestDistance = double.infinity;

      for (final line in _lines) {
        if (identical(line, heading) || _used.contains(line)) continue;
        if (!_inRow(line, heading)) continue;
        if (kind == _Declaration.mrp && _belongsToUnitPrice(line, heading)) continue;
        final shaped = _shape(kind, line.text.trim());
        if (shaped == null) continue;
        final distance = (line.y + line.height / 2 - headingCentre).abs();
        if (distance < bestDistance) {
          best = line;
          bestValue = shaped;
          bestDistance = distance;
        }
      }

      if (best != null) {
        _used.add(best);
        return bestValue;
      }
    }
    return null;
  }

  void _resolveDates() {
    if (_datesResolved) return;
    _datesResolved = true;

    final mfgHeadings = _headingLines(_mfgHeading);
    final expiryHeadings = _headingLines(_expiryHeading);
    if (mfgHeadings.isEmpty && expiryHeadings.isEmpty) return;

    // The declarations block spans every recognised heading.
    final headings = [
      for (final pattern in _headings.values) ..._headingLines(pattern),
      ...mfgHeadings,
      ...expiryHeadings,
    ];
    var top = double.infinity;
    var bottom = double.negativeInfinity;
    var left = double.infinity;
    var rowHeight = 0.0;
    for (final h in headings) {
      top = math.min(top, h.y);
      bottom = math.max(bottom, h.y + h.height);
      left = math.min(left, h.x + h.width * 0.6);
      rowHeight = math.max(rowHeight, h.height);
    }

    final dates = <OcrTextBlockGeometry, DateTime>{};
    for (final line in _lines) {
      if (_used.contains(line) || line.x < left) continue;
      final centre = line.y + line.height / 2;
      if (centre < top - rowHeight * 1.5 || centre > bottom + rowHeight * 1.5) {
        continue;
      }
      final text = _date.firstMatch(line.text.trim())?.group(1);
      final date = text == null ? null : _parseLabelDate(text);
      if (date != null) dates[line] = date;
    }

    if (dates.length >= 2) {
      final ordered = dates.keys.toList()
        ..sort((a, b) => dates[a]!.compareTo(dates[b]!));
      final earliest = ordered.first;
      final latest = ordered.last;
      if (dates[earliest] == dates[latest]) return;
      if (mfgHeadings.isNotEmpty) {
        _manufactureDate = _dateText(earliest);
        _used.add(earliest);
      }
      // A faint USE BY heading often goes unread; with exactly two dates
      // beside a manufacture-date heading, the later one is still the expiry.
      if (expiryHeadings.isNotEmpty ||
          (mfgHeadings.isNotEmpty && dates.length == 2)) {
        _expiryDate = _dateText(latest);
        _used.add(latest);
      }
      return;
    }

    if (dates.length == 1) {
      final only = dates.keys.single;
      final inMfgRow = mfgHeadings.any((h) => _inRow(only, h));
      final inExpiryRow = expiryHeadings.any((h) => _inRow(only, h));
      if (inMfgRow == inExpiryRow) return;
      if (inMfgRow) {
        _manufactureDate = _dateText(only);
      } else {
        _expiryDate = _dateText(only);
      }
      _used.add(only);
    }
  }

  String? _dateText(OcrTextBlockGeometry line) {
    final date = _date.firstMatch(line.text.trim())?.group(1);
    return date == null ? null : _compactDate(date);
  }

  String? _shape(_Declaration kind, String text) {
    switch (kind) {
      case _Declaration.netQuantity:
        final m = _quantity.firstMatch(text);
        return m == null ? null : '${m.group(1)} ${m.group(2)}';
      case _Declaration.mrp:
        if (text.toLowerCase().contains('per')) return null;
        final m = _price.firstMatch(text);
        if (m == null || (m.group(1) == null && m.group(3) == null)) {
          return null;
        }
        final whole = _normaliseAmount(m.group(2)!);
        return m.group(3) == null ? whole : '$whole.${m.group(3)}';
      case _Declaration.batch:
        final isCode = _batchCode.hasMatch(text) &&
            text.contains(RegExp(r'[A-Za-z]')) &&
            text.contains(RegExp(r'\d'));
        if (!isCode || _date.hasMatch(text) || _quantity.hasMatch(text)) {
          return null;
        }
        return text;
    }
  }
}
