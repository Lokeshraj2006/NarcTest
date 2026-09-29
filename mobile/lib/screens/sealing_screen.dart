import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';

import '../l10n/lang.dart';
import '../models/test_models.dart';
import '../services/api_service.dart';
import '../services/device_id_service.dart';
import '../services/gps_service.dart';
import '../utils/app_colors.dart';
import 'result_screen.dart';

/// Step 3: get GPS + device id + photo hash, send to server, show result.
class SealingScreen extends StatefulWidget {
  final KitProfile kit;
  final Uint8List imageBytes;
  final String filename;

  const SealingScreen({
    super.key,
    required this.kit,
    required this.imageBytes,
    required this.filename,
  });

  @override
  State<SealingScreen> createState() => _SealingScreenState();
}

class _SealingScreenState extends State<SealingScreen> {
  String _step = 'Getting your location...';
  String? _error;

  @override
  void initState() {
    super.initState();
    _run();
  }

  /// ISO 8601 with the phone's time-zone offset, e.g. 2026-09-28T11:40:00+05:30
  static String isoWithOffset(DateTime t) {
    final off = t.timeZoneOffset;
    final sign = off.isNegative ? '-' : '+';
    final hh = off.inHours.abs().toString().padLeft(2, '0');
    final mm = (off.inMinutes.abs() % 60).toString().padLeft(2, '0');
    final base = t.toIso8601String().split('.').first;
    return '$base$sign$hh:$mm';
  }

  Future<void> _run() async {
    setState(() {
      _error = null;
      _step = 'Getting your location...';
    });
    try {
      Position? pos;
      try {
        pos = await GpsService.getCurrentPosition();
      } catch (_) {
        pos = null;
      }
      final deviceId = await DeviceIdService.getId();
      final hash = sha256.convert(widget.imageBytes).toString();
      if (!mounted) return;
      setState(() => _step = 'Sealing your test record...');

      final context = <String, dynamic>{
        'kit_id': widget.kit.id,
        'latitude': pos?.latitude,
        'longitude': pos?.longitude,
        'gps_accuracy_m': pos?.accuracy,
        'gps_is_mock': pos?.isMocked ?? false,
        'device_id': deviceId,
        'device_time': isoWithOffset(DateTime.now()),
        'client_sha256': hash,
        'lab_sample_id': null,
        'notes': null,
      };
      final record = await ApiService().submitTest(
        imageBytes: widget.imageBytes,
        filename: widget.filename,
        context: context,
      );
      if (!mounted) return;
      Navigator.of(this.context).pushReplacement(
        MaterialPageRoute(builder: (_) => ResultScreen(record: record)),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = ApiService.friendlyError(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(tr(context, 'Saving test')),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Image.memory(widget.imageBytes,
                    height: 180, fit: BoxFit.cover),
              ),
              const SizedBox(height: 24),
              if (_error == null) ...[
                const CircularProgressIndicator(),
                const SizedBox(height: 16),
                Text(tr(context, _step),
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                        fontSize: 18, fontWeight: FontWeight.w600)),
                const SizedBox(height: 6),
                Text(tr(context, 'Please wait, do not close the app.'),
                    style: const TextStyle(color: AppColors.textSecondary)),
              ] else ...[
                const Icon(Icons.error_outline, color: Colors.red, size: 48),
                const SizedBox(height: 12),
                Text(tr(context, _error!),
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 16)),
                const SizedBox(height: 16),
                FilledButton.icon(
                  onPressed: _run,
                  icon: const Icon(Icons.refresh),
                  label: Text(tr(context, 'Try sending again')),
                ),
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: Text(tr(context, 'Go back')),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
