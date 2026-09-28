import 'package:flutter/material.dart';

import 'app_colors.dart';

/// The three results a scan can have, from the server's `overall_status`.
///
/// `needs_review`: no evidence of a violation, but a required detail (MRP,
/// dates, quantity, maker…) couldn't be read, so the pack isn't shown as
/// compliant. It raises no complaint on its own; a person checks the pack.
class Verdict {
  Verdict._();

  static const actionNeeded = 'action_needed';
  static const needsReview = 'needs_review';

  static String label(String status) => switch (status) {
        actionNeeded => 'ACTION NEEDED',
        needsReview => 'NEEDS REVIEW',
        _ => 'COMPLIANT',
      };

  static Color color(String status) => switch (status) {
        actionNeeded => AppColors.actionNeeded,
        needsReview => AppColors.review,
        _ => AppColors.compliant,
      };

  static IconData icon(String status) => switch (status) {
        actionNeeded => Icons.report_problem,
        needsReview => Icons.help_outline,
        _ => Icons.verified,
      };

  /// Small glyph for a map pin.
  static IconData pinGlyph(String status) => switch (status) {
        actionNeeded => Icons.priority_high,
        needsReview => Icons.question_mark,
        _ => Icons.check,
      };
}
