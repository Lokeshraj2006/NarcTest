import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../models/inspection_log_models.dart';
import '../../providers/inspection_log_provider.dart';
import '../../utils/verdict.dart';
import '../../widgets/scan_flags.dart';
import 'inspection_detail_screen.dart';

class InspectionsLogScreen extends StatefulWidget {
  const InspectionsLogScreen({super.key});

  @override
  State<InspectionsLogScreen> createState() => _InspectionsLogScreenState();
}

class _InspectionsLogScreenState extends State<InspectionsLogScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<InspectionLogProvider>().refresh();
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<InspectionLogProvider>();

    return Column(
      children: [
        _filterBar(provider),
        Expanded(child: _body(provider)),
      ],
    );
  }

  Widget _filterBar(InspectionLogProvider provider) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      color: Colors.grey.shade100,
      child: Row(
        children: [
          Expanded(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  FilterChip(
                    label: const Text('Action needed'),
                    selected: provider.onlyActionNeeded,
                    onSelected: (v) => provider.setOnlyActionNeeded(v),
                    selectedColor: Colors.red.shade100,
                  ),
                  const SizedBox(width: 8),
                  // "What have I checked": this inspector's own scans.
                  FilterChip(
                    label: const Text('Mine only'),
                    selected: provider.mineOnly,
                    onSelected: (v) => provider.setMineOnly(v),
                    selectedColor: Colors.blueGrey.shade100,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 8),
          Text('${provider.rows.length} rows',
              style: TextStyle(color: Colors.grey.shade700, fontSize: 12)),
          const SizedBox(width: 8),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: provider.loading ? null : () => provider.refresh(),
          ),
        ],
      ),
    );
  }

  Widget _body(InspectionLogProvider provider) {
    if (provider.loading && provider.rows.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (provider.errorMessage != null && provider.rows.isEmpty) {
      return _errorState(provider.errorMessage!, () => provider.refresh());
    }
    if (provider.rows.isEmpty) {
      return const _EmptyState(
        icon: Icons.assignment_outlined,
        title: 'No inspections logged yet.',
        subtitle:
            'When a consumer or inspector submits a scan, it will appear here.',
      );
    }
    return RefreshIndicator(
      onRefresh: provider.refresh,
      child: ListView.separated(
        padding: const EdgeInsets.all(12),
        itemCount: provider.rows.length,
        separatorBuilder: (_, __) => const SizedBox(height: 8),
        itemBuilder: (context, i) => _rowCard(provider.rows[i]),
      ),
    );
  }

  Widget _rowCard(InspectionLogRow row) {
    final color = Verdict.color(row.overallStatus);
    final subtitle = <String>[
      DateFormat('dd MMM yyyy, HH:mm').format(row.timestamp),
      if (row.capturedByUsername != null) 'by ${row.capturedByUsername}',
      if (row.gpsLatitude != null && row.gpsLongitude != null)
        '${row.gpsLatitude!.toStringAsFixed(4)}, ${row.gpsLongitude!.toStringAsFixed(4)}',
    ].join(' • ');
    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: BorderSide(color: color.withValues(alpha: 0.4)),
      ),
      elevation: 0,
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: color.withValues(alpha: 0.15),
          child: Icon(Icons.location_on, color: color),
        ),
        title: Text(
          row.productName ?? 'Evidence #${row.evidenceRecordId}',
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(subtitle, style: const TextStyle(fontSize: 12)),
            const SizedBox(height: 4),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                Verdict.label(row.overallStatus),
                style: TextStyle(
                  fontSize: 10.5,
                  fontWeight: FontWeight.bold,
                  color: color,
                  letterSpacing: 0.4,
                ),
              ),
            ),
            if (row.actionReason != null) ...[
              const SizedBox(height: 4),
              Text(
                row.actionReason!,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(fontSize: 11.5, color: Colors.grey.shade700),
              ),
            ],
            ScanFlags(row: row),
          ],
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: () {
          Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) =>
                  InspectionDetailScreen(evidenceRecordId: row.evidenceRecordId),
            ),
          );
        },
      ),
    );
  }

  Widget _errorState(String msg, VoidCallback retry) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off, size: 56, color: Colors.grey),
            const SizedBox(height: 12),
            Text(msg, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            FilledButton.icon(
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
              onPressed: retry,
            ),
          ],
        ),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  const _EmptyState({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 60, color: Colors.grey.shade400),
            const SizedBox(height: 12),
            Text(title,
                style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: Colors.grey.shade700)),
            const SizedBox(height: 6),
            Text(subtitle,
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
          ],
        ),
      ),
    );
  }
}
