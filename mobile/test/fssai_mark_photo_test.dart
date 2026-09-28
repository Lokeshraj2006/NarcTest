import 'package:flutter_test/flutter_test.dart';
import 'package:labelguard_mobile/models/inspection_log_models.dart';
import 'package:labelguard_mobile/models/scan_models.dart';

void main() {
  group('Veg mark from an extra photo', () {
    test('says which photo showed the mark', () {
      final r = ScanResponse.fromJson({
        'overall_status': 'compliant',
        'fssai_mark': {
          'status': 'vegetarian',
          'confidence': 1.0,
          'photo': 1,
          'photos_checked': 2,
        },
      });
      expect(r.fssaiMark?.status, 'vegetarian');
      expect(r.fssaiMark?.foundOn, 'extra photo 1');
      expect(r.fssaiMark?.photosChecked, 2);
    });

    test('a scan with only the main photo shows nothing extra', () {
      final m = FssaiMarkModel.fromJson({'status': 'vegetarian', 'photo': 0});
      expect(m.photosChecked, 1);
      expect(m.foundOn, isNull);
    });

    test('older scans without the fields still parse', () {
      final d = InspectionDetail.fromJson({
        'fssai_mark': {'status': 'not_found', 'confidence': 0.0},
      });
      expect(d.fssaiMark?.photo, isNull);
      expect(d.fssaiMark?.photosChecked, 1);
      expect(d.fssaiMark?.foundOn, isNull);
    });
  });
}
