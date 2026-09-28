import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Runtime-configurable app settings.
///
/// The backend URL is the important one: on a phone hotspot the laptop's IP
/// changes whenever the hotspot restarts, and a compile-time-only URL would
/// mean rebuilding the APK every time. This stores an override in secure
/// storage and caches it in memory so the Dio interceptor can read it
/// synchronously on every request.
///
/// Resolution order:
///   1. User-entered override (secure storage)
///   2. Compile-time --dart-define=LABELGUARD_API_BASE
///   3. Android emulator loopback fallback
class SettingsService {
  SettingsService._();

  static const _storage = FlutterSecureStorage();
  static const _apiBaseUrlKey = 'api_base_url_override';

  static const String _emulatorFallback = 'http://10.0.2.2:8000';
  static const String compiledDefault =
      String.fromEnvironment('LABELGUARD_API_BASE', defaultValue: '');

  /// The value baked in at build time, or the emulator fallback.
  static String get defaultBaseUrl =>
      compiledDefault.isNotEmpty ? compiledDefault : _emulatorFallback;

  static String? _cachedOverride;
  static bool _loaded = false;

  /// Effective base URL. Safe to call synchronously after [load].
  static String get apiBaseUrl {
    final o = _cachedOverride;
    return (o != null && o.isNotEmpty) ? o : defaultBaseUrl;
  }

  /// True when the user has set an override different from the build default.
  static bool get hasOverride =>
      _cachedOverride != null && _cachedOverride!.isNotEmpty;

  /// Load persisted settings into the cache. Call once at app startup.
  static Future<void> load() async {
    if (_loaded) return;
    try {
      _cachedOverride = await _storage.read(key: _apiBaseUrlKey);
    } catch (_) {
      _cachedOverride = null;
    }
    _loaded = true;
  }

  /// Persist a new backend URL and update the cache immediately.
  static Future<void> setApiBaseUrl(String url) async {
    final normalized = normalizeUrl(url);
    _cachedOverride = normalized;
    await _storage.write(key: _apiBaseUrlKey, value: normalized);
  }

  /// Drop the override and fall back to the compiled-in default.
  static Future<void> clearApiBaseUrl() async {
    _cachedOverride = null;
    await _storage.delete(key: _apiBaseUrlKey);
  }

  /// Trim, add a scheme if missing, and strip any trailing slash.
  static String normalizeUrl(String raw) {
    var s = raw.trim();
    if (s.isEmpty) return s;
    if (!s.startsWith('http://') && !s.startsWith('https://')) {
      s = 'http://$s';
    }
    while (s.endsWith('/')) {
      s = s.substring(0, s.length - 1);
    }
    return s;
  }

  /// Returns null when valid, else a human-readable reason.
  static String? validate(String raw) {
    final s = normalizeUrl(raw);
    if (s.isEmpty) return 'Enter a backend address.';
    final uri = Uri.tryParse(s);
    if (uri == null || uri.host.isEmpty) {
      return 'Not a valid address. Example: 192.168.1.42:8000';
    }
    if (!uri.hasPort) {
      return 'Include the port. Example: ${uri.host}:8000';
    }
    return null;
  }
}
