import 'package:flutter/material.dart';

import '../l10n/lang.dart';
import '../models/test_models.dart';
import '../services/api_service.dart';
import '../utils/app_colors.dart';
import '../widgets/colour_chip.dart';
import 'capture_screen.dart';

/// Step 1: pick which test kit you are using.
class KitPickerScreen extends StatefulWidget {
  const KitPickerScreen({super.key});

  @override
  State<KitPickerScreen> createState() => _KitPickerScreenState();
}

class _KitPickerScreenState extends State<KitPickerScreen> {
  late Future<List<KitProfile>> _future;

  @override
  void initState() {
    super.initState();
    _future = ApiService().getKits();
  }

  void _reload() => setState(() => _future = ApiService().getKits());

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(tr(context, 'Pick your test kit')),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
      ),
      body: FutureBuilder<List<KitProfile>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return _Message(
              text: tr(context, ApiService.friendlyError(snap.error!)),
              onRetry: _reload,
            );
          }
          final kits = snap.data ?? [];
          if (kits.isEmpty) {
            return _Message(
                text: tr(context, 'No test kits found on the server.'),
                onRetry: _reload);
          }
          return RefreshIndicator(
            onRefresh: () async => _reload(),
            child: ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: kits.length,
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemBuilder: (context, i) => _KitCard(kit: kits[i]),
            ),
          );
        },
      ),
    );
  }
}

class _KitCard extends StatelessWidget {
  final KitProfile kit;
  const _KitCard({required this.kit});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      elevation: 1,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => CaptureScreen(kit: kit)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(kit.name,
                  style: const TextStyle(
                      fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              Text(kit.reagent,
                  style: const TextStyle(color: AppColors.textSecondary)),
              const SizedBox(height: 6),
              Row(
                children: [
                  const Icon(Icons.timer_outlined, size: 18),
                  const SizedBox(width: 4),
                  Text(tr(context, 'Wait {0} seconds before reading', [kit.readTimeS])),
                ],
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 6,
                runSpacing: 8,
                children: [
                  for (final o in kit.outcomes)
                    ColourChip(color: o.color, label: tr(context, o.label), size: 40),
                ],
              ),
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerRight,
                child: FilledButton.icon(
                  onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => CaptureScreen(kit: kit)),
                  ),
                  icon: const Icon(Icons.camera_alt),
                  label: Text(tr(context, 'Use this kit')),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Message extends StatelessWidget {
  final String text;
  final VoidCallback onRetry;
  const _Message({required this.text, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off, size: 48, color: Colors.black38),
            const SizedBox(height: 12),
            Text(text, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            FilledButton(onPressed: onRetry, child: Text(tr(context, 'Try again'))),
          ],
        ),
      ),
    );
  }
}
