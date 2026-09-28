import 'package:camera/camera.dart';

/// Camera service wrapper managing camera controllers and image captures.
class CameraService {
  CameraController? _controller;
  List<CameraDescription> _cameras = [];
  bool _isInitialized = false;

  bool get isInitialized => _isInitialized && _controller != null;
  CameraController? get controller => _controller;

  /// Initializes the primary back camera with high resolution.
  Future<void> initialize() async {
    try {
      _cameras = await availableCameras();
      if (_cameras.isEmpty) return;

      final backCamera = _cameras.firstWhere(
        (cam) => cam.lensDirection == CameraLensDirection.back,
        orElse: () => _cameras.first,
      );

      _controller = CameraController(
        backCamera,
        ResolutionPreset.veryHigh,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.jpeg,
      );

      await _controller!.initialize();
      _isInitialized = true;
    } catch (_) {
      _isInitialized = false;
    }
  }

  /// Captures a still photograph and returns the local file path.
  Future<XFile?> takePicture() async {
    if (!isInitialized) return null;
    try {
      return await _controller!.takePicture();
    } catch (_) {
      return null;
    }
  }

  void dispose() {
    _controller?.dispose();
    _isInitialized = false;
  }
}
