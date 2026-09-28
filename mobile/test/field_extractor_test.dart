import 'package:flutter_test/flutter_test.dart';
import 'package:labelguard_mobile/models/scan_models.dart';
import 'package:labelguard_mobile/services/field_extractor.dart';

OcrTextBlockGeometry line(String text, double x, double y, double width,
        [double height = 20]) =>
    OcrTextBlockGeometry(
        text: text, x: x, y: y, width: width, height: height);

String joined(List<OcrTextBlockGeometry> lines) =>
    lines.map((l) => l.text).join('\n');

void main() {
  final extractor = FieldExtractor();

  group('FieldExtractor', () {
    test('extracts core fields from a realistic label', () {
      const label = '''
MAGGI 2-Minute Masala Noodles
Manufactured by: Nestle India Ltd., Nestle House, Jacaranda Marg, Gurgaon 122002
Net Wt.: 70 g
MRP: Rs. 14.00 (inclusive of all taxes)
Mfg Date: 12/05/2026
Best Before: 12/11/2026
Batch No: L2345AB
FSSAI Lic No. 10012011000027
GSTIN: 06AAACN1160N1ZG
Country of Origin: India
For feedback call 1800 103 1947 or consumer.services@in.nestle.com
''';

      final f = extractor.extract(label);

      expect(f.productName, contains('MAGGI'));
      expect(f.manufacturer, contains('Nestle India'));
      expect(f.manufacturerAddress, contains('Gurgaon'));
      expect(f.netQuantity, '70 g');
      expect(f.mrp, '14.00');
      expect(f.mfgDate, '12/05/2026');
      expect(f.expiryDate, '12/11/2026');
      expect(f.batchNumber, 'L2345AB');
      expect(f.fssaiNumber, '10012011000027');
      expect(f.gstNumber, '06AAACN1160N1ZG');
      expect(f.countryOfOrigin, 'India');
      expect(f.consumerCarePhone, isNotNull);
      expect(f.consumerCareEmail, 'consumer.services@in.nestle.com');
    });

    test('tolerates OCR noise in keywords and spacing', () {
      const noisy = '''
Nett Wt  :  500  gm
M.R.P.  Rs 105
MFD DT : 01-01-2026
''';
      final f = extractor.extract(noisy);
      expect(f.netQuantity, '500 gm');
      expect(f.mrp, '105');
      expect(f.mfgDate, '01-01-2026');
    });

    test('extracts LMPC registration number', () {
      expect(extractor.extract('LMPC Regn No: LMPC/HR/1234').lmpcNumber,
          'LMPC/HR/1234');
      expect(extractor.extract('Importer Registration No. IMP-7788991').lmpcNumber,
          'IMP-7788991');
      expect(extractor.extract('no registration here').lmpcNumber, isNull);
    });

    test('toOcrFields carries the fields rules 5, 8 and 12 depend on', () {
      const label = '''
Net Wt 70 g
MRP Rs. 14.00 inclusive of all taxes
LMPC Regn No: LMPC/HR/1234
Consumer care: 1800 103 1947 / care@nestle.in
''';
      final o = extractor.extract(label).toOcrFields();
      expect(o.consumerCarePhone, isNotNull, reason: 'rule 8 needs this');
      expect(o.consumerCareEmail, 'care@nestle.in');
      expect(o.lmpcNumber, 'LMPC/HR/1234', reason: 'rule 12 needs this');
      expect(o.rawText, isNotNull, reason: 'rule 5 scans raw text');
      expect(o.rawText, contains('inclusive of all taxes'));

      final json = o.toJson();
      expect(json['consumer_care_phone'], isNotNull);
      expect(json['lmpc_number'], 'LMPC/HR/1234');
      expect(json['raw_text'], isNotNull);
    });

    test('finds a bare GSTIN with no label prefix', () {
      final f = extractor.extract('Some text 27AAPFU0939F1ZV more text');
      expect(f.gstNumber, '27AAPFU0939F1ZV');
    });

    test('recovers an email OCR split across a space', () {
      final f = extractor.extract('CONSUMER FEEDBACK@PEPSICO, COM');
      expect(f.consumerCareEmail, 'FEEDBACK@PEPSICO.COM');
    });

    test('returns nulls rather than guesses on empty input', () {
      final f = extractor.extract('');
      expect(f.productName, isNull);
      expect(f.mrp, isNull);
      expect(f.gstNumber, isNull);
      expect(f.filledFieldCount, 0);
    });

    test('toOcrFields parses MRP to a number for the backend', () {
      final f = extractor.extract('MRP: Rs. 1,299.50');
      expect(f.toOcrFields().mrp, 1299.50);
    });

    test('a date after the MRP heading is not read as the price', () {
      expect(extractor.extract('MRP\n08/02/27\nRs.60.00').mrp, '60.00');
      expect(extractor.extract('MRP Rs.0.31 Per g').mrp, isNull);
    });

    test('text-only product name skips label boilerplate', () {
      const raw = 'MATERLAL IN ANAIR TIGHT CONTAINER.\n'
          'PACKAGED IN A PROTECTIVE ATMOSPHERE\n'
          'Aloo Bhujia\n'
          'Net Wt 400 g';
      expect(extractor.extract(raw).productName, 'Aloo Bhujia');
      expect(
        extractor
            .extract('STORE IN A COOL & DRY PLACE\nFor Feedback or Queries, Write to-')
            .productName,
        isNull,
      );
    });
  });

  group('FieldExtractor with line positions', () {
    // Text is what ML Kit read from a real Haldiram's Bhujia Sev pack (scan
    // #11), including its misreads. Positions follow that photo: headings in
    // one column, values in another, printed about a row lower.
    final bhujiaSev = [
      line('BHUJIA SEV', 505, 420, 310, 48),
      line('1037, we combined | tradition with delicate', 140, 470, 360, 18),
      line('eraftsmenship to introduce our moth dal Bhujia.', 140, 492, 370, 18),
      line('FIND MORE', 150, 645, 140, 26),
      line('FAVOURITES', 150, 672, 150, 26),
      line('ALOO BHUJIA SEV', 170, 708, 170),
      line('2ANATTA MEETHA', 170, 736, 160),
      line('STORE IN A COOL& DRY PLACE, ONCE OPENED', 150, 805, 330, 18),
      line('NET OUANTITY:', 135, 1318, 125),
      line('ATCH NO.:', 135, 1343, 90),
      line('MG DATE:', 135, 1368, 95),
      line('MRP', 135, 1412, 40),
      line('USP', 135, 1462, 35),
      line('200 g', 312, 1320, 55),
      line('LFG13-18', 425, 1370, 85),
      line('4107/26', 425, 1395, 80),
      line('8/02/27', 425, 1420, 78),
      line('Re60 00', 425, 1445, 80),
      line('30 per 9', 440, 1470, 80),
    ];

    test('pairs headings with values printed in a separate, lower column', () {
      final f = extractor.extract(joined(bhujiaSev), lines: bhujiaSev);
      expect(f.netQuantity, '200 g');
      expect(f.batchNumber, 'LFG13-18');
      expect(f.mrp, '60.00');
      expect(f.mfgDate, isNull, reason: 'OCR misread the date as 4107/26');
      expect(f.expiryDate, isNull, reason: 'the USE BY heading was not read');
    });

    // Scan #43: Haldiram's panel with the MRP amount under a finger. The ink-jet
    // column holds only the unit price ("Rs 0.31" per g, read as "Rs 9.31"),
    // level with its USP heading; "MRP:₹" read as "MRP:3".
    List<OcrTextBlockGeometry> haldiramPanel({required bool mrpVisible}) => [
          line('NET QUANTITY:', 135, 1318, 125),
          line('400 g (350 g + 50 g EXTRA)', 312, 1318, 220),
          line('MRP:3', 135, 1412, 60),
          if (mrpVisible) line('Rs. 109.00', 425, 1412, 95),
          line('(Incl. of all taxes)', 135, 1436, 140),
          line('USP ( Per g):', 135, 1462, 110),
          line('Rs 9.31', 425, 1462, 70),
        ];

    test('the unit price is never taken as the MRP when the MRP is covered', () {
      final lines = haldiramPanel(mrpVisible: false);
      expect(extractor.extract(joined(lines), lines: lines).mrp, isNull);
    });

    test('with both printed, the MRP is its own amount, not the unit price', () {
      final lines = haldiramPanel(mrpVisible: true);
      expect(extractor.extract(joined(lines), lines: lines).mrp, '109.00');
    });

    test('takes the prominent title, not the cross-sell list', () {
      final f = extractor.extract(joined(bhujiaSev), lines: bhujiaSev);
      expect(f.productName, 'BHUJIA SEV');
    });

    test('a back panel with no prominent title gives no product name', () {
      final back = [
        line('FIND MORE', 150, 645, 140, 30),
        line('FAVOURITES', 150, 675, 150, 30),
        line('BHUJIA SEV', 170, 712, 110, 22),
        line('KHATTA MEETHA', 170, 738, 150, 22),
        line('MOONG DAL', 170, 764, 110, 22),
        line('KEEP THE MATERIAL IN AN AIR TIGHT CONTAINER.', 150, 830, 360, 18),
        line('For Feedback or Queries, Write to-', 150, 900, 300, 18),
        line('OHALDIRAMS SNACKS', 170, 1150, 230, 18),
        line('Hakirams', 180, 1230, 110, 40),
      ];
      expect(extractor.extract(joined(back), lines: back).productName, isNull);
    });

    test('a value of the wrong shape is never paired', () {
      final panel = [
        line('MRP', 135, 1412, 40),
        line('08/02/27', 425, 1420, 78),
        line('Rs.0.31 Per g', 425, 1440, 110),
      ];
      expect(extractor.extract(joined(panel), lines: panel).mrp, isNull);
    });

    test('a value on the heading line still comes from the text itself', () {
      final single = [line('MRP: Rs. 109.00 (Incl. of all taxes)', 135, 1412, 300)];
      expect(extractor.extract(joined(single), lines: single).mrp, '109.00');
    });

    // Text is what ML Kit read from a real Aloo Bhujia Sev pack (scan #13),
    // including its misreads. Positions follow that photo: here the value
    // column sits a row ABOVE its headings, the opposite of the Bhujia Sev
    // pack, and the USE BY heading was not read at all.
    final alooBhujia = [
      line("Haldiram's", 262, 447, 110, 30),
      line('ALOO BHUJIA SEV', 395, 452, 400, 34),
      line('AAPKA', 845, 415, 70, 18),
      line('FAVOURITE', 825, 440, 105, 22),
      line('CRUNCH', 850, 468, 70, 16),
      line('In 1937, we combined tradition with delicate craftsmanship', 138, 512, 370, 16),
      line('FIND MORE', 138, 670, 145, 24),
      line('FAVOURITES', 138, 697, 160, 24),
      line('BHUJIA SEV', 160, 738, 90, 16),
      line('KHATTA MEETHA', 160, 764, 125, 16),
      line('MOONG DAL', 160, 790, 95, 16),
      line('STORE IN A COOL & DRY PLACE, ONCE OPENED', 145, 822, 305, 16),
      line('NET QUANTITY:', 165, 1288, 125, 18),
      line('BATCH NO.:', 165, 1309, 95, 18),
      line('MFG. DATE:', 165, 1329, 95, 18),
      line('MRP:', 175, 1369, 45, 18),
      line('USP (R Per gl:', 177, 1406, 90, 18),
      line('400 g (350g+ 50g EXTRA")', 327, 1281, 210, 18),
      line('HAFG04', 583, 1292, 60, 16),
      line('06.07.26 12:36', 583, 1309, 105, 16),
      line('02.01.27', 583, 1326, 65, 16),
      line('Rs.109,00', 583, 1342, 70, 16),
      line('Rs.0.31 Per g', 583, 1360, 95, 16),
    ];

    test('reads a value column that sits a row above its headings', () {
      final f = extractor.extract(joined(alooBhujia), lines: alooBhujia);
      expect(f.netQuantity, '400 g');
      expect(f.batchNumber, 'HAFG04', reason: 'not the next heading, "MFG"');
      expect(f.mrp, '109.00', reason: 'OCR printed the decimal point as a comma');
      expect(f.toOcrFields().mrp, 109.0);
      expect(f.mfgDate, '06.07.26', reason: 'the earlier date is the manufacture date');
      expect(f.expiryDate, '02.01.27',
          reason: 'USE BY went unread, but the later of two panel dates is the expiry');
    });

    test('OCR edge cases from a real rescan of the same pack (scan #15)', () {
      final rescan = [
        line('ALO BHUJIA SEV FAVOURIT', 395, 452, 530, 34),
        line('In 1937, we combined tradition with delicate craftsmanship', 138, 512, 370, 16),
        line('STORE IN A COOL & DRY PLACE, ONCE OPENED', 145, 822, 305, 16),
        line('NET QUANTITY:', 165, 1288, 125, 18),
        line('BATCH N0.:', 165, 1309, 95, 18),
        line('MFG. DATE:', 165, 1329, 95, 18),
        line('400 g (350g+ 50g EXTRA")', 327, 1281, 210, 18),
        line('HAFGO4', 583, 1292, 60, 16),
        line('06.07.26 12:36', 583, 1309, 105, 16),
        line('02.01.27', 583, 1326, 65, 16),
        line('Rs.109,00', 583, 1342, 70, 16),
      ];
      final f = extractor.extract(joined(rescan), lines: rescan);
      expect(f.productName, 'ALO BHUJIA SEV', reason: 'badge word merged onto the title');
      expect(f.batchNumber, 'HAFGO4', reason: 'heading read as "N0" with a zero');
      expect(f.mfgDate, '06.07.26');
      expect(f.expiryDate, '02.01.27');
    });

    test('a badge saying "favourite" does not hide the title', () {
      final f = extractor.extract(joined(alooBhujia), lines: alooBhujia);
      expect(f.productName, 'ALOO BHUJIA SEV');
    });

    test('with both date headings, earlier and later dates are split correctly', () {
      final panel = [
        line('MFG. DATE:', 165, 1329, 95, 18),
        line('USE BY:', 165, 1349, 70, 18),
        line('02.01.27', 583, 1326, 65, 16),
        line('06.07.26 12:36', 583, 1309, 105, 16),
      ];
      final f = extractor.extract(joined(panel), lines: panel);
      expect(f.mfgDate, '06.07.26');
      expect(f.expiryDate, '02.01.27');
    });

    test('a date read with a space and a cut-off USE BY heading (scan #18)', () {
      // Text from scan #18; positions follow the same pack's scan #13 layout.
      final panel = [
        line('ALOO BHUJUIA SSV VOURITE', 395, 452, 530, 34),
        line('NET QUANTITY:', 165, 1288, 125, 18),
        line('BATCH NO.:', 165, 1309, 95, 18),
        line('MFG. DATE:', 165, 1329, 95, 18),
        line('E BY:', 185, 1349, 45, 18),
        line('HAFGO4', 583, 1292, 60, 16),
        line('06.07. 26 12:36', 583, 1309, 105, 16),
        line('02.01.27', 583, 1326, 65, 16),
      ];
      final f = extractor.extract(joined(panel), lines: panel);
      expect(f.mfgDate, '06.07.26');
      expect(f.expiryDate, '02.01.27');
      expect(f.productName, 'ALOO BHUJUIA SSV', reason: 'badge fragment "VOURITE"');

      final oneDate = panel.where((l) => !l.text.startsWith('06.07')).toList();
      final g = extractor.extract(joined(oneDate), lines: oneDate);
      expect(g.mfgDate, isNull,
          reason: 'one date between two date headings is not guessed');
      expect(g.expiryDate, isNull);
    });

    test('a date that lost its second dot is still a date (scan #29)', () {
      // Scan #29 read "06.07 26 12:36"; with only 02.01.27 left as a date,
      // the use-by date became the manufacture date and Rule 6 failed.
      final panel = [
        line('NET QUANTITY:', 165, 1288, 125, 18),
        line('BATCH NO.:', 165, 1309, 95, 18),
        line('MFG. DATE', 165, 1329, 95, 18),
        line('USE BY:', 165, 1349, 70, 18),
        line('HAFGO4', 583, 1292, 60, 16),
        line('06.07 26 12:36', 583, 1309, 105, 16),
        line('02.01.27', 583, 1326, 65, 16),
        line('Rs.109.00', 583, 1342, 70, 16),
      ];
      final f = extractor.extract(joined(panel), lines: panel);
      expect(f.mfgDate, '06.07.26');
      expect(f.expiryDate, '02.01.27');
      expect(f.batchNumber, 'HAFGO4');
    });

    test('a heading read as "NET QUAWTITY" still pairs its value (scan #19)', () {
      final panel = [
        line('NET QUAWTITY:', 165, 1288, 125, 18),
        line('BATCH NO.:', 165, 1309, 95, 18),
        line('MFG. DATE:', 165, 1329, 95, 18),
        line('400 g (350g + 50g EXTRA")', 327, 1281, 210, 18),
      ];
      expect(extractor.extract(joined(panel), lines: panel).netQuantity, '400 g');
    });

    test('a heading read as "NĚT QUANTIT" still pairs its value (scan #21)', () {
      final panel = [
        line('NĚT QUANTIT', 165, 1288, 110, 18),
        line('MFG DATE', 165, 1329, 85, 18),
        line('400 g (350g + 50g EXTRA")', 327, 1281, 210, 18),
      ];
      expect(extractor.extract(joined(panel), lines: panel).netQuantity, '400 g');
    });
  });

  group('FieldExtractor OCR punctuation', () {
    test('a comma-decimal MRP is not read as thousands', () {
      expect(extractor.extract('MRP: Rs.109,00').toOcrFields().mrp, 109.0);
      expect(extractor.extract('Rs.109,00\nRs.0.31 Per g').mrp, '109.00');
      expect(extractor.extract('MRP: Rs. 1,299').mrp, '1,299');
    });

    test('a heading read with a comma still anchors its value', () {
      expect(extractor.extract('MFG, DATE: 06.07.26').mfgDate, '06.07.26');
    });

    test('the batch pattern does not take the next heading as the batch', () {
      final f = extractor.extract('BATCH NO.: MFG. DATE: 06.07.26');
      expect(f.batchNumber, isNull);
      expect(f.mfgDate, '06.07.26');
    });

    test('country stops at the end of its line, not in the title below', () {
      // Real OCR order from scan #16.
      const raw = 'PRODUCT OF INDIA\nALOO BHUJIA SEV\nFor Feedback or Queries, Write to-';
      expect(extractor.extract(raw).countryOfOrigin, 'INDIA');
    });

    test('a batch heading cut short to "BATCH N" still pairs with its value', () {
      final panel = [
        line('BATCH N', 165, 1309, 70, 18),
        line('MFG. DATE:', 165, 1329, 95, 18),
        line('HAFGO4', 583, 1292, 60, 16),
        line('06.07.26 12:36', 583, 1309, 105, 16),
      ];
      expect(extractor.extract(joined(panel), lines: panel).batchNumber, 'HAFGO4');
    });

    test('a date OCR read with a space inside is still a date', () {
      expect(extractor.extract('MFG. DATE: 06.07. 26 12:36').mfgDate, '06.07.26');
      expect(extractor.extract('MFG. DATE: 06.07 26 12:36').mfgDate, '06.07.26');
      expect(extractor.extract('MFG. DATE: 06/07 2026').mfgDate, '06/07/2026');
      expect(extractor.extract('USE BY: 02.01.27.').expiryDate, '02.01.27');
    });

    test('numbers separated by a space are not taken as a date', () {
      expect(extractor.extract('MFG. DATE: 16.42 14.93').mfgDate, isNull,
          reason: 'nutrition figures');
      expect(extractor.extract('MFG. DATE: 06.07 12:36').mfgDate, isNull,
          reason: 'a day-month followed by a time has no year');
    });
  });

  // Excerpts of ML Kit's reading order on the real Aloo Bhujia Sev pack,
  // misreads included.
  group('FieldExtractor manufacturer and consumer care', () {
    test('takes the block under MANUFACTURED BY, not the footnote after MARKETED BY (scan #17)', () {
      const raw = 'For Feedback or Queries, Write to-\n'
          'THE CONSUMER SERVICE MANAGER,\n'
          'HALDIRAM SNACKS FOOD PRIVATE LIMITED,\n'
          'C-31, SECTOR-62,, NOIDA-201307,\n'
          'GAUTAM BUDH NAGAR, (UP), INDIA.\n'
          '90120-2400286\n'
          'Heldiram India (Pvt) Ld.\n'
          'Lic. No. 10014011001919\n'
          'MARKETED BY:\n'
          'size is 20g; 20 Serving in this pack. ##Limit of quantification\n'
          '%RDA\n'
          'Per Servet\n'
          'For EPR details scan the barcode via smart consumeY aPP\n'
          'MANUFACTURED BY:\n'
          'HALDIRAM SNACKS FOoD PRIVATE LIMITED\n'
          '(UNIT- HARIOMKAR)\n'
          '20 Km Stone, Kh. No, 4093. 410, 411, Village:\n'
          'Gumthala, Tah: Kamptee, Bhandara Road, Dist:\n'
          'Nagpur, Maharashtra, India - 441104\n'
          'FSSAI Lic. No. 10015022004173';
      final f = extractor.extract(raw);
      expect(f.manufacturer, 'HALDIRAM SNACKS FOoD PRIVATE LIMITED');
      expect(f.manufacturerAddress, startsWith('(UNIT- HARIOMKAR)'));
      expect(f.manufacturerAddress, endsWith('441104'));
      expect(f.consumerCarePhone, '0120-2400286',
          reason: 'the phone icon was read as a leading 9');
    });

    test('a company address outranks the consumer-feedback address (scan #18)', () {
      const raw = 'For Feedback or Queries, Write to-\n'
          'THE CONSUMER SERVICE MANAGER,\n'
          'HALDIRAM SNACKS FOOD PRIVATE LIMITED,\n'
          'C-31, SECTOR-62, NOIDA-201307,\n'
          'MARKETED BY:\n'
          'For EPR details scan the bercode via smart consumer apP-\n'
          'MANUFACTURED BY:\n'
          '%RDA values are based on 2000 kcal diet. † Per Serve\n'
          'size is 20g: 20 Serving in this pack. ##Limit of quantfication\n'
          'Flavouring Substances.\n'
          'HALDIRAM SNACKSs FOOD PRVATE LIMITED,\n'
          'Haldiram - Village Kherki Daula, Delhi - Jaipur\n'
          'Highway, Gurugram -122001, Haryana.\n'
          'HALDIRAM SNACKS FOOD PRVATE LIMİTED\n'
          '(UNIT- HARIOMKAR)\n'
          '%RDA\n'
          'Per Servet\n'
          '20 Km Stone, Kh. No. 409B. 410,411, Village:\n'
          'Gumthala, Tah: Kamptee, Bhand\n'
          '441104';
      final f = extractor.extract(raw);
      expect(f.manufacturer, 'HALDIRAM SNACKSs FOOD PRVATE LIMITED');
      expect(f.manufacturerAddress, contains('Gurugram -122001'));
    });

    test('a footnote after a manufacturer heading is not a manufacturer', () {
      final f = extractor.extract('MARKETED BY:\n'
          'size is 20g; 20 Serving in this pack. ##Limit of quantification\n'
          'For EPR details scan the barcode');
      expect(f.manufacturer, isNull);
      expect(f.manufacturerAddress, isNull);
    });

    test('a phone number is never cut from the FSSAI licence number', () {
      expect(extractor.extract('Lic. No. 10014011001919').consumerCarePhone, isNull);
    });

    test('a licence read with a space inside is one 14-digit licence (scan #19)', () {
      expect(
        extractor.extract('Lic. No. 10014011 001919\nI Lic. No. 10015022004173').fssaiNumber,
        '10014011001919',
      );
      expect(
        extractor.extract('FSS Lic. No. 1001502200173\n8 l904004"400779').fssaiNumber,
        isNull,
        reason: 'one digit short (scan #20), and never joined to the next line',
      );
      expect(extractor.extract('FSSAI Lic. No.\n10014011001919').fssaiNumber,
          '10014011001919');
    });
  });
}
