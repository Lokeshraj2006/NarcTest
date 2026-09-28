import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

import '../models/test_models.dart';
import '../services/camera_service.dart';
import 'sealing_screen.dart';

/// Step 2: in-app camera with a card-shaped guide box and a read timer.
class CaptureScreen extends StatefulWidget {
  final KitProfile kit;
  const CaptureScreen({super.key, required this.kit});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  final CameraService _camera = CameraService();
  bool _ready = false;
  bool _failed = false;
  bool _busy = false;
  Timer? _timer;
  int? _secondsLeft;

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    await _camera.initialize();
    if (!mounted) return;
    setState(() {
      _ready = _camera.isInitialized;
      _failed = !_camera.isInitialized;
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _camera.dispose();
    super.dispose();
  }

  void _startTimer() {
    _timer?.cancel();
    setState(() => _secondsLeft = widget.kit.readTimeS);
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted) {
        t.cancel();
        return;
      }
      final left = (_secondsLeft ?? 0) - 1;
      if (left <= 0) {
        t.cancel();
        setState(() => _secondsLeft = null);
        _capture();
      } else {
        setState(() => _secondsLeft = left);
      }
    });
  }

  void _stopTimer() {
    _timer?.cancel();
    setState(() => _secondsLeft = null);
  }

  Future<void> _capture() async {
    if (_busy || !_ready) return;
    _timer?.cancel();
    setState(() {
      _busy = true;
      _secondsLeft = null;
    });
    final XFile? file = await _camera.takePicture();
    if (!mounted) return;
    if (file == null) {
      setState(() => _busy = false);
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Could not take the photo. Please try again.')));
      return;
    }
    final bytes = await file.readAsBytes();
    if (!mounted) return;
    Navigator.of(context).pushReplacement(MaterialPageRoute(
      builder: (_) => SealingScreen(
        kit: widget.kit,
        imageBytes: bytes,
        filename: 'test_${DateTime.now().millisecondsSinceEpoch}.jpg',
      ),
    ));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        title: Text(widget.kit.name, overflow: TextOverflow.ellipsis),
      ),
      body: _failed
          ? const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'Camera is not working. Please allow camera permission and open this screen again.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.white),
                ),
              ),
            )
          : !_ready
              ? const Center(child: CircularProgressIndicator())
              : Stack(
                  fit: StackFit.expand,
                  children: [
                    _fullPreview(),
                    const _GuideBox(),
                    if (_secondsLeft != null)
                      Center(
                        child: Text(
                          '$_secondsLeft',
                          style: const TextStyle(
                            fontSize: 96,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                            shadows: [Shadow(blurRadius: 12)],
                          ),
                        ),
                      ),
                    if (_busy)
                      Container(
                        color: Colors.black54,
                        child: const Center(
                            child: CircularProgressIndicator(
                                color: Colors.white)),
                      ),
                    Positioned(
                      left: 16,
                      right: 16,
                      bottom: 24,
                      child: _controls(),
                    ),
                  ],
                ),
    );
  }

  Widget _fullPreview() {
    final c = _camera.controller!;
    // Camera sizes are landscape; flip for a portrait phone.
    final size = c.value.previewSize;
    final w = size?.height ?? 1080;
    final h = size?.width ?? 1920;
    return ClipRect(
      child: FittedBox(
        fit: BoxFit.cover,
        child: SizedBox(width: w, height: h, child: CameraPreview(c)),
      ),
    );
  }

  Widget _controls() {
    final counting = _secondsLeft != null;
    return Row(
      children: [
        Expanded(
          child: SizedBox(
            height: 56,
            child: FilledButton.icon(
              style: FilledButton.styleFrom(
                  backgroundColor:
                      counting ? Colors.orange.shade800 : Colors.indigo),
              onPressed: _busy
                  ? null
                  : (counting ? _stopTimer : _startTimer),
              icon: Icon(counting ? Icons.stop : Icons.timer),
              label: Text(
                counting
                    ? 'Stop timer'
                    : 'Start timer (${widget.kit.readTimeS}s)',
                style: const TextStyle(fontSize: 16),
              ),
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: SizedBox(
            height: 56,
            child: FilledButton.icon(
              style: FilledButton.styleFrom(backgroundColor: Colors.white),
              onPressed: _busy ? null : _capture,
              icon: const Icon(Icons.camera_alt, color: Colors.black),
              label: const Text('Capture now',
                  style: TextStyle(fontSize: 16, color: Colors.black)),
            ),
          ),
        ),
      ],
    );
  }
}

/// Landscape card-shaped box (190 x 120 mm ratio) with a hint.
class _GuideBox extends StatelessWidget {
  const _GuideBox();

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, box) {
      final w = box.maxWidth * 0.92;
      final h = w * 120 / 190;
      return IgnorePointer(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: Colors.black54,
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Text(
                'Keep the colour card inside the box',
                style: TextStyle(color: Colors.white, fontSize: 16),
              ),
            ),
            const SizedBox(height: 10),
            Container(
              width: w,
              height: h,
              decoration: BoxDecoration(
                border: Border.all(color: Colors.yellowAccent, width: 3),
                borderRadius: BorderRadius.circular(8),
              ),
            ),
            const SizedBox(height: 90),
          ],
        ),
      );
    });
  }
}
