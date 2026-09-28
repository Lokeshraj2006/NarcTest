import '../utils/server_time.dart';

/// Inspection model for inspectors to track assigned tasks.
class InspectionModel {
  final int id;
  final String inspectionNumber;
  final int inspectorId;
  final int? productId;
  final String status;
  final String complianceStatus;
  final String? locationName;
  final String? storeOrMarket;
  final double? latitude;
  final double? longitude;
  final String? notes;
  final DateTime createdAt;

  InspectionModel({
    required this.id,
    required this.inspectionNumber,
    required this.inspectorId,
    this.productId,
    required this.status,
    required this.complianceStatus,
    this.locationName,
    this.storeOrMarket,
    this.latitude,
    this.longitude,
    this.notes,
    required this.createdAt,
  });

  factory InspectionModel.fromJson(Map<String, dynamic> json) {
    return InspectionModel(
      id: json['id'] as int? ?? 0,
      inspectionNumber: json['inspection_number'] as String? ?? '',
      inspectorId: json['inspector_id'] as int? ?? 0,
      productId: json['product_id'] as int?,
      status: json['status'] as String? ?? 'scheduled',
      complianceStatus: json['compliance_status'] as String? ?? 'pending',
      locationName: json['location_name'] as String?,
      storeOrMarket: json['store_or_market'] as String?,
      latitude: (json['gps_latitude'] as num?)?.toDouble(),
      longitude: (json['gps_longitude'] as num?)?.toDouble(),
      notes: json['notes'] as String?,
      createdAt: parseServerTimeOr(json['created_at']),
    );
  }
}
