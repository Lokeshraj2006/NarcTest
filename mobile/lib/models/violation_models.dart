/// Models for the inspector -> admin escalation chain.
library;

class ViolatedRule {
  /// The check's number; null for a registry mismatch (Rule 6(3)).
  final int? ruleNumber;
  final String ruleCode;
  final String ruleName;
  final String statutoryReference;
  final String? detectedValue;
  final String? requiredValue;
  final String? failureReason;

  /// "rule" (a failed check) or "registry" (checked on the pack).
  final String source;

  ViolatedRule({
    required this.ruleNumber,
    required this.ruleCode,
    required this.ruleName,
    required this.statutoryReference,
    this.detectedValue,
    this.requiredValue,
    this.failureReason,
    this.source = 'rule',
  });

  factory ViolatedRule.fromJson(Map<String, dynamic> json) => ViolatedRule(
        ruleNumber: json['rule_number'] as int?,
        ruleCode: json['rule_code'] as String? ?? '',
        ruleName: json['rule_name'] as String? ?? '',
        statutoryReference: json['statutory_reference'] as String? ?? '',
        detectedValue: json['detected_value'] as String?,
        requiredValue: json['required_value'] as String?,
        failureReason: json['failure_reason'] as String?,
        source: json['source'] as String? ?? 'rule',
      );

  bool get isRegistry => source == 'registry';
}

class ViolationReportResult {
  final int id;
  final String reportNumber;
  final String status;
  final String severity;
  final String? productName;
  final String? shopName;
  final int violatedRuleCount;
  final List<ViolatedRule> violatedRules;
  final String? inspectorName;
  final String? inspectorBadge;

  ViolationReportResult({
    required this.id,
    required this.reportNumber,
    required this.status,
    required this.severity,
    this.productName,
    this.shopName,
    this.violatedRuleCount = 0,
    this.violatedRules = const [],
    this.inspectorName,
    this.inspectorBadge,
  });

  factory ViolationReportResult.fromJson(Map<String, dynamic> json) {
    return ViolationReportResult(
      id: json['id'] as int? ?? 0,
      reportNumber: json['report_number'] as String? ?? '',
      status: json['status'] as String? ?? '',
      severity: json['severity'] as String? ?? 'moderate',
      productName: json['product_name'] as String?,
      shopName: json['shop_name'] as String?,
      violatedRuleCount: json['violated_rule_count'] as int? ?? 0,
      violatedRules: (json['violated_rules'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(ViolatedRule.fromJson)
          .toList(),
      inspectorName: json['inspector_name'] as String?,
      inspectorBadge: json['inspector_badge'] as String?,
    );
  }

  /// Human-readable state for the confirmation screen.
  String get statusLabel => status.replaceAll('_', ' ');
}
