import 'package:flutter_test/flutter_test.dart';
import 'package:labelguard_mobile/models/inspection_log_models.dart';
import 'package:labelguard_mobile/models/scan_models.dart';
import 'package:labelguard_mobile/utils/app_colors.dart';
import 'package:labelguard_mobile/utils/verdict.dart';

void main() {
  group('Three verdicts', () {
    test('an unread required detail is shown as NEEDS REVIEW, never compliant', () {
      final r = ScanResponse.fromJson({
        'overall_status': 'needs_review',
        'pin_color': 'amber',
        'action_reason': "Couldn't read: MRP, manufacture date and expiry date. Check them on the pack.",
      });
      expect(r.isCompliant, isFalse);
      expect(r.isActionNeeded, isFalse);
      expect(Verdict.label(r.overallStatus), 'NEEDS REVIEW');
      expect(Verdict.color(r.overallStatus), AppColors.review);
      expect(AppColors.pin(r.pinColor), AppColors.review);
    });

    test('the other two are unchanged', () {
      expect(Verdict.label('action_needed'), 'ACTION NEEDED');
      expect(Verdict.color('action_needed'), AppColors.actionNeeded);
      expect(Verdict.label('compliant'), 'COMPLIANT');
      expect(Verdict.color('compliant'), AppColors.compliant);
      expect(AppColors.pin('red'), AppColors.potentialViolation);
      expect(AppColors.pin('green'), AppColors.compliant);
    });

    test('log rows and details carry the new verdict', () {
      final row = InspectionLogRow.fromJson({
        'evidence_record_id': 41,
        'overall_status': 'needs_review',
        'pin_color': 'amber',
        'timestamp': '2026-09-26T13:09:33+05:30',
      });
      expect(row.isActionNeeded, isFalse);
      expect(Verdict.label(row.overallStatus), 'NEEDS REVIEW');
      final d = InspectionDetail.fromJson({'overall_status': 'needs_review'});
      expect(Verdict.icon(d.overallStatus), Verdict.icon('needs_review'));
    });
  });
}
