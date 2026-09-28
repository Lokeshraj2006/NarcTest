import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:labelguard_mobile/services/field_extractor.dart';

// Scan #32: the side label of an Ob & Gob ice-cream tub, as OCR read it.
void main() {
  final extractor = FieldExtractor();
  final raw = File('test/fixtures_obgob_side.txt').readAsStringSync();
  final f = extractor.extract(raw);

  test('reads the MRP when the rupee sign is read as "&"', () {
    expect(f.mrp, '250.00');
  });

  test('finds the manufacturer when "Ltd" is read as "LId"', () {
    expect(f.manufacturer, contains('Dairy Classic'));
    expect(f.manufacturerAddress, contains('562112'));
  });

  test('two nutrition values on separate lines are not a phone number', () {
    expect(f.consumerCarePhone, isNot('4800 14292'));
  });

  test('a garbled "Nutritional Information" heading is not the product name', () {
    expect(f.productName, isNot('Nona tntormation'));
  });

  test('still reads the net quantity and FSSAI licence', () {
    expect(f.netQuantity, '200ml');
    expect(f.fssaiNumber, '10012043000476');
  });

  test('reads lid prints with a misread colon or "BY"', () {
    final a = extractor.extract('B.NO:A276\nMFD!27/08/26\nUSE BY:26/05/27');
    expect(a.mfgDate, '27/08/26');
    expect(a.expiryDate, '26/05/27');
    final b = extractor.extract('B.NO:A27G\nMFD:27/08/26\nUSE BU:26/05/27');
    expect(b.mfgDate, '27/08/26');
    expect(b.expiryDate, '26/05/27');
  });

  test('a nutrition footnote is never the product name (scan #33)', () {
    final g = extractor.extract('hpprox Values ** % RDA Calculated\nNet Qty.: 200ml');
    expect(g.productName, isNot(contains('RDA')));
  });

  test('reads Amul-style dates with a month name and a bare "Exp."', () {
    // As printed on an Amul dark chocolate wrapper.
    final g = extractor.extract('₹45.00;\nUSP ₹1.29/g\nPkd.11/JUN/26\nExp.11/JUN/27;BF1\nBN.KIF1621');
    expect(g.mfgDate, '11/JUN/26');
    expect(g.expiryDate, '11/JUN/27');
  });

  test('reads a price printed alone below "For MRP … see below" (scan #34)', () {
    final g = extractor.extract(
      'For MRP (Incl, of all taxes), Date of Packaglng (Pk0J\n'
      'See below.\n45.00;\nUSP R1. 297g\nPkd.11/JUN/28',
    );
    expect(g.mrp, '45.00');
  });

  test('a lone amount is not an MRP without an MRP heading', () {
    expect(extractor.extract('Total Fat (g)\n33.10\nSodium').mrp, isNull);
  });

  test('a cut-off "We appreciate your feedback" is not a product name', () {
    expect(extractor.extract('We apprec\nNet Weight: 35 g').productName, isNot('We apprec'));
  });

  test('finds a manufacturer whose PIN code has a space', () {
    final g = extractor.extract(
      'Manufactured by:\n'
      "Kaira District Co-operative Milk Producers' Union Ltd., Anand - 388 001, Gujarat, India.",
    );
    expect(g.manufacturer, contains('Kaira'));
  });

  test('a lowercase "lid" is not read as a company', () {
    final g = extractor.extract('Dates: see lid\nNagpur 441104');
    expect(g.manufacturer, isNull);
  });
}
