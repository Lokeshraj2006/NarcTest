import 'package:flutter/foundation.dart';
import '../models/user_model.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

/// Authentication state provider managing user session, role, and tokens.
class AuthProvider extends ChangeNotifier {
  final ApiService _apiService = ApiService();

  UserModel? _currentUser;
  UserRole? _userRole;
  bool _isLoading = false;
  String? _errorMessage;

  UserModel? get currentUser => _currentUser;
  UserRole? get userRole => _userRole;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  bool get isAuthenticated => _currentUser != null;

  /// Check persisted session on app launch.
  Future<void> checkSession() async {
    _isLoading = true;
    notifyListeners();

    try {
      final hasToken = await AuthService.isLoggedIn();
      if (hasToken) {
        _userRole = await AuthService.getUserRole() ?? UserRole.consumer;
      }
    } catch (_) {
      _currentUser = null;
      _userRole = null;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Perform login and route by role.
  Future<bool> login(String usernameOrEmail, String password) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final res = await _apiService.login(usernameOrEmail, password);
      final token = res['access_token'] as String;
      final roleStr = res['role'] as String? ?? 'consumer';
      final role = UserRole.fromString(roleStr);

      _currentUser = UserModel(
        id: res['user_id'] as int? ?? 0,
        email: usernameOrEmail.contains('@') ? usernameOrEmail : '',
        username: res['username'] as String? ?? usernameOrEmail,
        fullName: res['full_name'] as String? ?? 'User',
        role: role,
      );
      _userRole = role;

      await AuthService.saveToken(token);
      await AuthService.saveUserRole(role);

      _isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = 'Invalid username/email or password';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Log out and clear session.
  Future<void> logout() async {
    await AuthService.logout();
    _currentUser = null;
    _userRole = null;
    _errorMessage = null;
    notifyListeners();
  }
}
