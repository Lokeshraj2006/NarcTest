/// User roles used by the FieldProof backend: field_officer, supervisor, admin.
enum UserRole {
  fieldOfficer,
  supervisor,
  admin;

  static UserRole fromString(String role) {
    switch (role.toLowerCase()) {
      case 'admin':
        return UserRole.admin;
      case 'supervisor':
        return UserRole.supervisor;
      default:
        return UserRole.fieldOfficer;
    }
  }

  String toApiValue() => switch (this) {
        UserRole.fieldOfficer => 'field_officer',
        UserRole.supervisor => 'supervisor',
        UserRole.admin => 'admin',
      };
}

class UserModel {
  final int id;
  final String email;
  final String username;
  final String fullName;
  final UserRole role;

  UserModel({
    required this.id,
    required this.email,
    required this.username,
    required this.fullName,
    required this.role,
  });
}
