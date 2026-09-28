import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:labelguard_mobile/models/inspection_log_models.dart';
import 'package:labelguard_mobile/models/scan_models.dart';
import 'package:labelguard_mobile/models/violation_models.dart';
import 'package:labelguard_mobile/screens/inspector/file_report_screen.dart';

/// A scan with no failed checks whose registry cross-check flagged tampering.
InspectionDetail _tamperedScan({
  String status = 'tampered_suspected',
  List<Map<String, dynamic>> mismatches = const [
    {'field': 'mrp', 'expected': '109.0', 'detected': '129.0'},
  ],
  List<Map<String, dynamic>> ruleChecks = const [
    {'id': 1, 'rule_number': 4, 'rule_name': 'Net quantity', 'status': 'PASS'},
  ],
}) =>
    InspectionDetail.fromJson({
      'evidence_record_id': 44,
      'overall_status': 'action_needed',
      'rule_checks': ruleChecks,
      'authenticity': {'status': status, 'mismatches': mismatches},
      'evidence': {'sha256_hash': 'ab' * 32},
    });

Future<void> _open(WidgetTester tester, InspectionDetail d) async {
  await tester.pumpWidget(MaterialApp(home: FileReportScreen(detail: d)));
}

FilledButton _submitButton(WidgetTester tester) =>
    tester.widget<FilledButton>(find.byWidgetPredicate((w) => w is FilledButton));

void main() {
  group('Registry mismatches an inspector may cite (Rule 6(3))', () {
    test('only Legal Metrology declarations on a tampering flag', () {
      final a = AuthenticityResultModel.fromJson({
        'status': 'tampered_suspected',
        'mismatches': [
          {'field': 'mrp', 'expected': '109.0', 'detected': '129.0'},
          {'field': 'fssai_license_number', 'expected': '1', 'detected': '2'},
        ],
      });
      expect(a.citableMismatches.map((m) => m.label), ['MRP']);
    });

    test('nothing on an authentic scan, such as one with a lower MRP', () {
      final a = AuthenticityResultModel.fromJson({
        'status': 'verified_authentic',
        'mismatches': const [],
      });
      expect(a.citableMismatches, isEmpty);
    });

    test('a lower MRP stored as tampering on an older scan is not citable', () {
      // Scan #43: the MRP was hidden and 9.31 was read against a registered 109.
      final a = AuthenticityResultModel.fromJson({
        'status': 'tampered_suspected',
        'mismatches': [
          {'field': 'mrp', 'expected': '109.0', 'detected': '9.31'},
        ],
      });
      expect(a.citableMismatches, isEmpty);
    });

    test('a registry ground in a filed report has no rule number', () {
      final r = ViolatedRule.fromJson({
        'rule_number': null,
        'rule_code': 'REGISTRY_MISMATCH',
        'rule_name': 'MRP differs from the registered product',
        'statutory_reference': 'Rule 6(3), Legal Metrology (Packaged '
            'Commodities) Rules, 2011',
        'source': 'registry',
      });
      expect(r.ruleNumber, isNull);
      expect(r.isRegistry, isTrue);
    });

    test('reports filed before registry grounds still read as rule checks', () {
      final r = ViolatedRule.fromJson({'rule_number': 5, 'rule_code': 'MRP'});
      expect(r.ruleNumber, 5);
      expect(r.isRegistry, isFalse);
    });
  });

  group('File report screen', () {
    testWidgets('a tampering flag waits for the pack check', (tester) async {
      await _open(tester, _tamperedScan());

      expect(find.text('Registry mismatch · Rule 6(3)'), findsOneWidget);
      expect(find.textContaining('label shows 129.0, registered 109.0'),
          findsOneWidget);
      expect(find.text('Check the pack first'), findsOneWidget);
      expect(_submitButton(tester).onPressed, isNull);

      await tester.tap(find.byType(Checkbox));
      await tester.pump();

      expect(find.text('File report (1 violation)'), findsOneWidget);
      expect(_submitButton(tester).onPressed, isNotNull);
    });

    testWidgets('failed checks can be filed with or without the registry',
        (tester) async {
      await _open(
        tester,
        _tamperedScan(ruleChecks: const [
          {'id': 1, 'rule_number': 4, 'rule_name': 'Net quantity',
           'status': 'FAIL', 'failure_reason': 'Net quantity not declared'},
        ]),
      );
      expect(find.text('File report (1 violation)'), findsOneWidget);
      expect(_submitButton(tester).onPressed, isNotNull);

      await tester.tap(find.byType(Checkbox));
      await tester.pump();
      expect(find.text('File report (2 violations)'), findsOneWidget);
    });

    testWidgets('an authentic scan with no failures has nothing to file',
        (tester) async {
      await _open(tester, _tamperedScan(status: 'verified_authentic',
          mismatches: const []));

      expect(find.text('Registry mismatch · Rule 6(3)'), findsNothing);
      expect(find.text('No failed checks on this scan'), findsOneWidget);
      expect(_submitButton(tester).onPressed, isNull);
    });
  });
}
