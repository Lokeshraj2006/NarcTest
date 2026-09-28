import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';
import '../models/evidence_model.dart';
import '../models/scan_models.dart';

/// ML Kit output in two granularities: blocks, which the backend measures,
/// and the individual lines inside them, which the field extractor uses to
/// pair label headings with their values.
class OcrRecognition {
  const OcrRecognition({required this.blocks, required this.lines});

  static const empty = OcrRecognition(blocks: [], lines: []);

  final List<OcrTextBlock> blocks;
  final List<OcrTextBlockGeometry> lines;
}

/// On-device OCR using Google ML Kit Text Recognition v2.
class OcrService {
  final TextRecognizer _textRecognizer = TextRecognizer(script: TextRecognitionScript.latin);

  Future<OcrRecognition> recognize(String imagePath) async {
    final inputImage = InputImage.fromFilePath(imagePath);
    final recognizedText = await _textRecognizer.processImage(inputImage);

    final List<OcrTextBlock> blocks = [];
    final List<OcrTextBlockGeometry> lines = [];

    for (final block in recognizedText.blocks) {
      final rect = block.boundingBox;
      blocks.add(
        OcrTextBlock(
          text: block.text.trim(),
          bbox: BoundingBox(
            x: rect.left,
            y: rect.top,
            width: rect.width,
            height: rect.height,
          ),
        ),
      );
      for (final line in block.lines) {
        final box = line.boundingBox;
        lines.add(
          OcrTextBlockGeometry(
            text: line.text.trim(),
            x: box.left,
            y: box.top,
            width: box.width,
            height: box.height,
          ),
        );
      }
    }

    return OcrRecognition(blocks: blocks, lines: lines);
  }

  void dispose() {
    _textRecognizer.close();
  }
}
