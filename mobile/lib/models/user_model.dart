/// User model matching backend RBAC roles: consumer, inspector, admin.
enum UserRole {
  consumer,
  inspector,
  admin;

  static UserRole fromString(String role) {
    switch (role.toLowerCase()) {
      case 'admin':
        return UserRole.admin;
      case 'inspector':
        return UserRole.inspector;
      case 'consumer':
      default:
        return UserRole.consumer;
    }
  }

  String toApiValue() => name;
}

class UserModel {
  final int id;
  final String email;
  final String username;
  final String fullName;
  final UserRole role;
  final String? badgeNumber;
  final String? phoneNumber;
  final bool isActive;

  UserModel({
    required this.id,
    required this.email,
    required this.username,
    required this.fullName,
    required this.role,
    this.badgeNumber,
    this.phoneNumber,
    this.isActive = true,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'] as int? ?? json['user_id'] as int? ?? 0,
      email: json['email'] as String? ?? '',
      username: json['username'] as String? ?? '',
      fullName: json['full_name'] as String? ?? '',
      role: UserRole.fromString(json['role'] as String? ?? 'consumer'),
      badgeNumber: json['badge_number'] as String?,
      phoneNumber: json['phone_number'] as String?,
      isActive: json['is_active'] as bool? ?? true,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'email': email,
      'username': username,
      'full_name': fullName,
      'role': role.toApiValue(),
      'badge_number': badgeNumber,
      'phone_number': phoneNumber,
      'is_active': isActive,
    };
  }
}
