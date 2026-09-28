import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../models/user_model.dart';

/// Secure token & user session management via FlutterSecureStorage.
class AuthService {
  static const _storage = FlutterSecureStorage();
  static const _tokenKey = 'jwt_access_token';
  static const _userRoleKey = 'user_role';

  /// Saves JWT access token.
  static Future<void> saveToken(String token) async {
    await _storage.write(key: _tokenKey, value: token);
  }

  /// Retrieves stored JWT access token.
  static Future<String?> getToken() async {
    return await _storage.read(key: _tokenKey);
  }

  /// Saves user role for quick navigation checks.
  static Future<void> saveUserRole(UserRole role) async {
    await _storage.write(key: _userRoleKey, value: role.name);
  }

  /// Retrieves user role.
  static Future<UserRole?> getUserRole() async {
    final val = await _storage.read(key: _userRoleKey);
    if (val == null) return null;
    return UserRole.fromString(val);
  }

  /// Clear session credentials upon logout.
  static Future<void> logout() async {
    await _storage.deleteAll();
  }

  /// Check if an active session exists.
  static Future<bool> isLoggedIn() async {
    final token = await getToken();
    return token != null && token.isNotEmpty;
  }
}
