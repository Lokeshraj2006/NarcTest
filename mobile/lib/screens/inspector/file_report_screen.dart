import 'package:dio/dio.dart';
import 'package:flutter/material.dart';

import '../../models/inspection_log_models.dart';
import '../../models/scan_models.dart';
import '../../models/violation_models.dart';
import '../../services/api_service.dart';
import '../../utils/app_colors.dart';

/// Inspector files a formal violation report from a scan.
///
/// The rules cited and the severity are derived server-side from the scan's
/// failed checks — the inspector supplies only what the system can't know:
/// which shop this was, and what they observed on site.
///
/// A registry mismatch (MRP higher than registered, a different net quantity
/// or maker) can be cited too, under Rule 6(3), but only after the inspector
/// ticks that they checked the pack: a misread photo alone looks the same.
class FileReportScreen extends StatefulWidget {
  final InspectionDetail detail;
  final int? complaintId;

  const FileReportScreen({
    super.key,
    required this.detail,
    this.complaintId,
  });

  @override
  State<FileReportScreen> createState() => _FileReportScreenState();
}

class _FileReportScreenState extends State<FileReportScreen> {
  final _shopName = TextEditingController();
  final _shopAddress = TextEditingController();
  final _notes = TextEditingController();
  final _api = ApiService();

  bool _submitting = false;
  bool _packChecked = false;
  String? _error;
  ViolationReportResult? _result;

  List<RuleCheckDetail> get _failed =>
      widget.detail.ruleChecks.where((rc) => rc.isFail).toList();

  List<AuthenticityMismatch> get _grounds =>
      widget.detail.authenticity?.citableMismatches ?? const [];

  bool get _citeRegistry => _grounds.isNotEmpty && _packChecked;

  int get _citedCount =>
      _failed.length + (_citeRegistry ? _grounds.length : 0);

  @override
  void dispose() {
    _shopName.dispose();
    _shopAddress.dispose();
    _notes.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final res = await _api.fileViolationReport(
        evidenceRecordId: widget.detail.evidenceRecordId,
        inspectorNotes: _notes.text.trim(),
        shopName: _shopName.text.trim(),
        shopAddress: _shopAddress.text.trim(),
        complaintId: widget.complaintId,
        citeRegistry: _citeRegistry,
        packChecked: _packChecked,
      );
      if (!mounted) return;
      setState(() => _result = res);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = _friendly(e));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  String _friendly(Object e) {
    // DioException.toString() drops the response body, which is exactly where
    // the backend puts its explanation — so read `detail` directly.
    String? detail;
    int? status;
    if (e is DioException) {
      status = e.response?.statusCode;
      final data = e.response?.data;
      if (data is Map && data['detail'] != null) {
        detail = data['detail'].toString();
      }
      if (e.type == DioExceptionType.connectionError ||
          e.type == DioExceptionType.connectionTimeout) {
        return 'Could not reach the backend. Check the address in Settings.';
      }
    }

    final text = detail ?? e.toString();

    if (text.contains('already open')) {
      return 'A report has already been filed for this scan. The Controller '
          'is reviewing it — check the dashboard for its status.';
    }
    if (text.contains('No failed rule checks')) {
      return _grounds.isEmpty
          ? 'This scan has no failed checks, so there is nothing to report.'
          : 'Tick "I checked the pack myself" to cite the registry mismatch.';
    }
    if (text.contains('checked the pack yourself')) {
      return 'Tick "I checked the pack myself" to cite the registry mismatch.';
    }
    if (status == 403) {
      return 'Only inspectors and admins can file reports.';
    }
    // Prefer the backend's own wording; it is written for a human reader.
    return detail ?? 'Could not file the report: $e';
  }

  @override
  Widget build(BuildContext context) {
    if (_result != null) return _successView(_result!);

    final d = widget.detail;
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('File Violation Report'),
        backgroundColor: AppColors.inspectorPrimary,
        foregroundColor: Colors.white,
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_error != null) _errorBanner(_error!),
          _citedCard(),
          if (_grounds.isNotEmpty) ...[
            const SizedBox(height: 12),
            _registryCard(),
          ],
          const SizedBox(height: 12),
          _sectionLabel('Where did you inspect?',
              'Appears on the notice served to the shop'),
          TextField(
            controller: _shopName,
            textCapitalization: TextCapitalization.words,
            decoration: _dec('Shop / premises name', Icons.storefront),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _shopAddress,
            maxLines: 2,
            textCapitalization: TextCapitalization.words,
            decoration: _dec('Shop address', Icons.location_on_outlined),
          ),
          const SizedBox(height: 16),
          _sectionLabel('What did you observe?',
              'Your field notes go to the Controller with the report'),
          TextField(
            controller: _notes,
            maxLines: 4,
            textCapitalization: TextCapitalization.sentences,
            decoration: _dec(
              'Inspector notes',
              Icons.edit_note,
              hint: 'e.g. Stock offered for sale past best-before date. '
                  'MRP sticker overwritten.',
            ),
          ),
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: 0.06),
              borderRadius: BorderRadius.circular(10),
              border:
                  Border.all(color: AppColors.primary.withValues(alpha: 0.3)),
            ),
            child: Row(children: [
              const Icon(Icons.gavel, size: 18, color: AppColors.primary),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'This report goes to the Controller for review. Only the '
                  'Controller can issue a legal notice to the manufacturer '
                  'and shop.',
                  style: TextStyle(
                      fontSize: 12, color: Colors.grey.shade800, height: 1.35),
                ),
              ),
            ]),
          ),
          const SizedBox(height: 8),
          Text('Evidence #${d.evidenceRecordId} · SHA-256 '
              '${d.evidence.sha256Hash.isEmpty ? "—" : "${d.evidence.sha256Hash.substring(0, 16)}…"}',
              style: const TextStyle(
                  fontSize: 11, color: AppColors.textSecondary)),
        ],
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: FilledButton.icon(
            style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(52),
              backgroundColor: AppColors.potentialViolation,
            ),
            icon: _submitting
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white),
                  )
                : const Icon(Icons.send),
            label: Text(
              _submitting
                  ? 'Filing…'
                  : _citedCount == 0 && _grounds.isNotEmpty
                      ? 'Check the pack first'
                      : 'File report ($_citedCount violation'
                          '${_citedCount == 1 ? '' : 's'})',
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
            ),
            onPressed: _submitting || _citedCount == 0 ? null : _submit,
          ),
        ),
      ),
    );
  }

  // ── Pieces ───────────────────────────────────────────────────────────
  InputDecoration _dec(String label, IconData icon, {String? hint}) =>
      InputDecoration(
        labelText: label,
        hintText: hint,
        isDense: true,
        filled: true,
        fillColor: AppColors.surface,
        prefixIcon: Icon(icon, size: 19),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: AppColors.border),
        ),
      );

  Widget _sectionLabel(String title, String subtitle) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title,
              style:
                  const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
          Text(subtitle,
              style: const TextStyle(
                  fontSize: 11.5, color: AppColors.textSecondary)),
        ]),
      );

  Widget _errorBanner(String msg) => Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.potentialViolation.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
              color: AppColors.potentialViolation.withValues(alpha: 0.5)),
        ),
        child: Row(children: [
          const Icon(Icons.error_outline,
              color: AppColors.potentialViolation, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(msg,
                style: const TextStyle(
                    fontSize: 12.5, color: AppColors.potentialViolation)),
          ),
        ]),
      );

  Widget _citedCard() {
    final failed = _failed;
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: AppColors.border),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(
              failed.isEmpty ? Icons.info_outline : Icons.rule,
              size: 19,
              color: failed.isEmpty
                  ? AppColors.textSecondary
                  : AppColors.potentialViolation,
            ),
            const SizedBox(width: 8),
            Text(
              failed.isEmpty
                  ? 'No failed checks on this scan'
                  : 'Rules to be cited (${failed.length})',
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
            ),
          ]),
          const SizedBox(height: 4),
          if (failed.isEmpty)
            Text(
              _grounds.isEmpty
                  ? 'Every check passed or needs manual review, so there is '
                      'nothing to escalate. Reports can only cite failed checks '
                      'or a registry mismatch.'
                  : 'Every check passed or needs manual review. The registry '
                      'mismatch below can still be cited once you have checked '
                      'the pack.',
              style:
                  const TextStyle(fontSize: 12, color: AppColors.textSecondary),
            )
          else
            ...failed.map((rc) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 22,
                        alignment: Alignment.center,
                        child: Text('${rc.ruleNumber}',
                            style: const TextStyle(
                                fontWeight: FontWeight.bold, fontSize: 12)),
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(rc.ruleName,
                                style: const TextStyle(
                                    fontSize: 12.5,
                                    fontWeight: FontWeight.w600)),
                            if (rc.failureReason != null)
                              Text(rc.failureReason!,
                                  style: TextStyle(
                                      fontSize: 11.5,
                                      color: Colors.grey.shade700)),
                            Text(rc.statutoryReference,
                                style: TextStyle(
                                    fontSize: 10.5,
                                    fontStyle: FontStyle.italic,
                                    color: Colors.grey.shade600)),
                          ],
                        ),
                      ),
                    ],
                  ),
                )),
        ]),
      ),
    );
  }

  /// The scan's registry mismatch, cited under Rule 6(3) only once the
  /// inspector ticks that the physical pack contradicts the registry.
  Widget _registryCard() {
    final grounds = _grounds;
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: _packChecked
              ? AppColors.potentialViolation.withValues(alpha: 0.6)
              : AppColors.border,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 14, 14, 6),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Row(children: [
            Icon(Icons.qr_code_2, size: 19, color: AppColors.potentialViolation),
            SizedBox(width: 8),
            Expanded(
              child: Text('Registry mismatch · Rule 6(3)',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
            ),
          ]),
          const SizedBox(height: 6),
          ...grounds.map((m) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const SizedBox(
                      width: 22,
                      child: Icon(Icons.compare_arrows,
                          size: 16, color: AppColors.textSecondary),
                    ),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text.rich(
                        TextSpan(children: [
                          TextSpan(
                              text: '${m.label}: ',
                              style:
                                  const TextStyle(fontWeight: FontWeight.w600)),
                          TextSpan(
                              text: 'label shows ${m.detected ?? '—'}, '
                                  'registered ${m.expected ?? '—'}'),
                        ]),
                        style: const TextStyle(fontSize: 12.5),
                      ),
                    ),
                  ],
                ),
              )),
          const SizedBox(height: 6),
          Text(
            'Rule 6(3) forbids altering a declaration on the pack. The only '
            'exception is a sticker that lowers the MRP, so a lower MRP is '
            'never listed here. A misread photo can look the same, so compare '
            'the pack in your hand with the registered details.',
            style: TextStyle(
                fontSize: 11.5, color: Colors.grey.shade700, height: 1.35),
          ),
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            controlAffinity: ListTileControlAffinity.leading,
            dense: true,
            value: _packChecked,
            activeColor: AppColors.potentialViolation,
            onChanged: _submitting
                ? null
                : (v) => setState(() {
                      _packChecked = v ?? false;
                      _error = null;
                    }),
            title: const Text(
              "I checked the pack myself and it doesn't match the registered "
              'details',
              style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600),
            ),
          ),
        ]),
      ),
    );
  }

  Widget _successView(ViolationReportResult r) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Report Filed'),
        backgroundColor: AppColors.compliant,
        foregroundColor: Colors.white,
        automaticallyImplyLeading: false,
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const SizedBox(height: 10),
          const Center(
            child: Icon(Icons.check_circle,
                size: 68, color: AppColors.compliant),
          ),
          const SizedBox(height: 14),
          Center(
            child: Text(r.reportNumber,
                style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    fontFamily: 'monospace')),
          ),
          const SizedBox(height: 6),
          Center(
            child: Text('Sent to the Controller for review',
                style: TextStyle(
                    fontSize: 13, color: Colors.grey.shade700)),
          ),
          const SizedBox(height: 22),
          Card(
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: const BorderSide(color: AppColors.border),
            ),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(children: [
                _kv('Status', r.statusLabel),
                _kv('Severity', r.severity.toUpperCase()),
                _kv('Rules cited', '${r.violatedRuleCount}'),
                if (r.shopName != null) _kv('Shop', r.shopName!),
                if (r.inspectorBadge != null)
                  _kv('Filed by', '${r.inspectorName} (${r.inspectorBadge})'),
              ]),
            ),
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(13),
            decoration: BoxDecoration(
              color: AppColors.accent.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.accent.withValues(alpha: 0.4)),
            ),
            child: Row(children: [
              const Icon(Icons.hourglass_top, size: 19, color: AppColors.review),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'The Controller will confirm or reject these findings. If '
                  'confirmed, a legal notice is issued to the manufacturer '
                  'and shop.',
                  style: TextStyle(
                      fontSize: 12, height: 1.35, color: Colors.grey.shade800),
                ),
              ),
            ]),
          ),
          const SizedBox(height: 24),
          FilledButton(
            style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(48),
              backgroundColor: AppColors.inspectorPrimary,
            ),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Done'),
          ),
        ],
      ),
    );
  }

  Widget _kv(String k, String v) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(children: [
          SizedBox(
            width: 100,
            child: Text(k,
                style: const TextStyle(
                    fontSize: 12, color: AppColors.textSecondary)),
          ),
          Expanded(
            child: Text(v,
                style: const TextStyle(
                    fontSize: 13, fontWeight: FontWeight.w600)),
          ),
        ]),
      );
}
