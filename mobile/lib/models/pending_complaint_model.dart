import '../utils/server_time.dart';

/// Row in GET /complaints/pending — for the inspector's pending queue.
class PendingComplaintRow {
  final int complaintId;
  final int? evidenceRecordId;
  final String? productName;
  final String? overallStatus;
  final String? actionReason;
  final double? gpsLatitude;
  final double? gpsLongitude;
  final DateTime filedAt;
  final String status;

  PendingComplaintRow({
    required this.complaintId,
    this.evidenceRecordId,
    this.productName,
    this.overallStatus,
    this.actionReason,
    this.gpsLatitude,
    this.gpsLongitude,
    required this.filedAt,
    required this.status,
  });

  factory PendingComplaintRow.fromJson(Map<String, dynamic> json) {
    return PendingComplaintRow(
      complaintId: json['complaint_id'] as int? ?? 0,
      evidenceRecordId: json['evidence_record_id'] as int?,
      productName: json['product_name'] as String?,
      overallStatus: json['overall_status'] as String?,
      actionReason: json['action_reason'] as String?,
      gpsLatitude: (json['gps_latitude'] as num?)?.toDouble(),
      gpsLongitude: (json['gps_longitude'] as num?)?.toDouble(),
      filedAt: parseServerTimeOr(json['filed_at']),
      status: json['status'] as String? ?? 'pending_inspector_review',
    );
  }
}
