import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

import '../models/test_models.dart';
import 'auth_service.dart';
import 'settings_service.dart';

/// REST client for the FieldProof FastAPI backend.
///
/// The base URL is read on every request, so a change in Settings works
/// right away (Settings override -> LABELGUARD_API_BASE -> emulator fallback).
class ApiService {
  static String get defaultBaseUrl => SettingsService.defaultBaseUrl;

  final String? _pinnedBaseUrl;
  final Dio _dio;

  ApiService({String? baseUrl})
      : _pinnedBaseUrl = baseUrl,
        _dio = Dio(
          BaseOptions(
            connectTimeout: const Duration(seconds: 20),
            receiveTimeout: const Duration(seconds: 60),
            headers: {'Accept': 'application/json'},
          ),
        ) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          options.baseUrl = _pinnedBaseUrl ?? SettingsService.apiBaseUrl;
          final token = await AuthService.getToken();
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          return handler.next(options);
        },
      ),
    );
  }

  /// GET /health, used by the Settings screen's "Test connection" button.
  Future<Map<String, dynamic>> checkHealth({String? overrideBaseUrl}) async {
    final probe = Dio(
      BaseOptions(
        baseUrl:
            overrideBaseUrl ?? _pinnedBaseUrl ?? SettingsService.apiBaseUrl,
        connectTimeout: const Duration(seconds: 8),
        receiveTimeout: const Duration(seconds: 8),
        headers: {'Accept': 'application/json'},
      ),
    );
    final response = await probe.get('/health');
    return Map<String, dynamic>.from(response.data as Map);
  }

  /// POST /auth/login
  Future<Map<String, dynamic>> login(
      String usernameOrEmail, String password) async {
    final response = await _dio.post(
      '/auth/login',
      data: {'username_or_email': usernameOrEmail, 'password': password},
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  /// GET /kits (active kit profiles).
  Future<List<KitProfile>> getKits() async {
    final response = await _dio.get('/kits');
    return _list(response.data).map(KitProfile.fromJson).toList();
  }

  /// POST /tests: multipart photo + context JSON. Returns the sealed record.
  Future<TestRecord> submitTest({
    required Uint8List imageBytes,
    required String filename,
    required Map<String, dynamic> context,
  }) async {
    final form = FormData()
      ..files.add(MapEntry(
        'image',
        MultipartFile.fromBytes(imageBytes,
            filename: filename, contentType: DioMediaType('image', 'jpeg')),
      ))
      ..fields.add(MapEntry('context', jsonEncode(context)));
    final response = await _dio.post('/tests', data: form);
    return TestRecord.fromJson(Map<String, dynamic>.from(response.data as Map));
  }

  /// GET /tests?mine=true (my own tests, newest first).
  Future<List<TestRecord>> getMyTests() async {
    final response = await _dio.get('/tests', queryParameters: {'mine': true});
    return _list(response.data).map(TestRecord.fromJson).toList();
  }

  /// GET /tests/{id}
  Future<TestRecord> getTest(int id) async {
    final response = await _dio.get('/tests/$id');
    return TestRecord.fromJson(Map<String, dynamic>.from(response.data as Map));
  }

  /// Accepts either a bare list or {"rows"/"items": [...]}.
  static List<Map<String, dynamic>> _list(dynamic data) {
    dynamic list = data;
    if (data is Map) {
      list = data['rows'] ?? data['items'] ?? data['tests'] ?? data['kits'];
    }
    if (list is! List) return [];
    return list
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();
  }

  /// Turns any error into a short, simple message for the screen.
  static String friendlyError(Object e) {
    if (e is DioException) {
      final code = e.response?.statusCode;
      final data = e.response?.data;
      if (data is Map && data['detail'] is String) {
        return data['detail'] as String;
      }
      if (code == 401) return 'Your login has expired. Please log in again.';
      if (code == 403) return 'You are not allowed to do this.';
      if (code != null) {
        return 'Server said no (error $code). Please try again.';
      }
      return 'Cannot reach the server. Check Wi-Fi and the server address in Settings.';
    }
    return 'Something went wrong: $e';
  }
}
