import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../models/user_model.dart';

/// Secure token and user session storage.
class AuthService {
  static const _storage = FlutterSecureStorage();
  static const _tokenKey = 'jwt_access_token';
  static const _userRoleKey = 'user_role';
  static const _userNameKey = 'user_full_name';

  static Future<void> saveToken(String token) =>
      _storage.write(key: _tokenKey, value: token);

  static Future<String?> getToken() async {
    try {
      return await _storage.read(key: _tokenKey);
    } catch (_) {
      return null;
    }
  }

  static Future<void> saveUserRole(UserRole role) =>
      _storage.write(key: _userRoleKey, value: role.toApiValue());

  static Future<UserRole?> getUserRole() async {
    final val = await _storage.read(key: _userRoleKey);
    if (val == null) return null;
    return UserRole.fromString(val);
  }

  static Future<void> saveFullName(String name) =>
      _storage.write(key: _userNameKey, value: name);

  static Future<String?> getFullName() => _storage.read(key: _userNameKey);

  /// Clears only the login. Server URL and device id stay saved.
  static Future<void> logout() async {
    await _storage.delete(key: _tokenKey);
    await _storage.delete(key: _userRoleKey);
    await _storage.delete(key: _userNameKey);
  }

  static Future<bool> isLoggedIn() async {
    final token = await getToken();
    return token != null && token.isNotEmpty;
  }
}
