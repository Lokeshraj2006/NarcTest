import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/auth_provider.dart';
import '../utils/app_colors.dart';
import 'auth/login_screen.dart';
import 'kit_picker_screen.dart';
import 'my_tests_screen.dart';
import 'settings_screen.dart';

/// Home: same screen for every role.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  Future<void> _logout(BuildContext context) async {
    await context.read<AuthProvider>().logout();
    if (!context.mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (_) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final name = context.watch<AuthProvider>().fullName;
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('FieldProof'),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Text(
              name == null || name.isEmpty ? 'Hello!' : 'Hello, $name!',
              style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 4),
            const Text(
              'Test a drug kit, get a sealed record.',
              style: TextStyle(color: AppColors.textSecondary),
            ),
            const SizedBox(height: 24),
            _BigButton(
              icon: Icons.add_a_photo_outlined,
              label: 'New Test',
              subtitle: 'Pick the kit and take a photo',
              color: AppColors.primary,
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const KitPickerScreen()),
              ),
            ),
            const SizedBox(height: 14),
            _BigButton(
              icon: Icons.history,
              label: 'My Tests',
              subtitle: 'See the tests you already did',
              color: Colors.teal.shade700,
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const MyTestsScreen()),
              ),
            ),
            const SizedBox(height: 14),
            _BigButton(
              icon: Icons.settings_outlined,
              label: 'Settings',
              subtitle: 'Change the server address',
              color: Colors.blueGrey.shade600,
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const SettingsScreen()),
              ),
            ),
            const SizedBox(height: 14),
            _BigButton(
              icon: Icons.logout,
              label: 'Logout',
              subtitle: 'Sign out of this phone',
              color: Colors.red.shade400,
              onTap: () => _logout(context),
            ),
          ],
        ),
      ),
    );
  }
}

class _BigButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final String subtitle;
  final Color color;
  final VoidCallback onTap;

  const _BigButton({
    required this.icon,
    required this.label,
    required this.subtitle,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(16),
      elevation: 1,
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Row(
            children: [
              CircleAvatar(
                radius: 28,
                backgroundColor: color.withValues(alpha: 0.12),
                child: Icon(icon, color: color, size: 30),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(label,
                        style: const TextStyle(
                            fontSize: 19, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 2),
                    Text(subtitle,
                        style: const TextStyle(
                            color: AppColors.textSecondary, fontSize: 13)),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right),
            ],
          ),
        ),
      ),
    );
  }
}
