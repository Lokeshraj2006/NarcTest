import 'dart:math';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// A random device id made once and kept in secure storage.
class DeviceIdService {
  DeviceIdService._();

  static const _storage = FlutterSecureStorage();
  static const _key = 'fieldproof_device_id';

  static Future<String> getId() async {
    try {
      final existing = await _storage.read(key: _key);
      if (existing != null && existing.isNotEmpty) return existing;
    } catch (_) {}
    final rnd = Random.secure();
    final hex = List.generate(16, (_) => rnd.nextInt(256))
        .map((b) => b.toRadixString(16).padLeft(2, '0'))
        .join();
    final id = 'android-$hex';
    try {
      await _storage.write(key: _key, value: id);
    } catch (_) {}
    return id;
  }
}
