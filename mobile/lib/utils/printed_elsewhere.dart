import '../models/extracted_fields.dart';

// Many packs print the dates or the price on another surface and say so on
// the label ("BATCH NO., MFD., USE BY: SEE SEAL"). Mirrors the server's check
// in compliance_rules.py, so the app can point the user to the right place.
const _place =
    r'[\s\S]{0,40}?\bsee\s+(?:the\s+)?'
    r'(seal|lid|top|cap|crimp|bottom|base|back|side|neck|shoulder|carton|pack|pouch)\b';

final _datesElsewhere = RegExp(
  r'(?:mf[dg]|manufactur|pkd|packed|use\s*by|best\s*before|expiry|\bexp\b|batch|\bb\.?\s*no)' +
      _place,
  caseSensitive: false,
);

final _priceElsewhere = RegExp(
  r'(?:\bm\.?\s?r\.?\s?p\b|retail\s+(?:sale\s+)?price)' + _place,
  caseSensitive: false,
);

/// Where the label says its dates are printed ("seal"), if it says so.
String? datesPrintedOn(String rawText) =>
    _datesElsewhere.firstMatch(rawText)?.group(1)?.toLowerCase();

/// Where the label says its price is printed ("bottom"), if it says so.
String? pricePrintedOn(String rawText) =>
    _priceElsewhere.firstMatch(rawText)?.group(1)?.toLowerCase();

/// Fields a second photo can fill, keyed as on Review Details. Wrappers split
/// their declarations across panels and folds (scan #34), so any blank field
/// can come from another part of the pack.
const elsewhereFieldLabels = <String, String>{
  'mfgDate': 'manufacture date',
  'expiryDate': 'use-by date',
  'mrp': 'MRP',
  'batchNumber': 'batch number',
  'productName': 'product name',
  'manufacturer': 'manufacturer',
  'manufacturerAddress': 'manufacturer address',
  'netQuantity': 'net quantity',
  'countryOfOrigin': 'country of origin',
  'fssaiNumber': 'FSSAI licence',
  'gstNumber': 'GSTIN',
  'lmpcNumber': 'LMPC number',
  'consumerCarePhone': 'consumer care phone',
  'consumerCareEmail': 'consumer care email',
};

Map<String, String?> _readings(ExtractedFields extra) => {
      'mfgDate': extra.mfgDate,
      'expiryDate': extra.expiryDate,
      'mrp': extra.mrp,
      'batchNumber': extra.batchNumber,
      'productName': extra.productName,
      'manufacturer': extra.manufacturer,
      'manufacturerAddress': extra.manufacturerAddress,
      'netQuantity': extra.netQuantity,
      'countryOfOrigin': extra.countryOfOrigin,
      'fssaiNumber': extra.fssaiNumber,
      'gstNumber': extra.gstNumber,
      'lmpcNumber': extra.lmpcNumber,
      'consumerCarePhone': extra.consumerCarePhone,
      'consumerCareEmail': extra.consumerCareEmail,
    };

/// Values read from a second photo, for only the fields still blank.
/// Never overwrites anything the first photo read or the user typed.
Map<String, String> valuesToFill({
  required Map<String, String> current,
  required ExtractedFields extra,
}) {
  return {
    for (final e in _readings(extra).entries)
      if ((current[e.key] ?? '').trim().isEmpty && (e.value ?? '').trim().isNotEmpty)
        e.key: e.value!.trim(),
  };
}

/// Fields the second photo read differently from what the form holds now.
/// Only offered to the user, never applied on its own: either photo can be
/// the misread one, and the value may be what the user typed.
Map<String, ({String current, String read})> valuesThatDiffer({
  required Map<String, String> current,
  required ExtractedFields extra,
}) {
  final out = <String, ({String current, String read})>{};
  for (final e in _readings(extra).entries) {
    final now = (current[e.key] ?? '').trim();
    final read = (e.value ?? '').trim();
    if (now.isEmpty || read.isEmpty) continue;
    if (_comparable(e.key, now) == _comparable(e.key, read)) continue;
    out[e.key] = (current: now, read: read);
  }
  return out;
}

/// Punctuation, spacing and case don't make a value different: "27.08.26" is
/// "27/08/26", and "45" is "45.00" for an MRP.
String _comparable(String key, String value) {
  final v = value.toLowerCase();
  if (key == 'mrp') {
    final amount = double.tryParse(v.replaceAll(RegExp(r'[^0-9.]'), ''));
    if (amount != null) return amount.toStringAsFixed(2);
  }
  return v.replaceAll(RegExp(r'[^a-z0-9]'), '');
}

/// "manufacture date, use-by date and MRP"
String joinLabels(List<String> labels) {
  if (labels.length <= 1) return labels.join();
  return '${labels.sublist(0, labels.length - 1).join(', ')} and ${labels.last}';
}
