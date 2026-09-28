import 'package:flutter_test/flutter_test.dart';
import 'package:labelguard_mobile/models/inspection_log_models.dart';
import 'package:labelguard_mobile/models/scan_models.dart';

void main() {
  group('Barcode source', () {
    test('a scan response carries the barcode and who read it', () {
      final r = ScanResponse.fromJson({
        'overall_status': 'compliant',
        'barcode': '8904004400779',
        'barcode_source': 'server',
      });
      expect(r.barcode, '8904004400779');
      expect(r.barcodeSource, 'server');
    });

    test('the inspector detail carries the barcode and who read it', () {
      final d = InspectionDetail.fromJson({
        'barcode': '8904004400779',
        'barcode_source': 'device',
      });
      expect(d.barcode, '8904004400779');
      expect(d.barcodeSource, 'device');
    });

    test('says which reader found the barcode', () {
      expect(barcodeSourceLabel('8904004400779', 'device'), 'The phone');
      expect(barcodeSourceLabel('8904004400779', 'server'), contains('The server'));
      expect(barcodeSourceLabel(null, null),
          'Neither the phone nor the server could read it');
      expect(barcodeSourceLabel('', 'device'),
          'Neither the phone nor the server could read it');
    });

    test('older scans with a barcode but no recorded source say so', () {
      expect(barcodeSourceLabel('8904004400779', null), 'Not recorded for this scan');
    });
  });
}
