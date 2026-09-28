/// Client-side models for the POST /scan endpoint.
library;

class OcrFields {
  String? productName;
  String? manufacturerName;
  String? manufacturerAddress;
  double? mrp;
  String? netQuantity;
  String? fssaiLicenseNumber;
  String? gstNumber;
  String? mfgDate;
  String? expiryDate;
  String? countryOfOrigin;
  // Rule 8 — consumer care contact details
  String? consumerCarePhone;
  String? consumerCareEmail;
  // Rule 12 — LMPC registration number
  String? lmpcNumber;
  String? batchNumber;
  // Rule 5 scans the full OCR text for the mandatory "inclusive of all
  // taxes" wording, which field-level extraction routinely misses.
  String? rawText;

  OcrFields({
    this.productName,
    this.manufacturerName,
    this.manufacturerAddress,
    this.mrp,
    this.netQuantity,
    this.fssaiLicenseNumber,
    this.gstNumber,
    this.mfgDate,
    this.expiryDate,
    this.countryOfOrigin,
    this.consumerCarePhone,
    this.consumerCareEmail,
    this.lmpcNumber,
    this.batchNumber,
    this.rawText,
  });

  Map<String, dynamic> toJson() {
    final map = <String, dynamic>{};
    if (productName != null) map['product_name'] = productName;
    if (manufacturerName != null) map['manufacturer_name'] = manufacturerName;
    if (manufacturerAddress != null) map['manufacturer_address'] = manufacturerAddress;
    if (mrp != null) map['mrp'] = mrp;
    if (netQuantity != null) map['net_quantity'] = netQuantity;
    if (fssaiLicenseNumber != null) map['fssai_license_number'] = fssaiLicenseNumber;
    if (gstNumber != null) map['gst_number'] = gstNumber;
    if (mfgDate != null) map['mfg_date'] = mfgDate;
    if (expiryDate != null) map['expiry_date'] = expiryDate;
    if (countryOfOrigin != null) map['country_of_origin'] = countryOfOrigin;
    if (consumerCarePhone != null) map['consumer_care_phone'] = consumerCarePhone;
    if (consumerCareEmail != null) map['consumer_care_email'] = consumerCareEmail;
    if (lmpcNumber != null) map['lmpc_number'] = lmpcNumber;
    if (batchNumber != null) map['batch_number'] = batchNumber;
    if (rawText != null) map['raw_text'] = rawText;
    return map;
  }
}

/// One OCR text block with its pixel geometry.
///
/// The backend measures these heights against the barcode's known physical
/// width to decide rule 9 (font size) — without them that rule cannot be
/// evaluated and stays at REVIEW.
class OcrTextBlockGeometry {
  final String text;
  final double x;
  final double y;
  final double width;
  final double height;

  OcrTextBlockGeometry({
    required this.text,
    required this.x,
    required this.y,
    required this.width,
    required this.height,
  });

  Map<String, dynamic> toJson() => {
        'text': text,
        'x': x,
        'y': y,
        'width': width,
        'height': height,
      };
}

class ScanContext {
  final String? barcode;
  final double? gpsLatitude;
  final double? gpsLongitude;
  final double? gpsAccuracyMeters;
  final OcrFields ocrFields;
  final String? sellerName;
  final String? sellerAddress;
  final List<int>? fssaiRegion;
  final bool? isImported;

  // Chain of custody — proves when the capture happened, not merely when the
  // server received it.
  final DateTime? deviceTimestamp;
  final DateTime? ntpTimestamp;
  final double? ntpDriftSeconds;

  // Calibration inputs for rules 9-11.
  final List<double>? barcodeBbox;
  final String? barcodeFormat;
  final List<OcrTextBlockGeometry>? textBlocks;
  final int? imageWidthPx;
  final int? imageHeightPx;

  // Audit context: the scan this one repeats, and what OCR read before the
  // user corrected anything.
  final int? rescanOfId;
  final OcrFields? extractedFields;

  ScanContext({
    this.barcode,
    this.gpsLatitude,
    this.gpsLongitude,
    this.gpsAccuracyMeters,
    OcrFields? ocrFields,
    this.sellerName,
    this.sellerAddress,
    this.fssaiRegion,
    this.isImported,
    this.deviceTimestamp,
    this.ntpTimestamp,
    this.ntpDriftSeconds,
    this.barcodeBbox,
    this.barcodeFormat,
    this.textBlocks,
    this.imageWidthPx,
    this.imageHeightPx,
    this.rescanOfId,
    this.extractedFields,
  }) : ocrFields = ocrFields ?? OcrFields();

  Map<String, dynamic> toJson() => {
        if (barcode != null) 'barcode': barcode,
        if (gpsLatitude != null) 'gps_latitude': gpsLatitude,
        if (gpsLongitude != null) 'gps_longitude': gpsLongitude,
        if (gpsAccuracyMeters != null) 'gps_accuracy_meters': gpsAccuracyMeters,
        'ocr_fields': ocrFields.toJson(),
        if (sellerName != null) 'seller_name': sellerName,
        if (sellerAddress != null) 'seller_address': sellerAddress,
        if (fssaiRegion != null) 'fssai_region': fssaiRegion,
        if (isImported != null) 'is_imported': isImported,
        // Always sent as UTC ISO-8601 so the server never has to guess a zone.
        if (deviceTimestamp != null)
          'device_timestamp': deviceTimestamp!.toUtc().toIso8601String(),
        if (ntpTimestamp != null)
          'ntp_timestamp': ntpTimestamp!.toUtc().toIso8601String(),
        if (ntpDriftSeconds != null) 'ntp_drift_seconds': ntpDriftSeconds,
        if (barcodeBbox != null) 'barcode_bbox': barcodeBbox,
        if (barcodeFormat != null) 'barcode_format': barcodeFormat,
        if (textBlocks != null)
          'text_blocks': textBlocks!.map((b) => b.toJson()).toList(),
        if (imageWidthPx != null) 'image_width_px': imageWidthPx,
        if (imageHeightPx != null) 'image_height_px': imageHeightPx,
        if (rescanOfId != null) 'rescan_of_id': rescanOfId,
        if (extractedFields != null) 'extracted_fields': extractedFields!.toJson(),
      };
}

class AuthenticityMismatch {
  final String field;
  final String? expected;
  final String? detected;
  final String? note;

  AuthenticityMismatch({
    required this.field,
    this.expected,
    this.detected,
    this.note,
  });

  factory AuthenticityMismatch.fromJson(Map<String, dynamic> json) =>
      AuthenticityMismatch(
        field: json['field'] as String? ?? '',
        expected: json['expected'] as String?,
        detected: json['detected'] as String?,
        note: json['note'] as String?,
      );

  /// Registry mismatches a report may cite under Rule 6(3): Legal Metrology
  /// declarations only. A licence, veg mark or GSTIN isn't one. Mirrors
  /// `_CITABLE_REGISTRY_FIELDS` in the backend's violation_service.
  static const citableLabels = {
    'mrp': 'MRP',
    'net_quantity': 'Net quantity',
    'manufacturer_name': 'Manufacturer',
  };

  String get label => citableLabels[field] ?? field;

  /// A price below the registered MRP: allowed under Rule 6(3) (a sticker
  /// may lower it). Scans saved before the server checked the direction
  /// (#43) still list one as a mismatch.
  bool get isLowerMrp {
    if (field != 'mrp') return false;
    final shown = _price(detected), registered = _price(expected);
    return shown != null && registered != null && shown < registered;
  }

  static double? _price(String? raw) {
    final m = RegExp(r'\d+(?:\.\d+)?').firstMatch((raw ?? '').replaceAll(',', ''));
    return m == null ? null : double.tryParse(m.group(0)!);
  }
}

class AuthenticityResultModel {
  final String status;
  final String? matchedProductName;
  final int? registryId;
  final String message;
  final List<AuthenticityMismatch> mismatches;

  AuthenticityResultModel({
    required this.status,
    this.matchedProductName,
    this.registryId,
    this.message = '',
    this.mismatches = const [],
  });

  factory AuthenticityResultModel.fromJson(Map<String, dynamic> json) {
    final list = (json['mismatches'] as List<dynamic>? ?? [])
        .whereType<Map<String, dynamic>>()
        .map(AuthenticityMismatch.fromJson)
        .toList();
    return AuthenticityResultModel(
      status: json['status'] as String? ?? 'unverified_product',
      matchedProductName: json['matched_product_name'] as String?,
      registryId: json['registry_id'] as int?,
      message: json['message'] as String? ?? '',
      mismatches: list,
    );
  }

  bool get isAuthentic => status == 'verified_authentic';
  bool get isTampered => status == 'tampered_suspected';
  bool get isUnverified => status == 'unverified_product';

  /// What an inspector may cite in a report once they've checked the pack.
  /// A lower MRP never appears here: the server records it as a divergence,
  /// since Rule 6(3) allows a sticker that lowers the MRP.
  List<AuthenticityMismatch> get citableMismatches => isTampered
      ? mismatches
          .where((m) =>
              AuthenticityMismatch.citableLabels.containsKey(m.field) &&
              !m.isLowerMrp)
          .toList()
      : const [];
}

class FssaiMarkModel {
  final String status;
  final double confidence;
  final double greenPixelRatio;
  final double redPixelRatio;
  final List<int>? detectedRegion;
  final String message;

  /// Photo the mark was found on: 0 = the main photo, 1.. = extra photos.
  final int? photo;
  final int photosChecked;

  FssaiMarkModel({
    required this.status,
    this.confidence = 0.0,
    this.greenPixelRatio = 0.0,
    this.redPixelRatio = 0.0,
    this.detectedRegion,
    this.message = '',
    this.photo,
    this.photosChecked = 1,
  });

  factory FssaiMarkModel.fromJson(Map<String, dynamic> json) => FssaiMarkModel(
        status: json['status'] as String? ?? 'not_found',
        confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
        greenPixelRatio: (json['green_pixel_ratio'] as num?)?.toDouble() ?? 0.0,
        redPixelRatio: (json['red_pixel_ratio'] as num?)?.toDouble() ?? 0.0,
        detectedRegion: (json['detected_region'] as List<dynamic>?)
            ?.map((e) => (e as num).toInt())
            .toList(),
        message: json['message'] as String? ?? '',
        photo: (json['photo'] as num?)?.toInt(),
        photosChecked: (json['photos_checked'] as num?)?.toInt() ?? 1,
      );

  /// "the main photo" / "extra photo 2", when more than one was checked.
  String? get foundOn {
    if (photo == null || photosChecked < 2) return null;
    return photo == 0 ? 'the main photo' : 'extra photo $photo';
  }
}

class GstinModel {
  final String status;
  final String? detectedValue;
  final String? failureReason;
  final String note;

  GstinModel({
    required this.status,
    this.detectedValue,
    this.failureReason,
    this.note =
        'Format/checksum only — not a live GST Council registry lookup.',
  });

  factory GstinModel.fromJson(Map<String, dynamic> json) => GstinModel(
        status: json['status'] as String? ?? 'NOT_RUN',
        detectedValue: json['detected_value'] as String?,
        failureReason: json['failure_reason'] as String?,
        note: json['note'] as String? ??
            'Format/checksum only — not a live GST Council registry lookup.',
      );
}

/// A label field the user changed from what OCR read, before submitting.
class EditedField {
  final String field;
  final Object? extracted;
  final Object? submitted;

  const EditedField({required this.field, this.extracted, this.submitted});

  factory EditedField.fromJson(Map<String, dynamic> json) => EditedField(
        field: json['field'] as String? ?? '',
        extracted: json['extracted'],
        submitted: json['submitted'],
      );

  /// "manufacturer_name" → "manufacturer name".
  String get label => field.replaceAll('_', ' ');

  /// Null stays null: it means the change record wasn't kept, not "no changes".
  static List<EditedField>? listFromJson(Object? value) => value is List
      ? value.whereType<Map<String, dynamic>>().map(EditedField.fromJson).toList()
      : null;
}

/// Who read the barcode, in plain words. [source] is "device" (the phone's
/// ML Kit) or "server" (pyzbar on the uploaded photo); scans from before the
/// server recorded it have a barcode but no source.
String barcodeSourceLabel(String? barcode, String? source) {
  if (barcode == null || barcode.isEmpty) {
    return 'Neither the phone nor the server could read it';
  }
  return switch (source) {
    'device' => 'The phone',
    'server' => "The server, from the photo (the phone couldn't read it)",
    _ => 'Not recorded for this scan',
  };
}

class ScanResponse {
  final int evidenceRecordId;
  final int complianceResultId;
  final String overallStatus;
  final String? actionReason;
  final String? lawReference;
  final String? productName;
  final String pinColor;
  final String? barcode;
  final String? barcodeSource;
  final AuthenticityResultModel? authenticity;
  final FssaiMarkModel? fssaiMark;
  final GstinModel gstin;
  final List<int> failedRuleCheckIds;
  final bool complaintCreated;
  final int? complaintId;
  final String? complaintNumber;
  // The scan joined the open complaint of the scan it repeats (or the same
  // photo) instead of opening another.
  final bool complaintLinked;
  final int? rescanOfId;
  final int? duplicateOfId;
  final List<EditedField>? editedFields;

  ScanResponse({
    required this.evidenceRecordId,
    required this.complianceResultId,
    required this.overallStatus,
    this.actionReason,
    this.lawReference,
    this.productName,
    required this.pinColor,
    this.barcode,
    this.barcodeSource,
    this.authenticity,
    this.fssaiMark,
    required this.gstin,
    this.failedRuleCheckIds = const [],
    this.complaintCreated = false,
    this.complaintId,
    this.complaintNumber,
    this.complaintLinked = false,
    this.rescanOfId,
    this.duplicateOfId,
    this.editedFields,
  });

  factory ScanResponse.fromJson(Map<String, dynamic> json) {
    return ScanResponse(
      evidenceRecordId: json['evidence_record_id'] as int? ?? 0,
      complianceResultId: json['compliance_result_id'] as int? ?? 0,
      overallStatus: json['overall_status'] as String? ?? 'compliant',
      actionReason: json['action_reason'] as String?,
      lawReference: json['law_reference'] as String?,
      productName: json['product_name'] as String?,
      pinColor: json['pin_color'] as String? ?? 'green',
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
      failedRuleCheckIds: (json['failed_rule_check_ids'] as List<dynamic>? ?? [])
          .map((e) => (e as num).toInt())
          .toList(),
      complaintCreated: json['complaint_created'] as bool? ?? false,
      complaintId: json['complaint_id'] as int?,
      complaintNumber: json['complaint_number'] as String?,
      complaintLinked: json['complaint_linked'] as bool? ?? false,
      rescanOfId: json['rescan_of_id'] as int?,
      duplicateOfId: json['duplicate_of_id'] as int?,
      editedFields: EditedField.listFromJson(json['edited_fields']),
    );
  }

  bool get isActionNeeded => overallStatus == 'action_needed';
  bool get isCompliant => overallStatus == 'compliant';
}
