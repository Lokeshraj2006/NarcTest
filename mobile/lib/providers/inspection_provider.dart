import 'package:flutter/foundation.dart';
import '../models/complaint_model.dart';
import '../models/inspection_model.dart';
import '../services/api_service.dart';

/// Provider for inspector assignments and consumer complaint workflows.
class InspectionProvider extends ChangeNotifier {
  final ApiService _apiService = ApiService();

  List<InspectionModel> _inspections = [];
  List<ComplaintModel> _complaints = [];
  bool _isLoading = false;
  String? _errorMessage;

  List<InspectionModel> get inspections => _inspections;
  List<ComplaintModel> get complaints => _complaints;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  /// Loads assigned inspections for inspector role.
  Future<void> fetchInspections() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      _inspections = await _apiService.getInspections();
    } catch (e) {
      _errorMessage = 'Failed to load inspections';
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Loads complaints filed by consumer.
  Future<void> fetchComplaints() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      _complaints = await _apiService.getComplaints();
    } catch (e) {
      _errorMessage = 'Failed to load complaints';
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Submit new consumer complaint.
  Future<bool> submitComplaint({
    required String productName,
    String? brandName,
    String? storeName,
    required String description,
    double? latitude,
    double? longitude,
  }) async {
    _isLoading = true;
    notifyListeners();

    try {
      await _apiService.submitComplaint(
        productName: productName,
        brandName: brandName,
        storeName: storeName,
        description: description,
        latitude: latitude,
        longitude: longitude,
      );
      await fetchComplaints();
      _isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = 'Failed to submit complaint';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }
}
