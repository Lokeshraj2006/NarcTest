/// Models for kit profiles and sealed test records (see docs/CONTRACT.md).
library;

import 'dart:ui' show Color;

List<int>? _intList(dynamic v) {
  if (v is! List || v.length < 3) return null;
  return v.map((e) => (e as num).round()).toList();
}

Color? rgbColor(List<int>? rgb) {
  if (rgb == null || rgb.length < 3) return null;
  int c(int x) => x.clamp(0, 255);
  return Color.fromARGB(255, c(rgb[0]), c(rgb[1]), c(rgb[2]));
}

class KitOutcome {
  final String label;
  final String category;
  final List<int>? srgb;

  KitOutcome({required this.label, required this.category, this.srgb});

  Color? get color => rgbColor(srgb);

  factory KitOutcome.fromJson(Map<String, dynamic> j) => KitOutcome(
        label: j['label']?.toString() ?? '',
        category: j['category']?.toString() ?? '',
        srgb: _intList(j['srgb']),
      );
}

List<KitOutcome> _outcomes(dynamic v) => (v is List ? v : const [])
    .whereType<Map>()
    .map((e) => KitOutcome.fromJson(Map<String, dynamic>.from(e)))
    .toList();

class KitProfile {
  final int id;
  final String code;
  final String name;
  final String reagent;
  final int readTimeS;
  final List<KitOutcome> outcomes;

  KitProfile({
    required this.id,
    required this.code,
    required this.name,
    required this.reagent,
    required this.readTimeS,
    required this.outcomes,
  });

  factory KitProfile.fromJson(Map<String, dynamic> j) => KitProfile(
        id: (j['id'] as num?)?.toInt() ?? 0,
        code: j['code']?.toString() ?? '',
        name: j['name']?.toString() ?? 'Kit',
        reagent: j['reagent']?.toString() ?? '',
        readTimeS: (j['read_time_s'] as num?)?.toInt() ?? 10,
        outcomes: _outcomes(j['outcomes']),
      );
}

class TestRecord {
  final Map<String, dynamic> raw;
  TestRecord(this.raw);

  factory TestRecord.fromJson(Map<String, dynamic> j) => TestRecord(j);

  String? _s(String k) => raw[k]?.toString();
  double? _d(String k) => (raw[k] as num?)?.toDouble();

  int get id => (raw['id'] as num?)?.toInt() ?? 0;
  String get testUid => _s('test_uid') ?? '';
  String get result => (_s('result') ?? 'INCONCLUSIVE').toUpperCase();
  String? get outcomeLabel => _s('outcome_label');
  int? get confidence => (raw['confidence'] as num?)?.round();
  String? get reason => _s('reason');
  String? get createdAt => _s('created_at');
  String? get ntpTime => _s('ntp_time');
  String get timeSource => _s('time_source') ?? 'server_clock';
  double? get latitude => _d('latitude');
  double? get longitude => _d('longitude');
  double? get gpsAccuracyM => _d('gps_accuracy_m');
  bool get gpsIsMock => raw['gps_is_mock'] == true;
  String get officerName => _s('officer_name') ?? '-';
  String get kitName => _s('kit_name') ?? '-';
  String get imageSha256 => _s('image_sha256') ?? '';
  String get recordHash => _s('record_hash') ?? '';
  String? get signature => _s('signature');
  String? get verifyUrl => _s('verify_url');
  String? get reviewStatus => _s('review_status');
  bool? get clientHashMatch => raw['client_hash_match'] as bool?;
  List<int>? get measuredRgb => _intList(raw['measured_rgb']);
  Color? get measuredColor => rgbColor(measuredRgb);
  List<KitOutcome> get kitOutcomes => _outcomes(raw['kit_outcomes']);
}
