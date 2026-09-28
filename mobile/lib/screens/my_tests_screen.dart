import 'package:flutter/material.dart';

import '../models/test_models.dart';
import '../services/api_service.dart';
import '../utils/app_colors.dart';
import '../widgets/colour_chip.dart';
import 'result_screen.dart';

/// List of the tests I did, newest first.
class MyTestsScreen extends StatefulWidget {
  const MyTestsScreen({super.key});

  @override
  State<MyTestsScreen> createState() => _MyTestsScreenState();
}

class _MyTestsScreenState extends State<MyTestsScreen> {
  late Future<List<TestRecord>> _future;

  @override
  void initState() {
    super.initState();
    _future = ApiService().getMyTests();
  }

  Future<void> _reload() async {
    setState(() => _future = ApiService().getMyTests());
    await _future.catchError((_) => <TestRecord>[]);
  }

  String _when(TestRecord r) {
    final t = DateTime.tryParse(r.createdAt ?? '')?.toLocal();
    if (t == null) return r.createdAt ?? '';
    return '${t.day.toString().padLeft(2, '0')}-${t.month.toString().padLeft(2, '0')}-${t.year} '
        '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('My Tests'),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
      ),
      body: FutureBuilder<List<TestRecord>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(ApiService.friendlyError(snap.error!),
                        textAlign: TextAlign.center),
                    const SizedBox(height: 12),
                    FilledButton(
                        onPressed: _reload, child: const Text('Try again')),
                  ],
                ),
              ),
            );
          }
          final tests = snap.data ?? [];
          if (tests.isEmpty) {
            return const Center(
                child: Text('No tests yet. Tap "New Test" on Home to start.'));
          }
          return RefreshIndicator(
            onRefresh: _reload,
            child: ListView.separated(
              padding: const EdgeInsets.all(12),
              itemCount: tests.length,
              separatorBuilder: (_, __) => const SizedBox(height: 8),
              itemBuilder: (context, i) {
                final r = tests[i];
                return Card(
                  child: ListTile(
                    contentPadding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 6),
                    leading: CircleAvatar(
                      backgroundColor: r.measuredColor ?? Colors.grey.shade300,
                    ),
                    title: Text('Test #${r.id} · ${r.kitName}',
                        maxLines: 1, overflow: TextOverflow.ellipsis),
                    subtitle: Text(
                        '${_when(r)}\n${r.outcomeLabel ?? r.reason ?? ''}',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis),
                    isThreeLine: true,
                    trailing: ResultPill(result: r.result),
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute(
                          builder: (_) => ResultScreen(record: r)),
                    ),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}
