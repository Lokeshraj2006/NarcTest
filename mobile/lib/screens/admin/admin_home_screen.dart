import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../services/settings_service.dart';
import '../../utils/app_colors.dart';
import '../auth/login_screen.dart';

/// Administrators do not work from the mobile app.
///
/// The field app is for consumers (scan and report) and inspectors (inspect,
/// file violation reports). Reviewing reports and issuing GO notices is the
/// Controller's authority and happens on the web dashboard, where the full
/// case file, evidence and map are available on a proper screen.
///
/// This screen exists so an admin who signs in on a phone gets a clear
/// explanation instead of an empty or broken-looking home screen.
class AdminHomeScreen extends StatelessWidget {
  const AdminHomeScreen({super.key});

  /// Derive the dashboard URL from the configured API host — the dashboard
  /// is served alongside the backend, so the host is the same.
  String get _dashboardUrl {
    final api = SettingsService.apiBaseUrl;
    final uri = Uri.tryParse(api);
    if (uri == null || uri.host.isEmpty) return 'http://<server>:5173';
    return 'http://${uri.host}:5173';
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Administrator'),
        backgroundColor: AppColors.inspectorPrimary,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Sign out',
            onPressed: () async {
              await auth.logout();
              if (context.mounted) {
                Navigator.of(context).pushReplacement(
                  MaterialPageRoute(builder: (_) => const LoginScreen()),
                );
              }
            },
          ),
        ],
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.desktop_windows_outlined,
                    size: 52, color: AppColors.primary),
              ),
              const SizedBox(height: 20),
              Text(
                'Signed in as ${auth.currentUser?.fullName ?? 'Administrator'}',
                style: const TextStyle(
                    fontSize: 16, fontWeight: FontWeight.w600),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 6),
              const Text(
                'Administrator tools are on the web dashboard',
                style: TextStyle(
                    fontSize: 13, color: AppColors.textSecondary),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 22),
              _reasonCard(),
              const SizedBox(height: 16),
              _urlCard(),
              const SizedBox(height: 22),
              OutlinedButton.icon(
                icon: const Icon(Icons.logout, size: 18),
                label: const Text('Sign out'),
                onPressed: () async {
                  await auth.logout();
                  if (context.mounted) {
                    Navigator.of(context).pushReplacement(
                      MaterialPageRoute(builder: (_) => const LoginScreen()),
                    );
                  }
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _reasonCard() {
    Widget row(IconData icon, String who, String what) => Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, size: 18, color: AppColors.primary),
              const SizedBox(width: 10),
              Expanded(
                child: RichText(
                  text: TextSpan(
                    style: const TextStyle(
                        fontSize: 12.5,
                        height: 1.35,
                        color: AppColors.textPrimary),
                    children: [
                      TextSpan(
                          text: '$who — ',
                          style: const TextStyle(fontWeight: FontWeight.bold)),
                      TextSpan(text: what),
                    ],
                  ),
                ),
              ),
            ],
          ),
        );

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: AppColors.border),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Who does what',
                style:
                    TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
            const SizedBox(height: 4),
            row(Icons.phone_android, 'Consumer',
                'scans a product and reports it to an inspector'),
            row(Icons.badge_outlined, 'Inspector',
                'visits the shop, scans, and files a violation report'),
            row(Icons.gavel, 'Administrator',
                'reviews reports and issues the GO notice — on the dashboard'),
          ],
        ),
      ),
    );
  }

  Widget _urlCard() {
    return Card(
      elevation: 0,
      color: AppColors.primary.withValues(alpha: 0.06),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: AppColors.primary.withValues(alpha: 0.35)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          children: [
            const Text('Open on a computer',
                style: TextStyle(
                    fontSize: 12, color: AppColors.textSecondary)),
            const SizedBox(height: 6),
            SelectableText(
              _dashboardUrl,
              style: const TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.bold,
                color: AppColors.primary,
                fontFamily: 'monospace',
              ),
            ),
          ],
        ),
      ),
    );
  }
}
