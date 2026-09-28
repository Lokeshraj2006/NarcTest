import 'package:flutter/foundation.dart';
import '../models/scan_models.dart';
import '../services/api_service.dart';

/// State for the consumer scan flow — submits an image + context blob to
/// POST /scan and holds the returned verdict for the result screen.
class ScanProvider extends ChangeNotifier {
  final ApiService _api;

  ScanProvider({ApiService? api}) : _api = api ?? ApiService();

  bool _submitting = false;
  String? _errorMessage;
  ScanResponse? _lastResult;

  bool get submitting => _submitting;
  String? get errorMessage => _errorMessage;
  ScanResponse? get lastResult => _lastResult;

  Future<ScanResponse?> submit({
    required String imagePath,
    required ScanContext context,
    List<String> extraImagePaths = const [],
  }) async {
    _submitting = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final result = await _api.submitScan(
        imagePath: imagePath,
        context: context,
        extraImagePaths: extraImagePaths,
      );
      _lastResult = result;
      return result;
    } catch (e) {
      _errorMessage = _friendlyError(e);
      return null;
    } finally {
      _submitting = false;
      notifyListeners();
    }
  }

  void reset() {
    _lastResult = null;
    _errorMessage = null;
    notifyListeners();
  }

  String _friendlyError(Object e) {
    final msg = e.toString();
    if (msg.contains('SocketException') || msg.contains('Failed host')) {
      return 'Could not reach backend — is the API running?';
    }
    if (msg.contains('401')) return 'Session expired — please sign in again.';
    if (msg.contains('422')) return 'Scan payload rejected by the server.';
    return 'Scan failed: $msg';
  }
}
