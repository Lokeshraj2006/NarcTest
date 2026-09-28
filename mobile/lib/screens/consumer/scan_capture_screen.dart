import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../../models/evidence_model.dart';
import '../../models/scan_models.dart';
import '../../providers/scan_provider.dart';
import '../../services/barcode_service.dart';
import '../../services/camera_service.dart';
import '../../services/field_extractor.dart';
import '../../services/gps_service.dart';
import '../../services/ntp_service.dart';
import '../../services/ocr_service.dart';
import 'ocr_review_screen.dart';

/// Consumer-facing scan capture flow: preview camera → capture → barcode + OCR
/// → build ScanContext → POST /scan → route to the result screen.
class ScanCaptureScreen extends StatefulWidget {
  /// Set when rescanning an earlier scan; the result is saved as a new scan.
  final int? rescanOfId;

  const ScanCaptureScreen({super.key, this.rescanOfId});

  @override
  State<ScanCaptureScreen> createState() => _ScanCaptureScreenState();
}

class _ScanCaptureScreenState extends State<ScanCaptureScreen> {
  final _camera = CameraService();
  final _barcode = BarcodeService();
  final _ocr = OcrService();
  final _picker = ImagePicker();
  final _extractor = FieldExtractor();

  bool _initializing = true;
  String? _initError;
  String _stage = '';

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    try {
      await _camera.initialize();
    } catch (e) {
      _initError = 'Camera failed to initialize: $e';
    }
    if (!mounted) return;
    setState(() => _initializing = false);
  }

  @override
  void dispose() {
    _camera.dispose();
    _barcode.dispose();
    _ocr.dispose();
    super.dispose();
  }

  Future<void> _capture() async {
    final file = await _camera.takePicture();
    if (file == null) {
      _snack('Could not capture image.');
      return;
    }
    await _runPipeline(file.path);
  }

  Future<void> _pickFromGallery() async {
    final picked = await _picker.pickImage(source: ImageSource.gallery);
    if (picked == null) return;
    await _runPipeline(picked.path);
  }

  Future<void> _runPipeline(String imagePath) async {
    setState(() => _stage = 'Scanning barcode…');
    final barcodeMeta = await _safeBarcode(imagePath);

    setState(() => _stage = 'Reading text on label…');
    final ocr = await _safeOcr(imagePath);
    final blocks = ocr.blocks;
    final ocrText = blocks.map((b) => b.text).join('\n');

    setState(() => _stage = 'Extracting label fields…');
    final fields = _extractor.extract(ocrText, lines: ocr.lines);

    setState(() => _stage = 'Measuring label…');
    final imageSize = await _imageSize(imagePath);

    setState(() => _stage = 'Locating your position…');
    final gps = await GpsService.getCurrentPosition();

    // Atomic time. Its agreement with the device clock is what gives the
    // capture timestamp evidential weight, so it is worth the round trip —
    // but a failure must not block the scan.
    setState(() => _stage = 'Verifying time…');
    final time = await _safeNtp();

    if (!mounted) return;
    setState(() => _stage = '');

    // Hand off to the review screen — it owns correction and submission,
    // so a misread MRP or GSTIN can be fixed before the compliance rules
    // see it.
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => OcrReviewScreen(
          imagePath: imagePath,
          barcode: barcodeMeta?.data,
          barcodeBbox: barcodeMeta == null
              ? null
              : [
                  barcodeMeta.bbox.x,
                  barcodeMeta.bbox.y,
                  barcodeMeta.bbox.width,
                  barcodeMeta.bbox.height,
                ],
          barcodeFormat: barcodeMeta?.format,
          textBlocks: blocks
              .map((b) => OcrTextBlockGeometry(
                    text: b.text,
                    x: b.bbox.x,
                    y: b.bbox.y,
                    width: b.bbox.width,
                    height: b.bbox.height,
                  ))
              .toList(),
          imageWidthPx: imageSize?.width.round(),
          imageHeightPx: imageSize?.height.round(),
          gpsLatitude: gps?.latitude,
          gpsLongitude: gps?.longitude,
          gpsAccuracyMeters: gps?.accuracy,
          deviceTimestamp: time.deviceTime,
          ntpTimestamp: time.ntpTime,
          ntpDriftSeconds: time.driftSeconds,
          fields: fields,
          rescanOfId: widget.rescanOfId,
        ),
      ),
    );
  }

  Future<NtpTimeResult> _safeNtp() async {
    try {
      return await NtpService.getNetworkTime();
    } catch (_) {
      return NtpTimeResult(
        deviceTime: DateTime.now().toUtc(),
        ntpTime: null,
        driftSeconds: null,
        isSuccess: false,
      );
    }
  }

  /// Pixel dimensions of the captured file — needed to interpret the OCR
  /// geometry the backend measures against.
  Future<Size?> _imageSize(String path) async {
    try {
      final bytes = await File(path).readAsBytes();
      final decoded = await decodeImageFromList(bytes);
      return Size(decoded.width.toDouble(), decoded.height.toDouble());
    } catch (_) {
      return null;
    }
  }

  Future<BarcodeMetadata?> _safeBarcode(String imagePath) async {
    try {
      final meta = await _barcode.detectReferenceBarcode(imagePath);
      if (meta == null || meta.data.isEmpty) return null;
      return meta;
    } catch (_) {
      return null;
    }
  }

  Future<OcrRecognition> _safeOcr(String imagePath) async {
    try {
      return await _ocr.recognize(imagePath);
    } catch (_) {
      return OcrRecognition.empty;
    }
  }

  void _snack(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    final scan = context.watch<ScanProvider>();

    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: Text(widget.rescanOfId == null
            ? 'Scan Label'
            : 'Rescan #${widget.rescanOfId}'),
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.photo_library_outlined),
            tooltip: 'Pick from gallery',
            onPressed: scan.submitting ? null : _pickFromGallery,
          ),
        ],
      ),
      body: _buildBody(scan),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: FilledButton.icon(
            style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(56),
              backgroundColor: Colors.indigo.shade600,
            ),
            icon: const Icon(Icons.camera),
            label: Text(
              scan.submitting ? 'Working…' : 'Capture & Submit',
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
            ),
            onPressed: (scan.submitting ||
                    _initializing ||
                    !_camera.isInitialized)
                ? null
                : _capture,
          ),
        ),
      ),
    );
  }

  Widget _buildBody(ScanProvider scan) {
    if (_initializing) {
      return const Center(
        child: CircularProgressIndicator(color: Colors.white),
      );
    }
    if (_initError != null || !_camera.isInitialized) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.no_photography, size: 64, color: Colors.white54),
              SizedBox(height: 16),
              Text(
                'Camera not available on this device.',
                style: TextStyle(color: Colors.white70, fontSize: 16),
                textAlign: TextAlign.center,
              ),
              SizedBox(height: 8),
              Text(
                'Use the gallery button above to pick an existing image.',
                style: TextStyle(color: Colors.white38),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      );
    }

    return Stack(
      children: [
        Positioned.fill(child: CameraPreview(_camera.controller!)),
        _buildGuideOverlay(),
        if (scan.submitting || _stage.isNotEmpty) _buildProgressOverlay(),
      ],
    );
  }

  Widget _buildGuideOverlay() {
    return IgnorePointer(
      child: Center(
        child: Container(
          margin: const EdgeInsets.all(32),
          decoration: BoxDecoration(
            border: Border.all(color: Colors.white70, width: 2),
            borderRadius: BorderRadius.circular(12),
          ),
          child: const AspectRatio(aspectRatio: 3 / 4),
        ),
      ),
    );
  }

  Widget _buildProgressOverlay() {
    return Container(
      color: Colors.black54,
      alignment: Alignment.center,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const CircularProgressIndicator(color: Colors.white),
          const SizedBox(height: 16),
          Text(
            _stage.isEmpty ? 'Submitting…' : _stage,
            style: const TextStyle(color: Colors.white, fontSize: 15),
          ),
        ],
      ),
    );
  }
}

