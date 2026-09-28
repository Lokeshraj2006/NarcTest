import 'package:flutter_test/flutter_test.dart';
import 'package:labelguard_mobile/models/extracted_fields.dart';
import 'package:labelguard_mobile/services/field_extractor.dart';
import 'package:labelguard_mobile/utils/printed_elsewhere.dart';

void main() {
  final extractor = FieldExtractor();

  group('Dates or price printed elsewhere', () {
    test('finds the seal on an Ob & Gob tub label', () {
      const label = 'Net Qty.: 200ml / 155g\nBATCH NO., MFD., USE BY: SEE SEAL';
      expect(datesPrintedOn(label), 'seal');
      expect(pricePrintedOn(label), isNull, reason: 'the redirect is about dates');
    });

    test('a redirect split across OCR lines still counts', () {
      expect(datesPrintedOn('MFD., USE BY: SEE\nTOP'), 'top');
    });

    test('a price printed on the bottom', () {
      expect(pricePrintedOn('M.R.P.: SEE BOTTOM OF PACK'), 'bottom');
    });

    test('an unrelated "see back" is not a date redirect', () {
      expect(datesPrintedOn('Ingredients: see back of pack'), isNull);
    });
  });

  group('Scan another part', () {
    test('reads the lid print of the Ob & Gob tub', () {
      // The tub's lid: batch and dates printed without a "DATE" heading.
      const lid = 'B.NO:A276\nMFD:27/08/26\nUSE BY:26/05/27';
      final f = extractor.extract(lid);
      expect(f.mfgDate, '27/08/26');
      expect(f.expiryDate, '26/05/27');
      expect(f.batchNumber, 'A276');
    });

    test('a volume-and-weight declaration reads as the volume', () {
      // The registry stores 200 ml; picking 155 g would read as tampering.
      final qty = extractor.extract('Net Qty.: 200ml / 155g').netQuantity;
      expect(qty?.replaceAll(' ', ''), '200ml');
    });

    test('a bare MFD with a space keeps the whole date', () {
      expect(extractor.extract('MFD 27/08/26').mfgDate, '27/08/26');
    });

    test('fills only the fields that are still blank', () {
      const extra = ExtractedFields(
        rawText: '',
        mfgDate: '27/08/26',
        expiryDate: '26/05/27',
        mrp: '999',
        batchNumber: 'A276',
      );
      final fills = valuesToFill(
        current: {'mfgDate': '', 'expiryDate': '  ', 'mrp': '250.00', 'batchNumber': ''},
        extra: extra,
      );
      expect(fills, {'mfgDate': '27/08/26', 'expiryDate': '26/05/27', 'batchNumber': 'A276'});
      expect(fills.containsKey('mrp'), isFalse, reason: 'never overwrite a value already there');
    });

    test('fills contact and maker details from a folded panel too (scan #34)', () {
      const extra = ExtractedFields(
        rawText: '',
        manufacturer: 'Kaira District Co-operative Milk Producers Union Ltd.',
        consumerCarePhone: '1800 258 3333',
        consumerCareEmail: 'customercare@amul.coop',
      );
      final fills = valuesToFill(
        current: {'manufacturer': '', 'consumerCarePhone': '', 'consumerCareEmail': ''},
        extra: extra,
      );
      expect(fills.keys, containsAll(['manufacturer', 'consumerCarePhone', 'consumerCareEmail']));
    });

    test('names the fields in plain words', () {
      expect(joinLabels(['manufacture date']), 'manufacture date');
      expect(joinLabels(['manufacture date', 'use-by date', 'MRP']),
          'manufacture date, use-by date and MRP');
    });

    test('a field the first photo misread is offered, not replaced', () {
      // Amul #35: a rupee sign read as a leading digit gave MRP 345.00.
      const extra = ExtractedFields(rawText: '', mrp: '45.00', mfgDate: '11/06/26');
      final current = {'mrp': '345.00', 'mfgDate': ''};
      expect(valuesToFill(current: current, extra: extra), {'mfgDate': '11/06/26'});
      final differ = valuesThatDiffer(current: current, extra: extra);
      expect(differ.keys, ['mrp']);
      expect(differ['mrp']!.current, '345.00');
      expect(differ['mrp']!.read, '45.00');
    });

    test('the same value written differently is not a difference', () {
      const extra = ExtractedFields(
        rawText: '',
        mrp: '45',
        mfgDate: '27.08.26',
        manufacturer: 'Haldiram Snacks Food Pvt Ltd',
      );
      final differ = valuesThatDiffer(
        current: {
          'mrp': '45.00',
          'mfgDate': '27/08/26',
          'manufacturer': 'HALDIRAM SNACKS FOOD PVT. LTD.',
        },
        extra: extra,
      );
      expect(differ, isEmpty);
    });
  });

  group('Seal dates printed without headings', () {
    test('two dates: the earlier is made, the later expires', () {
      final pair = unlabelledDatePair('26/05/27\n27/08/26\nA276');
      expect(pair?.made, '27/08/26');
      expect(pair?.expires, '26/05/27');
    });

    test('dates and batch on one ink-jet line', () {
      final pair = unlabelledDatePair('A276 27.08.26 26.05.27');
      expect(pair?.made, '27.08.26');
      expect(pair?.expires, '26.05.27');
    });

    test('one date, three dates or the same date twice decide nothing', () {
      expect(unlabelledDatePair('27/08/26 A276'), isNull);
      expect(unlabelledDatePair('01/01/26 27/08/26 26/05/27'), isNull);
      expect(unlabelledDatePair('27/08/26 27.08.26'), isNull);
    });

    test('phone numbers and nutrition values are not dates', () {
      expect(unlabelledDatePair('0120-2400286\n16.42 14.93\n1800 258 3333'), isNull);
    });

    test('the extractor itself still needs a heading', () {
      final f = extractor.extract('27/08/26\n26/05/27\nA276');
      expect(f.mfgDate, isNull);
      expect(f.expiryDate, isNull);
    });
  });
}
