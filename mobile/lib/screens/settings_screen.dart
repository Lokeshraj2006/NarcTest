import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/settings_service.dart';
import '../utils/app_colors.dart';

/// Lets the user point the app at a different backend without rebuilding.
///
/// Needed because on a phone hotspot the laptop's LAN IP changes whenever
/// the hotspot restarts, and a compile-time-only URL would mean shipping a
/// new APK each time.
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _urlCtl;
  String? _validationError;
  bool _testing = false;
  String? _testResult;
  bool _testOk = false;
  bool _saved = false;

  @override
  void initState() {
    super.initState();
    _urlCtl = TextEditingController(text: SettingsService.apiBaseUrl);
  }

  @override
  void dispose() {
    _urlCtl.dispose();
    super.dispose();
  }

  Future<void> _test() async {
    final err = SettingsService.validate(_urlCtl.text);
    if (err != null) {
      setState(() {
        _validationError = err;
        _testResult = null;
      });
      return;
    }

    setState(() {
      _validationError = null;
      _testing = true;
      _testResult = null;
    });

    final url = SettingsService.normalizeUrl(_urlCtl.text);
    try {
      final health = await ApiService().checkHealth(overrideBaseUrl: url);
      if (!mounted) return;
      setState(() {
        _testOk = true;
        _testResult =
            'Connected — ${health['app'] ?? 'backend'} v${health['version'] ?? '?'}';
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _testOk = false;
        _testResult = _friendly(e);
      });
    } finally {
      if (mounted) setState(() => _testing = false);
    }
  }

  String _friendly(Object e) {
    final m = e.toString();
    if (m.contains('SocketException') ||
        m.contains('Connection refused') ||
        m.contains('Failed host')) {
      return 'Could not reach that address. Check the IP, that the backend is '
          'running, and that the firewall allows the port.';
    }
    if (m.contains('timeout') || m.contains('Timeout')) {
      return 'Timed out. Usually means a firewall is dropping the connection.';
    }
    if (m.contains('404')) {
      return 'Reached a server, but it has no /health endpoint. Wrong address?';
    }
    return 'Failed: $m';
  }

  Future<void> _save() async {
    final err = SettingsService.validate(_urlCtl.text);
    if (err != null) {
      setState(() => _validationError = err);
      return;
    }
    await SettingsService.setApiBaseUrl(_urlCtl.text);
    if (!mounted) return;
    setState(() {
      _validationError = null;
      _saved = true;
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Backend set to ${SettingsService.apiBaseUrl}')),
    );
  }

  Future<void> _reset() async {
    await SettingsService.clearApiBaseUrl();
    if (!mounted) return;
    setState(() {
      _urlCtl.text = SettingsService.defaultBaseUrl;
      _validationError = null;
      _testResult = null;
      _saved = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Settings'),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _explainer(),
          const SizedBox(height: 16),
          TextField(
            controller: _urlCtl,
            keyboardType: TextInputType.url,
            autocorrect: false,
            style: const TextStyle(fontSize: 15),
            decoration: InputDecoration(
              labelText: 'Backend address',
              hintText: '192.168.1.42:8000',
              helperText: 'http:// is added automatically if you omit it',
              errorText: _validationError,
              filled: true,
              fillColor: AppColors.surface,
              prefixIcon: const Icon(Icons.dns_outlined),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
            onChanged: (_) => setState(() {
              _validationError = null;
              _testResult = null;
              _saved = false;
            }),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  icon: _testing
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.wifi_tethering),
                  label: Text(_testing ? 'Testing…' : 'Test connection'),
                  onPressed: _testing ? null : _test,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: FilledButton.icon(
                  style: FilledButton.styleFrom(
                      backgroundColor: AppColors.primary),
                  icon: Icon(_saved ? Icons.check : Icons.save_outlined),
                  label: Text(_saved ? 'Saved' : 'Save'),
                  onPressed: _save,
                ),
              ),
            ],
          ),
          if (_testResult != null) ...[
            const SizedBox(height: 12),
            _testResultCard(),
          ],
          const SizedBox(height: 20),
          _currentValuesCard(),
          const SizedBox(height: 12),
          TextButton.icon(
            icon: const Icon(Icons.restart_alt),
            label: Text('Reset to built-in default '
                '(${SettingsService.defaultBaseUrl})'),
            onPressed: _reset,
          ),
        ],
      ),
    );
  }

  Widget _explainer() {
    return Card(
      elevation: 0,
      color: AppColors.primary.withValues(alpha: 0.06),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: AppColors.primary.withValues(alpha: 0.3)),
      ),
      child: const Padding(
        padding: EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(Icons.info_outline, size: 20, color: AppColors.primary),
              SizedBox(width: 8),
              Text('Backend address',
                  style: TextStyle(
                      fontWeight: FontWeight.bold, color: AppColors.primary)),
            ]),
            SizedBox(height: 8),
            Text(
              'Point this at the machine running the FieldProof API. On a phone '
              'hotspot the laptop\'s IP changes when the hotspot restarts — just '
              'retype it here instead of reinstalling the app.\n\n'
              'Find it by running "ipconfig" on the laptop and reading the IPv4 '
              'address of the Wi-Fi adapter.',
              style: TextStyle(fontSize: 12.5, height: 1.45),
            ),
          ],
        ),
      ),
    );
  }

  Widget _testResultCard() {
    final color = _testOk ? AppColors.compliant : AppColors.potentialViolation;
    return Card(
      elevation: 0,
      color: color.withValues(alpha: 0.08),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: BorderSide(color: color.withValues(alpha: 0.5)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(_testOk ? Icons.check_circle : Icons.error_outline,
                color: color, size: 20),
            const SizedBox(width: 10),
            Expanded(
              child: Text(_testResult!,
                  style: TextStyle(fontSize: 13, color: color)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _currentValuesCard() {
    return Card(
      elevation: 0,
      color: AppColors.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: const BorderSide(color: AppColors.border),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _kv('Currently using', SettingsService.apiBaseUrl),
            const SizedBox(height: 6),
            _kv('Built into this APK', SettingsService.defaultBaseUrl),
            const SizedBox(height: 6),
            _kv('Source',
                SettingsService.hasOverride ? 'Your override' : 'Build default'),
          ],
        ),
      ),
    );
  }

  Widget _kv(String k, String v) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 130,
          child: Text(k,
              style: const TextStyle(
                  fontSize: 12, color: AppColors.textSecondary)),
        ),
        Expanded(
          child: Text(v,
              style: const TextStyle(
                  fontSize: 12.5, fontWeight: FontWeight.w500)),
        ),
      ],
    );
  }
}
