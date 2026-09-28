import 'dart:convert';
import 'package:dio/dio.dart';
import '../models/compliance_model.dart';
import '../models/evidence_model.dart';
import '../models/inspection_model.dart';
import '../models/complaint_model.dart';
import '../models/inspection_log_models.dart';
import '../models/pending_complaint_model.dart';
import '../models/scan_models.dart';
import '../models/violation_models.dart';
import 'auth_service.dart';
import 'settings_service.dart';

/// REST API Client for communicating with the FieldProof FastAPI backend.
///
/// Base URL resolution order (evaluated per request, so changing it in
/// Settings takes effect immediately without an app restart):
///   1. Explicit [ApiService(baseUrl: ...)] argument — pins this instance.
///   2. User override saved in Settings ([SettingsService.apiBaseUrl]).
///   3. Compile-time --dart-define=LABELGUARD_API_BASE.
///   4. Android emulator loopback fallback.
///
/// A physical phone cannot reach `localhost` or `10.0.2.2` — those resolve
/// to the phone itself — so it needs the dev machine's LAN IP.
class ApiService {
  /// Build-time default, exposed for the Settings screen to display.
  static String get defaultBaseUrl => SettingsService.defaultBaseUrl;

  /// When non-null, pins this instance to one URL and ignores Settings.
  final String? _pinnedBaseUrl;
  final Dio _dio;

  ApiService({String? baseUrl})
      : _pinnedBaseUrl = baseUrl,
        _dio = Dio(
          BaseOptions(
            connectTimeout: const Duration(seconds: 20),
            receiveTimeout: const Duration(seconds: 30),
            headers: {'Accept': 'application/json'},
          ),
        ) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          // Resolved per request so a Settings change applies right away.
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

  /// GET /health — used by the Settings screen's "Test connection" button.
  /// Returns the parsed health payload, or throws with a readable message.
  Future<Map<String, dynamic>> checkHealth({String? overrideBaseUrl}) async {
    final probe = Dio(
      BaseOptions(
        baseUrl: overrideBaseUrl ?? _pinnedBaseUrl ?? SettingsService.apiBaseUrl,
        connectTimeout: const Duration(seconds: 8),
        receiveTimeout: const Duration(seconds: 8),
        headers: {'Accept': 'application/json'},
      ),
    );
    final response = await probe.get('/health');
    return Map<String, dynamic>.from(response.data as Map);
  }

  // ─── Auth ───────────────────────────────────────────────────────────────

  /// POST /auth/login
  Future<Map<String, dynamic>> login(
      String usernameOrEmail, String password) async {
    final response = await _dio.post(
      '/auth/login',
      data: {
        'username_or_email': usernameOrEmail,
        'password': password,
      },
    );
    return response.data as Map<String, dynamic>;
  }

  // ─── Scan pipeline (item 7) ─────────────────────────────────────────────

  /// POST /scan — multipart image + JSON context, plus any photos of other
  /// faces ("Scan another part"), which the server checks for the veg mark.
  /// Returns the full verdict including whether a pending Complaint was
  /// auto-created for consumers.
  Future<ScanResponse> submitScan({
    required String imagePath,
    required ScanContext context,
    List<String> extraImagePaths = const [],
  }) async {
    String name(String path) => path.split(RegExp(r'[\\/]')).last;
    final formData = FormData()
      ..files.add(MapEntry(
        'image',
        await MultipartFile.fromFile(imagePath, filename: name(imagePath)),
      ))
      ..fields.add(MapEntry('context', jsonEncode(context.toJson())));
    for (final path in extraImagePaths) {
      formData.files.add(MapEntry(
        'extra_images',
        await MultipartFile.fromFile(path, filename: name(path)),
      ));
    }
    final response = await _dio.post('/scan', data: formData);
    return ScanResponse.fromJson(response.data as Map<String, dynamic>);
  }

  // ─── Inspector dashboard (item 5) ───────────────────────────────────────

  /// GET /inspections/log
  Future<List<InspectionLogRow>> getInspectionLog({
    int limit = 200,
    int offset = 0,
    bool onlyActionNeeded = false,
    bool mine = false,
  }) async {
    final response = await _dio.get(
      '/inspections/log',
      queryParameters: {
        'limit': limit,
        'offset': offset,
        'only_action_needed': onlyActionNeeded,
        'mine': mine,
      },
    );
    final data = response.data as Map<String, dynamic>;
    final rows = (data['rows'] as List<dynamic>? ?? [])
        .whereType<Map<String, dynamic>>()
        .map(InspectionLogRow.fromJson)
        .toList();
    return rows;
  }

  /// GET /scan/history — the signed-in user's own scans, newest first.
  Future<List<InspectionLogRow>> getMyScanHistory({int limit = 200}) async {
    final response =
        await _dio.get('/scan/history', queryParameters: {'limit': limit});
    final data = response.data as Map<String, dynamic>;
    return (data['rows'] as List<dynamic>? ?? [])
        .whereType<Map<String, dynamic>>()
        .map(InspectionLogRow.fromJson)
        .toList();
  }

  /// GET /inspections/{evidence_record_id} — inspectors and admins see any
  /// scan; a consumer only their own.
  Future<InspectionDetail> getInspectionDetail(int evidenceRecordId) async {
    final response = await _dio.get('/inspections/$evidenceRecordId');
    return InspectionDetail.fromJson(response.data as Map<String, dynamic>);
  }

  // ─── Pending complaints (item 7 handoff) ────────────────────────────────

  /// GET /complaints/pending
  Future<List<PendingComplaintRow>> getPendingComplaints({
    int limit = 200,
    int offset = 0,
  }) async {
    final response = await _dio.get(
      '/complaints/pending',
      queryParameters: {'limit': limit, 'offset': offset},
    );
    final data = response.data as Map<String, dynamic>;
    return (data['rows'] as List<dynamic>? ?? [])
        .whereType<Map<String, dynamic>>()
        .map(PendingComplaintRow.fromJson)
        .toList();
  }

  // ─── Violation reports (inspector → admin escalation) ──────────────────

  /// POST /violations — file a formal report from a scan.
  ///
  /// The backend cites every FAILed rule check on the evidence record and
  /// derives severity from the worst one, so the inspector only supplies the
  /// context the system cannot know: which shop, and what they observed.
  Future<ViolationReportResult> fileViolationReport({
    required int evidenceRecordId,
    String? inspectorNotes,
    String? shopName,
    String? shopAddress,
    int? complaintId,
    bool citeRegistry = false,
    bool packChecked = false,
  }) async {
    final response = await _dio.post('/violations', data: {
      'evidence_record_id': evidenceRecordId,
      if (complaintId != null) 'complaint_id': complaintId,
      // A registry mismatch is cited under Rule 6(3) only when the inspector
      // has checked the pack; the server refuses one without the other.
      if (citeRegistry) 'cite_registry': true,
      if (citeRegistry) 'pack_checked': packChecked,
      if (inspectorNotes != null && inspectorNotes.isNotEmpty)
        'inspector_notes': inspectorNotes,
      if (shopName != null && shopName.isNotEmpty) 'shop_name': shopName,
      if (shopAddress != null && shopAddress.isNotEmpty)
        'shop_address': shopAddress,
    });
    return ViolationReportResult.fromJson(
        response.data as Map<String, dynamic>);
  }

  /// GET /violations — the reports this inspector filed.
  Future<List<ViolationReportResult>> myViolationReports() async {
    final response =
        await _dio.get('/violations', queryParameters: {'limit': 200});
    final data = response.data as Map<String, dynamic>;
    return (data['rows'] as List<dynamic>? ?? [])
        .whereType<Map<String, dynamic>>()
        .map(ViolationReportResult.fromJson)
        .toList();
  }

  // ─── Legal-notice PDF (ADMIN ONLY — issued from the web dashboard) ──────

  /// GET /legal-notice/{evidence_record_id}/generate
  ///
  /// Returns the raw PDF bytes and the filename the server suggested (via
  /// the X-Legal-Notice-Filename header, falling back to a stable name).
  Future<({List<int> bytes, String filename})> downloadLegalNotice(
      int evidenceRecordId) async {
    final response = await _dio.get<List<int>>(
      '/legal-notice/$evidenceRecordId/generate',
      options: Options(
        responseType: ResponseType.bytes,
        headers: {'Accept': 'application/pdf'},
      ),
    );
    final bytes = response.data ?? const [];
    final headerName = response.headers.value('x-legal-notice-filename');
    final filename = headerName ?? 'legal_notice_ev$evidenceRecordId.pdf';
    return (bytes: bytes, filename: filename);
  }

  // ─── Legacy endpoints — retained for backward compatibility ────────────

  /// POST /evidence/upload — pre-item-7 evidence upload path.
  Future<Map<String, dynamic>> uploadEvidence(EvidenceMetadata evidence) async {
    final formData = FormData.fromMap({
      'image': await MultipartFile.fromFile(
        evidence.imagePath,
        filename: evidence.imagePath.split('/').last,
      ),
      'sha256_hash': evidence.sha256Hash,
      'timestamp_device': evidence.deviceTimestamp.toIso8601String(),
      if (evidence.ntpTimestamp != null)
        'timestamp_ntp': evidence.ntpTimestamp!.toIso8601String(),
      if (evidence.ntpDriftSeconds != null)
        'ntp_drift_seconds': evidence.ntpDriftSeconds,
      if (evidence.latitude != null) 'gps_latitude': evidence.latitude,
      if (evidence.longitude != null) 'gps_longitude': evidence.longitude,
      if (evidence.accuracyMeters != null)
        'gps_accuracy_meters': evidence.accuracyMeters,
      if (evidence.inspectionId != null) 'inspection_id': evidence.inspectionId,
      if (evidence.complaintId != null) 'complaint_id': evidence.complaintId,
      if (evidence.mlKitPayload != null)
        'ocr_raw_payload': jsonEncode(evidence.mlKitPayload!.toJson()),
    });
    final response = await _dio.post('/evidence/upload', data: formData);
    return response.data as Map<String, dynamic>;
  }

  Future<ComplianceReport> getCompliance(int productId) async {
    final response = await _dio.get('/compliance/$productId');
    return ComplianceReport.fromJson(response.data as Map<String, dynamic>);
  }

  Future<Map<String, dynamic>> submitComplaint({
    required String productName,
    String? brandName,
    String? storeName,
    required String description,
    double? latitude,
    double? longitude,
  }) async {
    final response = await _dio.post(
      '/complaints',
      data: {
        'product_name': productName,
        'brand_name': brandName,
        'store_name': storeName,
        'description': description,
        'gps_latitude': latitude,
        'gps_longitude': longitude,
      },
    );
    return response.data as Map<String, dynamic>;
  }

  Future<List<ComplaintModel>> getComplaints() async {
    final response = await _dio.get('/complaints');
    final list = response.data as List<dynamic>;
    return list
        .map((e) => ComplaintModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<InspectionModel>> getInspections() async {
    final response = await _dio.get('/inspections');
    final list = response.data as List<dynamic>;
    return list
        .map((e) => InspectionModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
