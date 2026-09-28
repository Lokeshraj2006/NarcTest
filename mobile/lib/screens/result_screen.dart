import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/test_models.dart';
import '../utils/app_colors.dart';
import '../widgets/colour_chip.dart';

/// Step 4: the result with the sealed record details.
class ResultScreen extends StatelessWidget {
  final TestRecord record;
  const ResultScreen({super.key, required this.record});

  static const disclaimer =
      'Presumptive field result — not a substitute for laboratory confirmatory testing.';

  String _short(String s) => s.length > 16 ? '${s.substring(0, 16)}...' : s;

  String _time() {
    final t = record.ntpTime ?? record.createdAt;
    if (t == null) return '-';
    final parsed = DateTime.tryParse(t)?.toLocal();
    final shown = parsed == null
        ? t
        : '${parsed.day.toString().padLeft(2, '0')}-'
            '${parsed.month.toString().padLeft(2, '0')}-${parsed.year} '
            '${parsed.hour.toString().padLeft(2, '0')}:'
            '${parsed.minute.toString().padLeft(2, '0')}:'
            '${parsed.second.toString().padLeft(2, '0')}';
    final src = record.timeSource == 'ntp' ? 'internet time' : 'server clock';
    return '$shown ($src)';
  }

  String _gps() {
    final lat = record.latitude, lon = record.longitude;
    if (lat == null || lon == null) return 'Not available';
    var s = '${lat.toStringAsFixed(5)}, ${lon.toStringAsFixed(5)}';
    if (record.gpsAccuracyM != null) {
      s += ' (±${record.gpsAccuracyM!.round()} m)';
    }
    if (record.gpsIsMock) s += ' - FAKE GPS!';
    return s;
  }

  Future<void> _openVerify(BuildContext context) async {
    final url = record.verifyUrl;
    if (url == null || url.isEmpty) return;
    final ok = await launchUrl(Uri.parse(url),
        mode: LaunchMode.externalApplication);
    if (!ok && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not open $url')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final result = record.result;
    final colour = AppColors.forResult(result);
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text('Test #${record.id}'),
        backgroundColor: colour,
        foregroundColor: Colors.white,
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Big banner
          Container(
            padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 16),
            decoration: BoxDecoration(
              color: colour,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              children: [
                Icon(
                  switch (result) {
                    'POSITIVE' => Icons.warning_amber_rounded,
                    'NEGATIVE' => Icons.check_circle_outline,
                    _ => Icons.help_outline,
                  },
                  color: Colors.white,
                  size: 48,
                ),
                const SizedBox(height: 8),
                Text(
                  AppColors.resultTitle(result),
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                      color: Colors.white,
                      fontSize: 28,
                      fontWeight: FontWeight.bold),
                ),
                if (record.outcomeLabel != null) ...[
                  const SizedBox(height: 6),
                  Text(record.outcomeLabel!,
                      textAlign: TextAlign.center,
                      style:
                          const TextStyle(color: Colors.white, fontSize: 18)),
                ],
                if (record.confidence != null && result != 'INCONCLUSIVE') ...[
                  const SizedBox(height: 6),
                  Text('${record.confidence}% sure',
                      style: const TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.w600)),
                ],
              ],
            ),
          ),
          if (record.reason != null && record.reason!.isNotEmpty) ...[
            const SizedBox(height: 12),
            Card(
              color: Colors.amber.shade50,
              child: ListTile(
                leading: const Icon(Icons.info_outline),
                title: Text(record.reason!),
              ),
            ),
          ],
          const SizedBox(height: 16),

          // Colours
          _section(
            'Colour seen vs kit colours',
            Wrap(
              spacing: 6,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.start,
              children: [
                ColourChip(
                  color: record.measuredColor,
                  label: 'Your test',
                  highlight: true,
                  size: 56,
                ),
                for (final o in record.kitOutcomes)
                  ColourChip(
                    color: o.color,
                    label: o.label,
                    highlight: o.label == record.outcomeLabel,
                  ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // Record card
          _section(
            'Record details',
            Column(
              children: [
                _row('Test ID', '#${record.id}'),
                _row('Kit', record.kitName),
                _row('Time', _time()),
                _row('GPS', _gps()),
                _row('Officer', record.officerName),
                _row('Photo hash', _short(record.imageSha256)),
                _row('Record hash', _short(record.recordHash)),
                const SizedBox(height: 8),
                Row(
                  children: [
                    const Icon(Icons.verified, color: AppColors.negative),
                    const SizedBox(width: 6),
                    const Text('Sealed & signed',
                        style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: AppColors.negative)),
                    if (record.clientHashMatch == false) ...[
                      const SizedBox(width: 8),
                      const Flexible(
                        child: Text('(photo hash did not match!)',
                            style: TextStyle(color: Colors.red)),
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 52,
            child: FilledButton.icon(
              onPressed: (record.verifyUrl ?? '').isEmpty
                  ? null
                  : () => _openVerify(context),
              icon: const Icon(Icons.open_in_new),
              label: const Text('Open verify page',
                  style: TextStyle(fontSize: 16)),
            ),
          ),
          const SizedBox(height: 16),
          const Text(
            disclaimer,
            textAlign: TextAlign.center,
            style: TextStyle(
                fontSize: 13,
                fontStyle: FontStyle.italic,
                color: AppColors.textSecondary),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }

  Widget _section(String title, Widget child) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style:
                  const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          child,
        ],
      ),
    );
  }

  Widget _row(String k, String v) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 100,
            child: Text(k,
                style: const TextStyle(color: AppColors.textSecondary)),
          ),
          Expanded(
            child: Text(v,
                style: const TextStyle(fontWeight: FontWeight.w500)),
          ),
        ],
      ),
    );
  }
}
