/// Structured fields extracted from OCR text of a package label.
///
/// Field extraction is pattern matching, not legal reasoning — the backend
/// compliance rules decide whether the extracted values are compliant.
///
/// Ported from the legal_metrology_compliance_scanner prototype, extended
/// with `gstNumber` and `manufacturerAddress` which the FieldProof backend
/// needs (GSTIN feeds rule 13; the address feeds the authenticity
/// registry cross-check).
library;

import 'scan_models.dart';

class ExtractedFields {
  final String rawText;

  final String? productName;
  final String? manufacturer;
  final String? manufacturerAddress;
  final String? countryOfOrigin;
  final String? netQuantity;
  final String? mrp;
  final String? mfgDate;
  final String? expiryDate;
  final String? batchNumber;
  final String? fssaiNumber;
  final String? gstNumber;
  final String? lmpcNumber;
  final String? consumerCarePhone;
  final String? consumerCareEmail;
  final String? ingredients;

  const ExtractedFields({
    required this.rawText,
    this.productName,
    this.manufacturer,
    this.manufacturerAddress,
    this.countryOfOrigin,
    this.netQuantity,
    this.mrp,
    this.mfgDate,
    this.expiryDate,
    this.batchNumber,
    this.fssaiNumber,
    this.gstNumber,
    this.lmpcNumber,
    this.consumerCarePhone,
    this.consumerCareEmail,
    this.ingredients,
  });

  ExtractedFields copyWith({
    String? rawText,
    String? productName,
    String? manufacturer,
    String? manufacturerAddress,
    String? countryOfOrigin,
    String? netQuantity,
    String? mrp,
    String? mfgDate,
    String? expiryDate,
    String? batchNumber,
    String? fssaiNumber,
    String? gstNumber,
    String? lmpcNumber,
    String? consumerCarePhone,
    String? consumerCareEmail,
    String? ingredients,
  }) {
    return ExtractedFields(
      rawText: rawText ?? this.rawText,
      productName: productName ?? this.productName,
      manufacturer: manufacturer ?? this.manufacturer,
      manufacturerAddress: manufacturerAddress ?? this.manufacturerAddress,
      countryOfOrigin: countryOfOrigin ?? this.countryOfOrigin,
      netQuantity: netQuantity ?? this.netQuantity,
      mrp: mrp ?? this.mrp,
      mfgDate: mfgDate ?? this.mfgDate,
      expiryDate: expiryDate ?? this.expiryDate,
      batchNumber: batchNumber ?? this.batchNumber,
      fssaiNumber: fssaiNumber ?? this.fssaiNumber,
      gstNumber: gstNumber ?? this.gstNumber,
      lmpcNumber: lmpcNumber ?? this.lmpcNumber,
      consumerCarePhone: consumerCarePhone ?? this.consumerCarePhone,
      consumerCareEmail: consumerCareEmail ?? this.consumerCareEmail,
      ingredients: ingredients ?? this.ingredients,
    );
  }

  Map<String, dynamic> toJson() => {
        'rawText': rawText,
        'productName': productName,
        'manufacturer': manufacturer,
        'manufacturerAddress': manufacturerAddress,
        'countryOfOrigin': countryOfOrigin,
        'netQuantity': netQuantity,
        'mrp': mrp,
        'mfgDate': mfgDate,
        'expiryDate': expiryDate,
        'batchNumber': batchNumber,
        'fssaiNumber': fssaiNumber,
        'gstNumber': gstNumber,
        'lmpcNumber': lmpcNumber,
        'consumerCarePhone': consumerCarePhone,
        'consumerCareEmail': consumerCareEmail,
        'ingredients': ingredients,
      };

  /// Convert to the payload shape the FieldProof `POST /scan` endpoint
  /// expects. MRP is parsed to a number here because the backend compares
  /// it numerically against the product registry.
  OcrFields toOcrFields() {
    return OcrFields(
      productName: productName,
      manufacturerName: manufacturer,
      manufacturerAddress: manufacturerAddress,
      mrp: mrp == null ? null : double.tryParse(mrp!.replaceAll(',', '')),
      netQuantity: netQuantity,
      fssaiLicenseNumber: fssaiNumber,
      gstNumber: gstNumber,
      mfgDate: mfgDate,
      expiryDate: expiryDate,
      countryOfOrigin: countryOfOrigin,
      consumerCarePhone: consumerCarePhone,
      consumerCareEmail: consumerCareEmail,
      lmpcNumber: lmpcNumber,
      batchNumber: batchNumber,
      rawText: rawText.isEmpty ? null : rawText,
    );
  }

  /// Fields the extractor is confident about — drives the "N of M detected"
  /// indicator on the review screen.
  int get filledFieldCount {
    final values = [
      productName,
      manufacturer,
      manufacturerAddress,
      countryOfOrigin,
      netQuantity,
      mrp,
      mfgDate,
      expiryDate,
      batchNumber,
      fssaiNumber,
      gstNumber,
      lmpcNumber,
      consumerCarePhone,
      consumerCareEmail,
      ingredients,
    ];
    return values.where((v) => v != null && v.trim().isNotEmpty).length;
  }

  static const int totalFieldCount = 15;
}
