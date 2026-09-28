import 'package:google_mlkit_barcode_scanning/google_mlkit_barcode_scanning.dart';
import '../models/evidence_model.dart';

/// On-device barcode detector using Google ML Kit Barcode Scanning.
/// Used PURELY as a physical reference anchor (GS1 EAN-13 nominal 37.29 mm width).
class BarcodeService {
  final BarcodeScanner _barcodeScanner = BarcodeScanner(
    formats: [
      BarcodeFormat.ean13,
      BarcodeFormat.ean8,
      BarcodeFormat.upca,
      BarcodeFormat.upce,
      BarcodeFormat.code128,
    ],
  );

  /// Detects the primary barcode in the image and returns its bounding box.
  Future<BarcodeMetadata?> detectReferenceBarcode(String imagePath) async {
    final inputImage = InputImage.fromFilePath(imagePath);
    final barcodes = await _barcodeScanner.processImage(inputImage);

    if (barcodes.isEmpty) {
      return null;
    }

    // Prioritize EAN-13 as the standard calibration anchor (nominal 37.29 mm)
    Barcode primary = barcodes.first;
    for (final b in barcodes) {
      if (b.format == BarcodeFormat.ean13) {
        primary = b;
        break;
      }
    }

    final rect = primary.boundingBox;
    return BarcodeMetadata(
      data: primary.rawValue ?? '',
      format: _formatName(primary.format),
      bbox: BoundingBox(
        x: rect.left,
        y: rect.top,
        width: rect.width,
        height: rect.height,
      ),
    );
  }

  /// Map ML Kit's enum to the symbology names the backend calibrates against.
  /// Only fixed-width symbologies are useful as a dimensional reference;
  /// Code128 is variable-width, and the backend refuses to calibrate from it.
  String? _formatName(BarcodeFormat f) {
    switch (f) {
      case BarcodeFormat.ean13:
        return 'ean13';
      case BarcodeFormat.ean8:
        return 'ean8';
      case BarcodeFormat.upca:
        return 'upca';
      case BarcodeFormat.upce:
        return 'upce';
      case BarcodeFormat.code128:
        return 'code128';
      default:
        return null;
    }
  }

  void dispose() {
    _barcodeScanner.close();
  }
}
