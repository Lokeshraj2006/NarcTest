import 'package:flutter/foundation.dart';
import '../models/inspection_log_models.dart';
import '../services/api_service.dart';

/// State for the inspector dashboard — fetches GET /inspections/log rows and
/// per-record detail from GET /inspections/{id}.
class InspectionLogProvider extends ChangeNotifier {
  final ApiService _api;

  InspectionLogProvider({ApiService? api}) : _api = api ?? ApiService();

  bool _loading = false;
  bool _onlyActionNeeded = false;
  bool _mineOnly = false;
  String? _errorMessage;
  List<InspectionLogRow> _rows = [];

  bool get loading => _loading;
  bool get onlyActionNeeded => _onlyActionNeeded;
  bool get mineOnly => _mineOnly;
  String? get errorMessage => _errorMessage;
  List<InspectionLogRow> get rows => List.unmodifiable(_rows);

  int get actionNeededCount =>
      _rows.where((r) => r.isActionNeeded).length;

  Future<void> refresh() async {
    _loading = true;
    _errorMessage = null;
    notifyListeners();
    try {
      _rows = await _api.getInspectionLog(
        limit: 200,
        onlyActionNeeded: _onlyActionNeeded,
        mine: _mineOnly,
      );
    } catch (e) {
      _errorMessage = _friendlyError(e);
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  Future<void> setOnlyActionNeeded(bool value) async {
    _onlyActionNeeded = value;
    await refresh();
  }

  /// Only the signed-in inspector's own scans.
  Future<void> setMineOnly(bool value) async {
    _mineOnly = value;
    await refresh();
  }

  Future<InspectionDetail?> loadDetail(int evidenceRecordId) async {
    try {
      return await _api.getInspectionDetail(evidenceRecordId);
    } catch (e) {
      _errorMessage = _friendlyError(e);
      notifyListeners();
      return null;
    }
  }

  String _friendlyError(Object e) {
    final msg = e.toString();
    if (msg.contains('SocketException') || msg.contains('Failed host')) {
      return 'Backend unreachable — check your network / API URL.';
    }
    if (msg.contains('401')) return 'Session expired — please sign in again.';
    if (msg.contains('403')) {
      return 'Access denied — inspector or admin role required.';
    }
    return 'Load failed: $msg';
  }
}
