import '../utils/server_time.dart';

/// Consumer complaint model for filing and tracking.
class ComplaintModel {
  final int id;
  final String complaintNumber;
  final int consumerId;
  final int? productId;
  final String productName;
  final String? brandName;
  final String? storeName;
  final String description;
  final String status;
  final double? latitude;
  final double? longitude;
  final String? resolutionNotes;
  final DateTime createdAt;

  ComplaintModel({
    required this.id,
    required this.complaintNumber,
    required this.consumerId,
    this.productId,
    required this.productName,
    this.brandName,
    this.storeName,
    required this.description,
    required this.status,
    this.latitude,
    this.longitude,
    this.resolutionNotes,
    required this.createdAt,
  });

  factory ComplaintModel.fromJson(Map<String, dynamic> json) {
    return ComplaintModel(
      id: json['id'] as int? ?? 0,
      complaintNumber: json['complaint_number'] as String? ?? '',
      consumerId: json['consumer_id'] as int? ?? 0,
      productId: json['product_id'] as int?,
      productName: json['product_name'] as String? ?? '',
      brandName: json['brand_name'] as String?,
      storeName: json['store_name'] as String?,
      description: json['description'] as String? ?? '',
      status: json['status'] as String? ?? 'submitted',
      latitude: (json['gps_latitude'] as num?)?.toDouble(),
      longitude: (json['gps_longitude'] as num?)?.toDouble(),
      resolutionNotes: json['resolution_notes'] as String?,
      createdAt: parseServerTimeOr(json['created_at']),
    );
  }
}
