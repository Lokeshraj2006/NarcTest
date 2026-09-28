import '../utils/server_time.dart';

/// Compliance outcome status enum
enum ComplianceStatus {
  compliant,
  violation,
  reviewNeeded,
  exempt,
  pending;

  static ComplianceStatus fromString(String status) {
    switch (status.toLowerCase()) {
      case 'compliant':
        return ComplianceStatus.compliant;
      case 'violation':
        return ComplianceStatus.violation;
      case 'review':
      case 'review_needed':
        return ComplianceStatus.reviewNeeded;
      case 'exempt':
        return ComplianceStatus.exempt;
      default:
        return ComplianceStatus.pending;
    }
  }

  String toDisplayName() {
    switch (this) {
      case ComplianceStatus.compliant:
        return 'Compliant';
      case ComplianceStatus.violation:
        return 'Violation Detected';
      case ComplianceStatus.reviewNeeded:
        return 'Manual Review Needed';
      case ComplianceStatus.exempt:
        return 'Exempt from Rules';
      case ComplianceStatus.pending:
        return 'Processing...';
    }
  }
}

/// Single rule check result out of the 13 rules
class RuleCheckResult {
  final int ruleNumber;
  final String ruleName;
  final String ruleCode;
  final String statutoryReference;
  final String status; // PASS, FAIL, REVIEW, EXEMPT
  final double? score;
  final String? detectedValue;
  final String? requiredValue;
  final String? failureReason;

  RuleCheckResult({
    required this.ruleNumber,
    required this.ruleName,
    required this.ruleCode,
    required this.statutoryReference,
    required this.status,
    this.score,
    this.detectedValue,
    this.requiredValue,
    this.failureReason,
  });

  factory RuleCheckResult.fromJson(Map<String, dynamic> json) {
    return RuleCheckResult(
      ruleNumber: json['rule_number'] as int? ?? 0,
      ruleName: json['rule_name'] as String? ?? '',
      ruleCode: json['rule_code'] as String? ?? '',
      statutoryReference: json['statutory_reference'] as String? ?? '',
      status: json['status'] as String? ?? 'REVIEW',
      score: (json['score'] as num?)?.toDouble(),
      detectedValue: json['detected_value'] as String?,
      requiredValue: json['required_value'] as String?,
      failureReason: json['failure_reason'] as String?,
    );
  }

  bool get isPass => status.toUpperCase() == 'PASS';
  bool get isFail => status.toUpperCase() == 'FAIL';
  bool get isReview => status.toUpperCase() == 'REVIEW';
  bool get isExempt => status.toUpperCase() == 'EXEMPT';
}

/// Full product compliance report returned by backend
class ComplianceReport {
  final int productId;
  final String genericName;
  final String? brandName;
  final ComplianceStatus status;
  final List<RuleCheckResult> ruleChecks;
  final String? summary;
  final DateTime evaluatedAt;

  ComplianceReport({
    required this.productId,
    required this.genericName,
    this.brandName,
    required this.status,
    required this.ruleChecks,
    this.summary,
    required this.evaluatedAt,
  });

  factory ComplianceReport.fromJson(Map<String, dynamic> json) {
    final checks = (json['rule_checks'] as List<dynamic>? ?? [])
        .map((e) => RuleCheckResult.fromJson(e as Map<String, dynamic>))
        .toList();

    return ComplianceReport(
      productId: json['product_id'] as int? ?? 0,
      genericName: json['generic_name'] as String? ?? 'Unknown Product',
      brandName: json['brand_name'] as String?,
      status: ComplianceStatus.fromString(json['status'] as String? ?? 'pending'),
      ruleChecks: checks,
      summary: json['summary'] as String?,
      evaluatedAt: parseServerTimeOr(json['evaluated_at']),
    );
  }
}
