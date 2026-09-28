import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../providers/inspection_log_provider.dart';
import '../../providers/pending_complaints_provider.dart';
import '../auth/login_screen.dart';
import '../consumer/scan_capture_screen.dart';
import '../settings_screen.dart';
import 'inspection_map_screen.dart';
import 'inspections_log_screen.dart';
import 'pending_complaints_screen.dart';

class InspectorHomeScreen extends StatefulWidget {
  const InspectorHomeScreen({super.key});

  @override
  State<InspectorHomeScreen> createState() => _InspectorHomeScreenState();
}

class _InspectorHomeScreenState extends State<InspectorHomeScreen> {
  int _currentIndex = 0;

  /// A fresh scan on site, not tied to any complaint. The server opens no
  /// complaint for an inspector's scan; a FAIL can be reported from its detail.
  Future<void> _newScan() async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const ScanCaptureScreen()),
    );
    if (!mounted) return;
    setState(() => _currentIndex = 0);
    await context.read<InspectionLogProvider>().refresh();
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final pending = context.watch<PendingComplaintsProvider>();
    final user = auth.currentUser;

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Inspector Portal', style: TextStyle(fontSize: 18)),
            if (user?.badgeNumber != null)
              Text(
                'Badge: ${user!.badgeNumber}',
                style: const TextStyle(fontSize: 11, color: Colors.white70),
              ),
          ],
        ),
        backgroundColor: Colors.blueGrey.shade900,
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
      body: IndexedStack(
        index: _currentIndex,
        children: const [
          InspectionsLogScreen(),
          InspectionMapScreen(),
          PendingComplaintsScreen(),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _newScan,
        backgroundColor: Colors.blueGrey.shade900,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.document_scanner_outlined),
        label: const Text('New scan'),
      ),
      bottomNavigationBar: BottomNavigationBar(
        // Fixed: with 3+ items the default 'shifting' type hides labels.
        type: BottomNavigationBarType.fixed,
        currentIndex: _currentIndex,
        onTap: (i) => setState(() => _currentIndex = i),
        selectedItemColor: Colors.blueGrey.shade900,
        unselectedItemColor: Colors.grey.shade600,
        items: [
          const BottomNavigationBarItem(
            icon: Icon(Icons.assignment_outlined),
            activeIcon: Icon(Icons.assignment),
            label: 'Inspections',
          ),
          const BottomNavigationBarItem(
            icon: Icon(Icons.map_outlined),
            activeIcon: Icon(Icons.map),
            label: 'Map',
          ),
          BottomNavigationBarItem(
            icon: _pendingBadge(pending.pendingCount,
                const Icon(Icons.pending_actions_outlined)),
            activeIcon: _pendingBadge(pending.pendingCount,
                const Icon(Icons.pending_actions)),
            label: 'Pending',
          ),
        ],
      ),
    );
  }

  Widget _pendingBadge(int count, Widget child) {
    if (count == 0) return child;
    return Stack(
      clipBehavior: Clip.none,
      children: [
        child,
        Positioned(
          right: -6,
          top: -4,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
            decoration: BoxDecoration(
              color: Colors.red.shade600,
              borderRadius: BorderRadius.circular(10),
            ),
            constraints: const BoxConstraints(minWidth: 18, minHeight: 18),
            child: Text(
              count > 99 ? '99+' : '$count',
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 10,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
