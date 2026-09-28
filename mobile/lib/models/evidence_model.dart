/// Bounding box in pixel coordinates for font calibration.
class BoundingBox {
  final double x;
  final double y;
  final double width;
  final double height;

  BoundingBox({
    required this.x,
    required this.y,
    required this.width,
    required this.height,
  });

  factory BoundingBox.fromJson(Map<String, dynamic> json) {
    return BoundingBox(
      x: (json['x'] as num).toDouble(),
      y: (json['y'] as num).toDouble(),
      width: (json['width'] as num).toDouble(),
      height: (json['height'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'x': x.round(),
      'y': y.round(),
      'width': width.round(),
      'height': height.round(),
    };
  }
}

/// Barcode detection information used as measurement reference.
class BarcodeMetadata {
  final String data;
  final BoundingBox bbox;

  /// Symbology, e.g. "ean13". The backend uses this to look up the symbol's
  /// standardised printed width, which is what makes the barcode usable as a
  /// physical ruler for font-size measurement.
  final String? format;

  BarcodeMetadata({
    required this.data,
    required this.bbox,
    this.format,
  });

  factory BarcodeMetadata.fromJson(Map<String, dynamic> json) {
    return BarcodeMetadata(
      data: json['data'] as String? ?? '',
      format: json['format'] as String?,
      bbox: BoundingBox.fromJson(json['bbox'] as Map<String, dynamic>),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'data': data,
      'bbox': bbox.toJson(),
    };
  }
}

/// Extracted OCR text block with coordinates.
class OcrTextBlock {
  final String text;
  final BoundingBox bbox;

  OcrTextBlock({
    required this.text,
    required this.bbox,
  });

  factory OcrTextBlock.fromJson(Map<String, dynamic> json) {
    return OcrTextBlock(
      text: json['text'] as String? ?? '',
      bbox: BoundingBox.fromJson(json['bbox'] as Map<String, dynamic>),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'text': text,
      'bbox': bbox.toJson(),
    };
  }
}

/// Bundled ML Kit optical measurement payload.
class MlKitPayload {
  final BarcodeMetadata? barcode;
  final List<OcrTextBlock> textBlocks;
  final int imageWidthPx;
  final int imageHeightPx;

  MlKitPayload({
    this.barcode,
    required this.textBlocks,
    required this.imageWidthPx,
    required this.imageHeightPx,
  });

  factory MlKitPayload.fromJson(Map<String, dynamic> json) {
    return MlKitPayload(
      barcode: json['barcode'] != null
          ? BarcodeMetadata.fromJson(json['barcode'] as Map<String, dynamic>)
          : null,
      textBlocks: (json['text_blocks'] as List<dynamic>? ?? [])
          .map((e) => OcrTextBlock.fromJson(e as Map<String, dynamic>))
          .toList(),
      imageWidthPx: json['image_width_px'] as int? ?? 0,
      imageHeightPx: json['image_height_px'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'barcode': barcode?.toJson(),
      'text_blocks': textBlocks.map((b) => b.toJson()).toList(),
      'image_width_px': imageWidthPx,
      'image_height_px': imageHeightPx,
    };
  }
}

/// Comprehensive evidence bundle prior to transmission to FastAPI backend.
class EvidenceMetadata {
  final String imagePath;
  final String sha256Hash;
  final double? latitude;
  final double? longitude;
  final double? accuracyMeters;
  final DateTime deviceTimestamp;
  final DateTime? ntpTimestamp;
  final double? ntpDriftSeconds;
  final MlKitPayload? mlKitPayload;
  final int? inspectionId;
  final int? complaintId;

  EvidenceMetadata({
    required this.imagePath,
    required this.sha256Hash,
    this.latitude,
    this.longitude,
    this.accuracyMeters,
    required this.deviceTimestamp,
    this.ntpTimestamp,
    this.ntpDriftSeconds,
    this.mlKitPayload,
    this.inspectionId,
    this.complaintId,
  });
}
