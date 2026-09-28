import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:labelguard_mobile/services/field_extractor.dart';

// Scans #34 and #35: the back of an Amul dark chocolate wrapper (MRP ₹45.00,
// USP ₹1.29/g, 35 g, Pkd 11/JUN/26, Exp 11/JUN/27, BN KIF1621), as OCR read it.
void main() {
  final extractor = FieldExtractor();
  final scan34 = extractor.extract(File('test/fixtures_amul_scan34.txt').readAsStringSync());
  final scan35 = extractor.extract(File('test/fixtures_amul_scan35.txt').readAsStringSync());

  group('Amul scan #35', () {
    test('a ₹ sign read as "3" is corrected by the unit sale price', () {
      // "345.00;" under "For MP (nd. ef all taves)"; USP 1.29/g × 35 g ≈ 45.
      expect(scan35.mrp, '45.00');
    });

    test('dates with no separator before the year', () {
      expect(scan35.mfgDate, '11/JUN25');
      expect(scan35.expiryDate, '11/JUN27');
    });

    test('"BN" is a batch heading, and "see belot" is not "lot"', () {
      expect(scan35.batchNumber, 'KIF1621');
    });

    test('net weight', () {
      expect(scan35.netQuantity, '35 g');
    });
  });

  group('Amul scan #34', () {
    test('the price printed alone below "For MRP" agrees with the USP', () {
      expect(scan34.mrp, '45.00');
    });

    test('dates are read, as OCR printed them', () {
      // OCR read the 6 as an 8; the server now gives a future date REVIEW.
      expect(scan34.mfgDate, '11/JUN/28');
    });
  });

  group('MRP safety across packs', () {
    test('"MRP:3" (a lone rupee sign) loses to the printed price (scan #30)', () {
      final g = extractor.extract('MRP:3\nUSP (R Per gl:\nNET QUANTITY:\nRs.109.00\nRs.0.31 Per g');
      expect(g.mrp, '109.00');
    });

    test('a lone amount after MRP is not taken without "see below" (nutrition values)', () {
      final g = extractor.extract('MRP:\nUSP (R Per g):\nNUTRITIONAL INFORMATION\nEnergy\n11.19\n4.40');
      expect(g.mrp, isNull);
    });
  });

  group('Unit sale price check', () {
    test('a weakly placed price that disagrees with the USP is left blank', () {
      final g = extractor.extract('For MRP (incl. of all taxes) see below\n'
          '999.00;\nUSP ₹1.29/g\nNet Weight: 35 g');
      expect(g.mrp, isNull);
    });

    test('a labelled MRP that agrees with the USP is kept', () {
      final g = extractor.extract('MRP ₹45.00 (incl. of all taxes)\nUSP ₹1.29/g\nNet Weight: 35 g');
      expect(g.mrp, '45.00');
    });

    test('without a USP the price is taken as read', () {
      final g = extractor.extract('For MRP (incl. of all taxes) see below\n45.00;\nNet Weight: 35 g');
      expect(g.mrp, '45.00');
    });
  });
}
