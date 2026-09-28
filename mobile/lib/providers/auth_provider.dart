import 'package:flutter/foundation.dart';
import '../models/user_model.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

/// Login state: who is logged in and their role.
class AuthProvider extends ChangeNotifier {
  final ApiService _apiService = ApiService();

  UserModel? _currentUser;
  UserRole? _userRole;
  String? _fullName;
  bool _isLoading = false;
  String? _errorMessage;

  UserModel? get currentUser => _currentUser;
  UserRole? get userRole => _userRole;
  String? get fullName => _currentUser?.fullName ?? _fullName;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  bool get isAuthenticated => _userRole != null;

  Future<void> checkSession() async {
    _isLoading = true;
    notifyListeners();
    try {
      if (await AuthService.isLoggedIn()) {
        _userRole = await AuthService.getUserRole() ?? UserRole.fieldOfficer;
        _fullName = await AuthService.getFullName();
      }
    } catch (_) {
      _currentUser = null;
      _userRole = null;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> login(String usernameOrEmail, String password) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();
    try {
      final res = await _apiService.login(usernameOrEmail, password);
      final token = res['access_token'] as String;
      final role = UserRole.fromString(res['role']?.toString() ?? '');
      _currentUser = UserModel(
        id: (res['user_id'] as num?)?.toInt() ?? 0,
        email: usernameOrEmail.contains('@') ? usernameOrEmail : '',
        username: res['username']?.toString() ?? usernameOrEmail,
        fullName: res['full_name']?.toString() ?? usernameOrEmail,
        role: role,
      );
      _userRole = role;
      await AuthService.saveToken(token);
      await AuthService.saveUserRole(role);
      await AuthService.saveFullName(_currentUser!.fullName);
      return true;
    } catch (e) {
      final msg = ApiService.friendlyError(e);
      _errorMessage = msg.startsWith('Cannot reach')
          ? msg
          : 'Wrong username or password. Please try again.';
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> logout() async {
    await AuthService.logout();
    _currentUser = null;
    _userRole = null;
    _fullName = null;
    _errorMessage = null;
    notifyListeners();
  }
}
