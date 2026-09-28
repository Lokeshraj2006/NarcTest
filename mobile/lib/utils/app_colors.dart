/// Central colour palette for the app.
///
/// Change a colour here and it updates everywhere it is used.
/// Ported from the legal_metrology_compliance_scanner prototype and
/// extended with the verdict colours FieldProof's backend returns
/// (`compliant` / `needs_review` / `action_needed`) plus map pin colours.
library;

import 'package:flutter/material.dart';

class AppColors {
  AppColors._();

  /// Primary brand colour. Used for app bars and main buttons.
  static const Color primary = Color(0xFF1E3A8A); // deep blue

  /// Secondary accent. Used for highlights and icons.
  static const Color accent = Color(0xFFF59E0B); // amber

  /// Inspector-facing surfaces (darker, more authoritative).
  static const Color inspectorPrimary = Color(0xFF0F172A); // slate 900

  /// Status colours used for compliance results.
  static const Color compliant = Color(0xFF15803D); // green
  static const Color potentialViolation = Color(0xFFDC2626); // red
  static const Color review = Color(0xFFB45309); // orange
  static const Color exempt = Color(0xFF6B7280); // grey

  /// Backend's two-state verdict (`overall_status`).
  static const Color actionNeeded = potentialViolation;

  /// Authenticity verdicts from the product registry cross-check.
  static const Color authentic = compliant;
  static const Color tampered = potentialViolation;
  static const Color unverified = exempt;

  /// Neutral background.
  static const Color background = Color(0xFFF9FAFB);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color border = Color(0xFFE5E7EB);

  /// Default text colours.
  static const Color textPrimary = Color(0xFF111827);
  static const Color textSecondary = Color(0xFF6B7280);

  /// FieldProof test result colours.
  static const Color positive = Color(0xFFD32F2F); // red
  static const Color negative = Color(0xFF2E7D32); // green
  static const Color inconclusive = Color(0xFF6A1B9A); // purple

  static Color forResult(String result) => switch (result.toUpperCase()) {
        'POSITIVE' => positive,
        'NEGATIVE' => negative,
        _ => inconclusive,
      };

  static String resultTitle(String result) => switch (result.toUpperCase()) {
        'POSITIVE' => 'POSITIVE',
        'NEGATIVE' => 'NEGATIVE',
        _ => 'NOT SURE (INCONCLUSIVE)',
      };

  /// Map pin colour for a given backend `pin_color` string.
  static Color pin(String pinColor) => switch (pinColor) {
        'red' => potentialViolation,
        'amber' => review,
        _ => compliant,
      };

  /// Colour for a backend `overall_status` value.
  static Color forOverallStatus(String status) => switch (status) {
        'action_needed' => actionNeeded,
        'needs_review' => review,
        _ => compliant,
      };

  /// Colour for an individual RuleCheck status.
  static Color forCheckStatus(String status) {
    switch (status.toUpperCase()) {
      case 'PASS':
        return compliant;
      case 'FAIL':
        return potentialViolation;
      case 'EXEMPT':
        return exempt;
      default:
        return review;
    }
  }
}
