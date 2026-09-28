import 'package:flutter/foundation.dart';
import '../models/pending_complaint_model.dart';
import '../services/api_service.dart';

/// State for the inspector's "pending complaints" tab (GET /complaints/pending).
class PendingComplaintsProvider extends ChangeNotifier {
  final ApiService _api;

  PendingComplaintsProvider({ApiService? api}) : _api = api ?? ApiService();

  bool _loading = false;
  String? _errorMessage;
  List<PendingComplaintRow> _rows = [];

  bool get loading => _loading;
  String? get errorMessage => _errorMessage;
  List<PendingComplaintRow> get rows => List.unmodifiable(_rows);
  int get pendingCount => _rows.length;

  Future<void> refresh() async {
    _loading = true;
    _errorMessage = null;
    notifyListeners();
    try {
      _rows = await _api.getPendingComplaints(limit: 200);
    } catch (e) {
      _errorMessage = _friendlyError(e);
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  String _friendlyError(Object e) {
    final msg = e.toString();
    if (msg.contains('SocketException')) {
      return 'Backend unreachable — check your network / API URL.';
    }
    if (msg.contains('401')) return 'Session expired — please sign in again.';
    if (msg.contains('403')) {
      return 'Access denied — inspector or admin role required.';
    }
    return 'Load failed: $msg';
  }
}
