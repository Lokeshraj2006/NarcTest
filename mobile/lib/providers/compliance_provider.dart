import 'package:flutter/foundation.dart';
import '../models/compliance_model.dart';
import '../models/evidence_model.dart';
import '../services/api_service.dart';

/// State management for compliance checks and optical scan evaluation.
class ComplianceProvider extends ChangeNotifier {
  final ApiService _apiService = ApiService();

  ComplianceReport? _currentReport;
  bool _isEvaluating = false;
  String? _errorMessage;

  ComplianceReport? get currentReport => _currentReport;
  bool get isEvaluating => _isEvaluating;
  String? get errorMessage => _errorMessage;

  /// Submits captured evidence and processes compliance response.
  Future<bool> evaluateEvidence(EvidenceMetadata evidence) async {
    _isEvaluating = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final uploadRes = await _apiService.uploadEvidence(evidence);
      final productId = uploadRes['product_id'] as int? ?? 1;

      // Fetch evaluated compliance report
      _currentReport = await _apiService.getCompliance(productId);
      _isEvaluating = false;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = 'Compliance evaluation failed: ${e.toString()}';
      _isEvaluating = false;
      notifyListeners();
      return false;
    }
  }

  void clearReport() {
    _currentReport = null;
    _errorMessage = null;
    notifyListeners();
  }
}
