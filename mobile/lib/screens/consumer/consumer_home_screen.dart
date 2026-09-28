import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/scan_models.dart';
import '../../providers/auth_provider.dart';
import '../../providers/scan_provider.dart';
import '../../utils/verdict.dart';
import '../auth/login_screen.dart';
import '../settings_screen.dart';
import 'my_scans_screen.dart';
import 'scan_capture_screen.dart';
import 'scan_result_screen.dart';

/// Consumer home screen — quick access to scan-label + view last verdict.
class ConsumerHomeScreen extends StatelessWidget {
  const ConsumerHomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final scan = context.watch<ScanProvider>();
    final last = scan.lastResult;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Consumer Portal'),
        backgroundColor: Colors.indigo.shade700,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            tooltip: 'Backend settings',
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const SettingsScreen()),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.logout),
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
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _welcomeCard(auth.currentUser?.fullName ?? 'Consumer'),
          const SizedBox(height: 16),
          _rightsCard(),
          const SizedBox(height: 16),
          _scanButton(context),
          const SizedBox(height: 12),
          _historyButton(context),
          if (last != null) ...[
            const SizedBox(height: 24),
            _lastResultCard(context, last),
          ],
        ],
      ),
    );
  }

  Widget _welcomeCard(String name) {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      color: Colors.indigo.shade50,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(children: [
          CircleAvatar(
            backgroundColor: Colors.indigo.shade600,
            child: const Icon(Icons.person, color: Colors.white),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Welcome',
                    style: TextStyle(fontSize: 12, color: Colors.black54)),
                Text(name,
                    style: const TextStyle(
                        fontSize: 16, fontWeight: FontWeight.w600)),
              ],
            ),
          ),
        ]),
      ),
    );
  }

  Widget _rightsCard() {
    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(Icons.verified, color: Colors.indigo.shade600),
              const SizedBox(width: 8),
              const Text(
                'Know Your Consumer Rights',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
              ),
            ]),
            const SizedBox(height: 8),
            const Text(
              'Under Legal Metrology Rules, every packaged commodity must declare: '
              'MRP, Net Quantity, Mfg/Expiry date, and Manufacturer details.',
              style: TextStyle(fontSize: 13, color: Colors.black87),
            ),
          ],
        ),
      ),
    );
  }

  Widget _scanButton(BuildContext context) {
    return FilledButton.icon(
      style: FilledButton.styleFrom(
        backgroundColor: Colors.indigo.shade600,
        minimumSize: const Size.fromHeight(56),
      ),
      icon: const Icon(Icons.qr_code_scanner),
      label: const Text(
        'Scan Label',
        style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
      ),
      onPressed: () {
        Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const ScanCaptureScreen()),
        );
      },
    );
  }

  Widget _historyButton(BuildContext context) {
    return OutlinedButton.icon(
      style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(52)),
      icon: const Icon(Icons.history),
      label: const Text(
        'My scans',
        style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
      ),
      onPressed: () => Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => const MyScansScreen()),
      ),
    );
  }

  Widget _lastResultCard(BuildContext context, ScanResponse last) {
    final color = Verdict.color(last.overallStatus);
    return Card(
      color: color.withValues(alpha: 0.06),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: color),
      ),
      child: ListTile(
        leading: Icon(Verdict.icon(last.overallStatus), color: color),
        title: Text(
          last.productName ?? 'Last scan',
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        subtitle: Text(
          Verdict.label(last.overallStatus),
          style: TextStyle(color: color, fontWeight: FontWeight.bold),
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: () {
          Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => ScanResultScreen(result: last),
            ),
          );
        },
      ),
    );
  }
}
