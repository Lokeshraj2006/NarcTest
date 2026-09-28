import 'dart:io';
import 'package:crypto/crypto.dart';

/// Computes SHA-256 cryptographic hashes on raw image bytes prior to transmission.
class HashingService {
  /// Computes a standard 64-character lowercase hexadecimal SHA-256 hash.
  static Future<String> computeFileSha256(String filePath) async {
    final file = File(filePath);
    final bytes = await file.readAsBytes();
    final digest = sha256.convert(bytes);
    return digest.toString();
  }

  /// Computes SHA-256 directly from in-memory byte buffer.
  static String computeBytesSha256(List<int> bytes) {
    final digest = sha256.convert(bytes);
    return digest.toString();
  }
}
