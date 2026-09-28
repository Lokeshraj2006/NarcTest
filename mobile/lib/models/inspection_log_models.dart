import '../utils/server_time.dart';
import 'scan_models.dart';

/// Row in GET /inspections/log — for the inspector dashboard table.
class InspectionLogRow {
  final int evidenceRecordId;
  final int complianceResultId;
  final String? productName;
  final DateTime timestamp;
  final double? gpsLatitude;
  final double? gpsLongitude;
  final String overallStatus;
  final String? actionReason;
  final String pinColor;
  // Who scanned it, and its audit flags.
  final int? capturedById;
  final String? capturedByUsername;
  final String? capturedByRole;
  final String? complaintNumber;
  final String? complaintStatus;
  final int? rescanOfId;
  final int? duplicateOfId;
  /// Fields the user changed from the OCR reading; null = not recorded.
  final List<String>? editedFields;

  InspectionLogRow({
    required this.evidenceRecordId,
    required this.complianceResultId,
    this.productName,
    required this.timestamp,
    this.gpsLatitude,
    this.gpsLongitude,
    required this.overallStatus,
    this.actionReason,
    required this.pinColor,
    this.capturedById,
    this.capturedByUsername,
    this.capturedByRole,
    this.complaintNumber,
    this.complaintStatus,
    this.rescanOfId,
    this.duplicateOfId,
    this.editedFields,
  });

  factory InspectionLogRow.fromJson(Map<String, dynamic> json) {
    return InspectionLogRow(
      evidenceRecordId: json['evidence_record_id'] as int? ?? 0,
      complianceResultId: json['compliance_result_id'] as int? ?? 0,
      productName: json['product_name'] as String?,
      timestamp: parseServerTimeOr(json['timestamp']),
      gpsLatitude: (json['gps_latitude'] as num?)?.toDouble(),
      gpsLongitude: (json['gps_longitude'] as num?)?.toDouble(),
      overallStatus: json['overall_status'] as String? ?? 'compliant',
      actionReason: json['action_reason'] as String?,
      pinColor: json['pin_color'] as String? ?? 'green',
      capturedById: json['captured_by_id'] as int?,
      capturedByUsername: json['captured_by_username'] as String?,
      capturedByRole: json['captured_by_role'] as String?,
      complaintNumber: json['complaint_number'] as String?,
      complaintStatus: json['complaint_status'] as String?,
      rescanOfId: json['rescan_of_id'] as int?,
      duplicateOfId: json['duplicate_of_id'] as int?,
      editedFields: (json['edited_fields'] as List<dynamic>?)
          ?.whereType<String>()
          .toList(),
    );
  }

  bool get isActionNeeded => overallStatus == 'action_needed';
}

List<int> _ids(Object? value) => value is List
    ? value.whereType<num>().map((n) => n.toInt()).toList()
    : const [];

/// One rule check in the detail view.
class RuleCheckDetail {
  final int id;
  final int ruleNumber;
  final String ruleName;
  final String ruleCode;
  final String statutoryReference;
  final String status;
  final double? score;
  final String? detectedValue;
  final String? requiredValue;
  final String? failureReason;

  RuleCheckDetail({
    required this.id,
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

  factory RuleCheckDetail.fromJson(Map<String, dynamic> json) {
    return RuleCheckDetail(
      id: json['id'] as int? ?? 0,
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

  bool get isFail => status.toUpperCase() == 'FAIL';
  bool get isPass => status.toUpperCase() == 'PASS';
}

class EvidenceMetaModel {
  final int id;
  final String sha256Hash;
  final String filePath;
  final String originalFilename;
  final double? gpsLatitude;
  final double? gpsLongitude;
  final DateTime timestampDevice;
  final DateTime? timestampNtp;
  final double? ntpDriftSeconds;
  final bool isTampered;
  final double? gpsAccuracyMeters;

  EvidenceMetaModel({
    required this.id,
    required this.sha256Hash,
    required this.filePath,
    required this.originalFilename,
    this.gpsLatitude,
    this.gpsLongitude,
    required this.timestampDevice,
    this.timestampNtp,
    this.ntpDriftSeconds,
    this.isTampered = false,
    this.gpsAccuracyMeters,
  });

  factory EvidenceMetaModel.fromJson(Map<String, dynamic> json) {
    return EvidenceMetaModel(
      id: json['id'] as int? ?? 0,
      sha256Hash: json['sha256_hash'] as String? ?? '',
      filePath: json['file_path'] as String? ?? '',
      originalFilename: json['original_filename'] as String? ?? '',
      gpsLatitude: (json['gps_latitude'] as num?)?.toDouble(),
      gpsLongitude: (json['gps_longitude'] as num?)?.toDouble(),
      timestampDevice: parseServerTimeOr(json['timestamp_device']),
      timestampNtp: parseServerTime(json['timestamp_ntp']),
      ntpDriftSeconds: (json['ntp_drift_seconds'] as num?)?.toDouble(),
      isTampered: json['is_tampered'] as bool? ?? false,
      gpsAccuracyMeters: (json['gps_accuracy_meters'] as num?)?.toDouble(),
    );
  }
}

class InspectionDetail {
  final int evidenceRecordId;
  final int complianceResultId;
  final String overallStatus;
  final String? actionReason;
  final String? lawReference;
  final String? productName;
  final int totalChecks;
  final int failedChecks;
  final List<RuleCheckDetail> ruleChecks;
  final String? barcode;
  final String? barcodeSource;
  final AuthenticityResultModel? authenticity;
  final FssaiMarkModel? fssaiMark;
  final GstinModel gstin;
  final EvidenceMetaModel evidence;
  final List<int> failedRuleCheckIds;
  final bool hasViolationReport;
  final int? violationReportId;
  final String? violationReportNumber;
  final String? violationReportStatus;
  // Who scanned it, and how it relates to other scans.
  final String? capturedByUsername;
  final String? capturedByRole;
  final int? complaintId;
  final String? complaintNumber;
  final String? complaintStatus;
  final int? rescanOfId;
  final List<int> rescanIds;
  final int? duplicateOfId;
  final List<int> samePhotoIds;
  /// Fields changed from the OCR reading; null = not recorded for this scan.
  final List<EditedField>? editedFields;

  InspectionDetail({
    required this.evidenceRecordId,
    required this.complianceResultId,
    required this.overallStatus,
    this.actionReason,
    this.lawReference,
    this.productName,
    required this.totalChecks,
    required this.failedChecks,
    required this.ruleChecks,
    this.barcode,
    this.barcodeSource,
    this.authenticity,
    this.fssaiMark,
    required this.gstin,
    required this.evidence,
    this.failedRuleCheckIds = const [],
    this.hasViolationReport = false,
    this.violationReportId,
    this.violationReportNumber,
    this.violationReportStatus,
    this.capturedByUsername,
    this.capturedByRole,
    this.complaintId,
    this.complaintNumber,
    this.complaintStatus,
    this.rescanOfId,
    this.rescanIds = const [],
    this.duplicateOfId,
    this.samePhotoIds = const [],
    this.editedFields,
  });

  factory InspectionDetail.fromJson(Map<String, dynamic> json) {
    return InspectionDetail(
      evidenceRecordId: json['evidence_record_id'] as int? ?? 0,
      complianceResultId: json['compliance_result_id'] as int? ?? 0,
      overallStatus: json['overall_status'] as String? ?? 'compliant',
      actionReason: json['action_reason'] as String?,
      lawReference: json['law_reference'] as String?,
      productName: json['product_name'] as String?,
      totalChecks: json['total_checks'] as int? ?? 0,
      failedChecks: json['failed_checks'] as int? ?? 0,
      ruleChecks: (json['rule_checks'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(RuleCheckDetail.fromJson)
          .toList(),
      barcode: json['barcode'] as String?,
      barcodeSource: json['barcode_source'] as String?,
      authenticity: json['authenticity'] is Map<String, dynamic>
          ? AuthenticityResultModel.fromJson(
              json['authenticity'] as Map<String, dynamic>)
          : null,
      fssaiMark: json['fssai_mark'] is Map<String, dynamic>
          ? FssaiMarkModel.fromJson(json['fssai_mark'] as Map<String, dynamic>)
          : null,
      gstin: json['gstin'] is Map<String, dynamic>
          ? GstinModel.fromJson(json['gstin'] as Map<String, dynamic>)
          : GstinModel(status: 'NOT_RUN'),
      evidence: EvidenceMetaModel.fromJson(
          json['evidence'] as Map<String, dynamic>? ?? const {}),
      failedRuleCheckIds:
          (json['failed_rule_check_ids'] as List<dynamic>? ?? [])
              .map((e) => (e as num).toInt())
              .toList(),
      hasViolationReport: json['has_violation_report'] as bool? ?? false,
      violationReportId: json['violation_report_id'] as int?,
      violationReportNumber: json['violation_report_number'] as String?,
      violationReportStatus: json['violation_report_status'] as String?,
      capturedByUsername: json['captured_by_username'] as String?,
      capturedByRole: json['captured_by_role'] as String?,
      complaintId: json['complaint_id'] as int?,
      complaintNumber: json['complaint_number'] as String?,
      complaintStatus: json['complaint_status'] as String?,
      rescanOfId: json['rescan_of_id'] as int?,
      rescanIds: _ids(json['rescan_ids']),
      duplicateOfId: json['duplicate_of_id'] as int?,
      samePhotoIds: _ids(json['same_photo_ids']),
      editedFields: EditedField.listFromJson(json['edited_fields']),
    );
  }

  bool get isActionNeeded => overallStatus == 'action_needed';
}
