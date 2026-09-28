import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../providers/pending_complaints_provider.dart';
import 'inspection_detail_screen.dart';

class PendingComplaintsScreen extends StatefulWidget {
  const PendingComplaintsScreen({super.key});

  @override
  State<PendingComplaintsScreen> createState() =>
      _PendingComplaintsScreenState();
}

class _PendingComplaintsScreenState extends State<PendingComplaintsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<PendingComplaintsProvider>().refresh();
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<PendingComplaintsProvider>();

    if (provider.loading && provider.rows.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (provider.errorMessage != null && provider.rows.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off, size: 56, color: Colors.grey),
              const SizedBox(height: 12),
              Text(provider.errorMessage!, textAlign: TextAlign.center),
              const SizedBox(height: 12),
              FilledButton.icon(
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
                onPressed: () => provider.refresh(),
              ),
            ],
          ),
        ),
      );
    }
    if (provider.rows.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.mark_email_read_outlined,
                  size: 60, color: Colors.grey),
              SizedBox(height: 12),
              Text('No complaints awaiting review.',
                  style: TextStyle(fontWeight: FontWeight.bold)),
              SizedBox(height: 4),
              Text(
                'When a consumer scan flags action_needed, it will appear here.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 12, color: Colors.grey),
              ),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: provider.refresh,
      child: ListView.separated(
        padding: const EdgeInsets.all(12),
        itemCount: provider.rows.length,
        separatorBuilder: (_, __) => const SizedBox(height: 8),
        itemBuilder: (context, i) {
          final row = provider.rows[i];
          return Card(
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
              side: BorderSide(color: Colors.orange.shade300),
            ),
            child: ListTile(
              leading: CircleAvatar(
                backgroundColor: Colors.orange.shade100,
                child: Text('#${row.complaintId}',
                    style: TextStyle(
                        fontSize: 10, color: Colors.orange.shade800)),
              ),
              title: Text(row.productName ?? 'Unknown product',
                  style: const TextStyle(fontWeight: FontWeight.w600)),
              subtitle: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Filed ${DateFormat('dd MMM yyyy, HH:mm').format(row.filedAt)}',
                    style: const TextStyle(fontSize: 12),
                  ),
                  if (row.actionReason != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(row.actionReason!,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                              fontSize: 11.5, color: Colors.grey.shade700)),
                    ),
                ],
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: row.evidenceRecordId == null
                  ? null
                  : () {
                      Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => InspectionDetailScreen(
                            evidenceRecordId: row.evidenceRecordId!,
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
