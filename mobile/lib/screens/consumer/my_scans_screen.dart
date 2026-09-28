import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../models/inspection_log_models.dart';
import '../../services/api_service.dart';
import '../../utils/verdict.dart';
import '../../widgets/scan_flags.dart';
import '../inspector/inspection_detail_screen.dart';

/// The signed-in user's own scans, newest first: verdict, what happened to
/// the complaint, and audit flags. Read-only — a scan can be rescanned from
/// its detail page, never edited.
class MyScansScreen extends StatefulWidget {
  const MyScansScreen({super.key});

  @override
  State<MyScansScreen> createState() => _MyScansScreenState();
}

class _MyScansScreenState extends State<MyScansScreen> {
  final _api = ApiService();
  List<InspectionLogRow> _rows = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final rows = await _api.getMyScanHistory();
      if (!mounted) return;
      setState(() => _rows = rows);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString().contains('401')
          ? 'Session expired — please sign in again.'
          : 'Could not load your scans. Check the backend connection.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My scans'),
        backgroundColor: Colors.indigo.shade700,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loading ? null : _load,
          ),
        ],
      ),
      body: _body(),
    );
  }

  Widget _body() {
    if (_loading && _rows.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null && _rows.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(_error!, textAlign: TextAlign.center),
        ),
      );
    }
    if (_rows.isEmpty) {
      return const Center(child: Text('You have no scans yet.'));
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.all(12),
        itemCount: _rows.length,
        separatorBuilder: (_, __) => const SizedBox(height: 8),
        itemBuilder: (context, i) => _card(context, _rows[i]),
      ),
    );
  }

  Widget _card(BuildContext context, InspectionLogRow row) {
    final color = Verdict.color(row.overallStatus);
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: BorderSide(color: color.withValues(alpha: 0.4)),
      ),
      child: ListTile(
        leading: Icon(Verdict.icon(row.overallStatus), color: color),
        title: Text(
          row.productName ?? 'Scan #${row.evidenceRecordId}',
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Scan #${row.evidenceRecordId} • '
              '${DateFormat('dd MMM yyyy, HH:mm').format(row.timestamp)}',
              style: const TextStyle(fontSize: 12),
            ),
            const SizedBox(height: 2),
            Text(
              Verdict.label(row.overallStatus),
              style: TextStyle(
                  fontSize: 11, fontWeight: FontWeight.bold, color: color),
            ),
            if (row.actionReason != null)
              Text(
                row.actionReason!,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(fontSize: 11.5, color: Colors.grey.shade700),
              ),
            ScanFlags(row: row),
          ],
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: () async {
          await Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) =>
                  InspectionDetailScreen(evidenceRecordId: row.evidenceRecordId),
            ),
          );
          // A rescan started from the detail page adds a row.
          _load();
        },
      ),
    );
  }
}
