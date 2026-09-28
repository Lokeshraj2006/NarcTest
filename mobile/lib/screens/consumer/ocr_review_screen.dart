import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../../models/extracted_fields.dart';
import '../../models/scan_models.dart';
import '../../providers/scan_provider.dart';
import '../../services/field_extractor.dart';
import '../../services/ocr_service.dart';
import '../../utils/app_colors.dart';
import '../../utils/printed_elsewhere.dart';
import 'scan_result_screen.dart';

/// Review-and-correct step between OCR and submission.
///
/// OCR misreads are common on curved/glossy packaging, and a wrong MRP or
/// GSTIN would produce a bogus compliance verdict. This screen shows what
/// the extractor found, lets the user fix it, then submits.
class OcrReviewScreen extends StatefulWidget {
  final String imagePath;
  final String? barcode;
  final double? gpsLatitude;
  final double? gpsLongitude;
  final double? gpsAccuracyMeters;
  final ExtractedFields fields;

  // Calibration inputs — the backend measures font size against the
  // barcode's known physical width, so rules 9-11 depend on these.
  final List<double>? barcodeBbox;
  final String? barcodeFormat;
  final List<OcrTextBlockGeometry>? textBlocks;
  final int? imageWidthPx;
  final int? imageHeightPx;

  // Chain of custody.
  final DateTime? deviceTimestamp;
  final DateTime? ntpTimestamp;
  final double? ntpDriftSeconds;

  /// Set when this is a rescan of an earlier scan, which stays unchanged.
  final int? rescanOfId;

  const OcrReviewScreen({
    super.key,
    required this.imagePath,
    required this.fields,
    this.barcode,
    this.gpsLatitude,
    this.gpsLongitude,
    this.gpsAccuracyMeters,
    this.barcodeBbox,
    this.barcodeFormat,
    this.textBlocks,
    this.imageWidthPx,
    this.imageHeightPx,
    this.deviceTimestamp,
    this.ntpTimestamp,
    this.ntpDriftSeconds,
    this.rescanOfId,
  });

  @override
  State<OcrReviewScreen> createState() => _OcrReviewScreenState();
}

class _OcrReviewScreenState extends State<OcrReviewScreen> {
  late final Map<String, TextEditingController> _controllers;
  final _sellerNameCtl = TextEditingController();
  final _sellerAddressCtl = TextEditingController();
  bool _showRawText = false;
  bool _readingExtraPhoto = false;

  /// Photos of other faces ("Scan another part"). Sent with the scan so the
  /// server can look for the veg mark on them too; the evidence photo stays
  /// the first one.
  final List<String> _extraPhotos = [];
  static const _maxExtraPhotos = 3;

  // Shown in the "not found" card; batch number is only filled, not nagged.
  static const _oftenElsewhere = ['mfgDate', 'expiryDate', 'mrp'];

  static const _fieldLabels = <String, String>{
    'productName': 'Product name',
    'manufacturer': 'Manufacturer',
    'manufacturerAddress': 'Manufacturer address',
    'countryOfOrigin': 'Country of origin',
    'netQuantity': 'Net quantity',
    'mrp': 'MRP (₹)',
    'mfgDate': 'Mfg date',
    'expiryDate': 'Expiry / best before',
    'batchNumber': 'Batch number',
    'fssaiNumber': 'FSSAI licence no.',
    'gstNumber': 'GSTIN',
    'lmpcNumber': 'LMPC registration no.',
    'consumerCarePhone': 'Consumer care phone',
    'consumerCareEmail': 'Consumer care email',
    'ingredients': 'Ingredients',
  };

  @override
  void initState() {
    super.initState();
    final f = widget.fields;
    _controllers = {
      'productName': TextEditingController(text: f.productName ?? ''),
      'manufacturer': TextEditingController(text: f.manufacturer ?? ''),
      'manufacturerAddress':
          TextEditingController(text: f.manufacturerAddress ?? ''),
      'countryOfOrigin': TextEditingController(text: f.countryOfOrigin ?? ''),
      'netQuantity': TextEditingController(text: f.netQuantity ?? ''),
      'mrp': TextEditingController(text: f.mrp ?? ''),
      'mfgDate': TextEditingController(text: f.mfgDate ?? ''),
      'expiryDate': TextEditingController(text: f.expiryDate ?? ''),
      'batchNumber': TextEditingController(text: f.batchNumber ?? ''),
      'fssaiNumber': TextEditingController(text: f.fssaiNumber ?? ''),
      'gstNumber': TextEditingController(text: f.gstNumber ?? ''),
      'lmpcNumber': TextEditingController(text: f.lmpcNumber ?? ''),
      'consumerCarePhone':
          TextEditingController(text: f.consumerCarePhone ?? ''),
      'consumerCareEmail':
          TextEditingController(text: f.consumerCareEmail ?? ''),
      'ingredients': TextEditingController(text: f.ingredients ?? ''),
    };
    // Keep the "not found" card in step with what the user types.
    for (final key in _oftenElsewhere) {
      _controllers[key]!.addListener(_onKeyFieldChanged);
    }
  }

  void _onKeyFieldChanged() {
    if (mounted) setState(() {});
  }

  List<String> get _missingKeys => [
        for (final key in _oftenElsewhere)
          if (_controllers[key]!.text.trim().isEmpty) key,
      ];

  /// Reads another surface of the pack (lid, seal, bottom, the veg mark) and
  /// fills the fields still blank; values it reads differently are offered,
  /// not applied. The photo goes with the scan for the veg-mark check. The
  /// evidence photo stays the first one; values that differ from what OCR
  /// first read are recorded as edited fields.
  Future<void> _scanAnotherPart() async {
    if (_extraPhotos.length >= _maxExtraPhotos) {
      _snack('Up to $_maxExtraPhotos extra photos can be sent with one scan.');
      return;
    }
    final shot = await ImagePicker().pickImage(source: ImageSource.camera);
    if (shot == null || !mounted) return;
    setState(() {
      _extraPhotos.add(shot.path);
      _readingExtraPhoto = true;
    });
    final ocr = OcrService();
    try {
      final read = await ocr.recognize(shot.path);
      final text = read.blocks.map((b) => b.text).join('\n');
      var extra = FieldExtractor().extract(text, lines: read.lines);
      // The label said its dates are printed elsewhere, and this part prints
      // them with no headings ("27/08/26 26/05/27"): take them by order, for
      // the user to check.
      if (extra.mfgDate == null &&
          extra.expiryDate == null &&
          datesPrintedOn(widget.fields.rawText) != null) {
        final pair = unlabelledDatePair(text);
        if (pair != null) {
          extra = extra.copyWith(mfgDate: pair.made, expiryDate: pair.expires);
        }
      }
      final current = {
        for (final e in _controllers.entries) e.key: e.value.text,
      };
      final fills = valuesToFill(current: current, extra: extra);
      final differ = valuesThatDiffer(current: current, extra: extra);
      if (!mounted) return;
      setState(() {
        for (final e in fills.entries) {
          _controllers[e.key]!.text = e.value;
        }
      });
      final applied = [...fills.keys];
      if (differ.isNotEmpty) {
        final chosen = await _askWhichToUse(differ);
        if (!mounted) return;
        if (chosen.isNotEmpty) {
          setState(() {
            for (final key in chosen) {
              _controllers[key]!.text = differ[key]!.read;
            }
          });
          applied.addAll(chosen);
        }
      }
      final names = applied.map((k) => elsewhereFieldLabels[k]!).toList();
      _snack(applied.isEmpty
          ? 'No new details read from that photo. It is still sent with the '
              'scan to look for the veg mark.'
          : 'From the extra photo: ${joinLabels(names)}. Check they are right.');
    } catch (_) {
      _snack('Could not read text on that photo. It is still sent with the '
          'scan to look for the veg mark.');
    } finally {
      ocr.dispose();
      if (mounted) setState(() => _readingExtraPhoto = false);
    }
  }

  /// Which of the extra photo's differing readings to use; none by default.
  Future<Set<String>> _askWhichToUse(
      Map<String, ({String current, String read})> differ) async {
    final chosen = <String>{};
    final result = await showDialog<Set<String>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('The extra photo reads some details differently'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Tick the ones to take from the extra photo. Check the pack '
                  'if you are not sure.',
                  style: TextStyle(fontSize: 13),
                ),
                for (final e in differ.entries)
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    value: chosen.contains(e.key),
                    onChanged: (on) => setDialogState(() {
                      on == true ? chosen.add(e.key) : chosen.remove(e.key);
                    }),
                    title: Text(_fieldLabels[e.key] ?? e.key),
                    subtitle: Text(
                        'Now: ${e.value.current}\nExtra photo: ${e.value.read}'),
                  ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(<String>{}),
              child: const Text('Keep current'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(Set.of(chosen)),
              child: const Text('Use ticked'),
            ),
          ],
        ),
      ),
    );
    return result ?? <String>{};
  }

  void _snack(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  void dispose() {
    for (final key in _oftenElsewhere) {
      _controllers[key]!.removeListener(_onKeyFieldChanged);
    }
    for (final c in _controllers.values) {
      c.dispose();
    }
    _sellerNameCtl.dispose();
    _sellerAddressCtl.dispose();
    super.dispose();
  }

  String? _val(String key) {
    final t = _controllers[key]!.text.trim();
    return t.isEmpty ? null : t;
  }

  Future<void> _submit() async {
    final corrected = ExtractedFields(
      rawText: widget.fields.rawText,
      productName: _val('productName'),
      manufacturer: _val('manufacturer'),
      manufacturerAddress: _val('manufacturerAddress'),
      countryOfOrigin: _val('countryOfOrigin'),
      netQuantity: _val('netQuantity'),
      mrp: _val('mrp'),
      mfgDate: _val('mfgDate'),
      expiryDate: _val('expiryDate'),
      batchNumber: _val('batchNumber'),
      fssaiNumber: _val('fssaiNumber'),
      gstNumber: _val('gstNumber'),
      lmpcNumber: _val('lmpcNumber'),
      consumerCarePhone: _val('consumerCarePhone'),
      consumerCareEmail: _val('consumerCareEmail'),
      ingredients: _val('ingredients'),
    );

    final ctx = ScanContext(
      barcode: widget.barcode,
      gpsLatitude: widget.gpsLatitude,
      gpsLongitude: widget.gpsLongitude,
      gpsAccuracyMeters: widget.gpsAccuracyMeters,
      ocrFields: corrected.toOcrFields(),
      sellerName: _sellerNameCtl.text.trim().isEmpty
          ? null
          : _sellerNameCtl.text.trim(),
      sellerAddress: _sellerAddressCtl.text.trim().isEmpty
          ? null
          : _sellerAddressCtl.text.trim(),
      barcodeBbox: widget.barcodeBbox,
      barcodeFormat: widget.barcodeFormat,
      textBlocks: widget.textBlocks,
      imageWidthPx: widget.imageWidthPx,
      imageHeightPx: widget.imageHeightPx,
      deviceTimestamp: widget.deviceTimestamp,
      ntpTimestamp: widget.ntpTimestamp,
      ntpDriftSeconds: widget.ntpDriftSeconds,
      rescanOfId: widget.rescanOfId,
      // What OCR read before any correction, so every change is on record.
      extractedFields: widget.fields.toOcrFields()..rawText = null,
    );

    final provider = context.read<ScanProvider>();
    final result = await provider.submit(
      imagePath: widget.imagePath,
      extraImagePaths: List.of(_extraPhotos),
      context: ctx,
    );

    if (!mounted) return;
    if (result == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(provider.errorMessage ?? 'Scan failed.')),
      );
      return;
    }
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => ScanResultScreen(
          result: result,
          capturedImagePath: widget.imagePath,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final scan = context.watch<ScanProvider>();
    final detected = widget.fields.filledFieldCount;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Review Details'),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
      ),
      body: AbsorbPointer(
        absorbing: scan.submitting,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (widget.rescanOfId != null) ...[
              _rescanBanner(),
              const SizedBox(height: 12),
            ],
            _summaryCard(detected),
            const SizedBox(height: 12),
            _thumbnailAndBarcode(),
            const SizedBox(height: 12),
            _otherPartsCard(),
            const SizedBox(height: 12),
            if (_missingKeys.isNotEmpty) ...[
              _printedElsewhereCard(),
              const SizedBox(height: 12),
            ],
            _sectionHeader('Label details',
                'Correct anything OCR misread. Changes are recorded with the scan.'),
            ..._fieldLabels.entries.map(
              (e) => _fieldRow(e.key, e.value),
            ),
            const SizedBox(height: 8),
            _sectionHeader('Shop / seller', 'Optional — appears on legal notice'),
            _plainField(_sellerNameCtl, 'Shop name'),
            _plainField(_sellerAddressCtl, 'Shop address', maxLines: 2),
            const SizedBox(height: 8),
            _rawTextTile(),
          ],
        ),
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: FilledButton.icon(
            style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(52),
              backgroundColor: AppColors.primary,
            ),
            icon: scan.submitting
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white),
                  )
                : const Icon(Icons.verified),
            label: Text(
              scan.submitting ? 'Checking compliance…' : 'Check Compliance',
              style:
                  const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
            ),
            onPressed: scan.submitting ? null : _submit,
          ),
        ),
      ),
    );
  }

  Widget _rescanBanner() {
    return Card(
      elevation: 0,
      color: AppColors.primary.withValues(alpha: 0.06),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: AppColors.primary.withValues(alpha: 0.4)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            const Icon(Icons.replay, color: AppColors.primary),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                'Rescan of scan #${widget.rescanOfId}. It is saved as a new '
                'scan; the original stays unchanged.',
                style:
                    const TextStyle(fontSize: 13, color: AppColors.textPrimary),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _printedElsewhereCard() {
    final missing = _missingKeys;
    final names = missing.map((k) => elsewhereFieldLabels[k]!).toList();
    final raw = widget.fields.rawText;
    final datesMissing = missing.contains('mfgDate') || missing.contains('expiryDate');
    final where = (datesMissing ? datesPrintedOn(raw) : null) ??
        (missing.contains('mrp') ? pricePrintedOn(raw) : null);
    final what = joinLabels(names);
    final title = '${what[0].toUpperCase()}${what.substring(1)} not found';

    return Card(
      elevation: 0,
      color: AppColors.review.withValues(alpha: 0.08),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: AppColors.review.withValues(alpha: 0.5)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              const Icon(Icons.search, color: AppColors.review),
              const SizedBox(width: 8),
              Expanded(
                child: Text(title,
                    style: const TextStyle(
                        fontWeight: FontWeight.bold, color: AppColors.review)),
              ),
            ]),
            const SizedBox(height: 6),
            Text(
              where != null
                  ? 'The label says it is printed on the ${where.toUpperCase()}. '
                      'Please check there.'
                  : 'Please check whether it is printed somewhere else on the pack. '
                      'Common places: the top or lid, the seal, the crimped edge of a '
                      'pouch, the bottom, or the neck of a bottle.',
              style: const TextStyle(fontSize: 13, color: AppColors.textPrimary),
            ),
            const SizedBox(height: 4),
            const Text(
              'If you find it, type it in below, or photograph that part with '
              'Scan another part above.',
              style: TextStyle(fontSize: 13, color: AppColors.textPrimary),
            ),
          ],
        ),
      ),
    );
  }

  /// Always available: the veg mark or a detail can be on any face.
  Widget _otherPartsCard() {
    final count = _extraPhotos.length;
    return Card(
      elevation: 0,
      color: AppColors.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: AppColors.border),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Other parts of the pack',
                style: TextStyle(
                    fontWeight: FontWeight.bold, color: AppColors.textPrimary)),
            const SizedBox(height: 4),
            const Text(
              'Veg mark or details on another side, the lid or the seal? '
              'Photograph that part. Blank fields are filled from it, and it is '
              'sent with the scan to look for the FSSAI veg mark.',
              style: TextStyle(fontSize: 13, color: AppColors.textPrimary),
            ),
            if (count > 0) ...[
              const SizedBox(height: 10),
              SizedBox(
                height: 76,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: count,
                  separatorBuilder: (_, __) => const SizedBox(width: 8),
                  itemBuilder: (_, i) => Stack(
                    children: [
                      ClipRRect(
                        borderRadius: BorderRadius.circular(8),
                        child: Image.file(File(_extraPhotos[i]),
                            width: 58, height: 76, fit: BoxFit.cover),
                      ),
                      Positioned(
                        right: 0,
                        top: 0,
                        child: InkWell(
                          onTap: _readingExtraPhoto
                              ? null
                              : () => setState(() => _extraPhotos.removeAt(i)),
                          child: Container(
                            decoration: const BoxDecoration(
                                color: Colors.black54, shape: BoxShape.circle),
                            padding: const EdgeInsets.all(2),
                            child: const Icon(Icons.close,
                                size: 14, color: Colors.white),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 4),
              Text(
                '$count extra photo${count == 1 ? '' : 's'} will be sent with '
                'the scan.',
                style: const TextStyle(
                    fontSize: 12, color: AppColors.textSecondary),
              ),
            ],
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: _readingExtraPhoto || count >= _maxExtraPhotos
                  ? null
                  : _scanAnotherPart,
              icon: _readingExtraPhoto
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.add_a_photo_outlined, size: 18),
              label: Text(_readingExtraPhoto
                  ? 'Reading…'
                  : count >= _maxExtraPhotos
                      ? '$_maxExtraPhotos extra photos added'
                      : 'Scan another part'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _summaryCard(int detected) {
    final ok = detected >= 5;
    final color = ok ? AppColors.compliant : AppColors.review;
    return Card(
      elevation: 0,
      color: color.withValues(alpha: 0.08),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: color.withValues(alpha: 0.5)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Icon(ok ? Icons.check_circle : Icons.info_outline, color: color),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '$detected of ${ExtractedFields.totalFieldCount} fields detected',
                    style: TextStyle(
                        fontWeight: FontWeight.bold, color: color),
                  ),
                  const SizedBox(height: 2),
                  const Text(
                    'Blank fields are treated as "not declared" by the compliance rules.',
                    style: TextStyle(
                        fontSize: 12, color: AppColors.textSecondary),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _thumbnailAndBarcode() {
    final file = File(widget.imagePath);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (file.existsSync())
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: Image.file(file,
                width: 90, height: 120, fit: BoxFit.cover),
          ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Barcode',
                  style: TextStyle(
                      fontSize: 12, color: AppColors.textSecondary)),
              Text(
                widget.barcode ?? 'Not detected',
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  color: widget.barcode == null
                      ? AppColors.textSecondary
                      : AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              const Text('Location',
                  style: TextStyle(
                      fontSize: 12, color: AppColors.textSecondary)),
              Text(
                (widget.gpsLatitude != null && widget.gpsLongitude != null)
                    ? '${widget.gpsLatitude!.toStringAsFixed(5)}, ${widget.gpsLongitude!.toStringAsFixed(5)}'
                    : 'Unavailable',
                style: const TextStyle(fontSize: 13),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _sectionHeader(String title, String subtitle) {
    return Padding(
      padding: const EdgeInsets.only(top: 8, bottom: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 15,
                  color: AppColors.textPrimary)),
          Text(subtitle,
              style: const TextStyle(
                  fontSize: 12, color: AppColors.textSecondary)),
        ],
      ),
    );
  }

  Widget _fieldRow(String key, String label) {
    final wasDetected = _controllers[key]!.text.trim().isNotEmpty;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: TextField(
        controller: _controllers[key],
        maxLines: key == 'ingredients' || key == 'manufacturerAddress' ? 2 : 1,
        style: const TextStyle(fontSize: 14),
        decoration: InputDecoration(
          labelText: label,
          isDense: true,
          filled: true,
          fillColor: AppColors.surface,
          hintText: wasDetected ? null : 'Not detected — type if visible',
          prefixIcon: Icon(
            wasDetected ? Icons.check_circle_outline : Icons.help_outline,
            size: 18,
            color: wasDetected ? AppColors.compliant : AppColors.textSecondary,
          ),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(8),
            borderSide: const BorderSide(color: AppColors.border),
          ),
        ),
      ),
    );
  }

  Widget _plainField(TextEditingController c, String label,
      {int maxLines = 1}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: TextField(
        controller: c,
        maxLines: maxLines,
        style: const TextStyle(fontSize: 14),
        decoration: InputDecoration(
          labelText: label,
          isDense: true,
          filled: true,
          fillColor: AppColors.surface,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(8),
            borderSide: const BorderSide(color: AppColors.border),
          ),
        ),
      ),
    );
  }

  Widget _rawTextTile() {
    return Card(
      elevation: 0,
      color: AppColors.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: const BorderSide(color: AppColors.border),
      ),
      child: Column(
        children: [
          ListTile(
            dense: true,
            leading: const Icon(Icons.text_snippet_outlined, size: 20),
            title: const Text('Raw OCR text',
                style: TextStyle(fontSize: 14)),
            trailing: Icon(
                _showRawText ? Icons.expand_less : Icons.expand_more),
            onTap: () => setState(() => _showRawText = !_showRawText),
          ),
          if (_showRawText)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              child: SelectableText(
                widget.fields.rawText.isEmpty
                    ? '(no text recognised)'
                    : widget.fields.rawText,
                style: const TextStyle(
                    fontSize: 11.5,
                    height: 1.4,
                    color: AppColors.textSecondary),
              ),
            ),
        ],
      ),
    );
  }
}
