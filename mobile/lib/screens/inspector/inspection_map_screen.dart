import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:intl/intl.dart';
import 'package:latlong2/latlong.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../models/inspection_log_models.dart';
import '../../models/pending_complaint_model.dart';
import '../../providers/inspection_log_provider.dart';
import '../../providers/pending_complaints_provider.dart';
import '../../utils/app_colors.dart';
import '../../utils/verdict.dart';
import 'inspection_detail_screen.dart';

/// Field map for inspectors: where consumers have reported problems, and
/// where scans have already been done.
///
/// Uses OpenStreetMap tiles via flutter_map (the Leaflet equivalent), so the
/// pin semantics match the React admin dashboard exactly.
class InspectionMapScreen extends StatefulWidget {
  const InspectionMapScreen({super.key});

  @override
  State<InspectionMapScreen> createState() => _InspectionMapScreenState();
}

enum _Layer { complaints, scans, both }

class _InspectionMapScreenState extends State<InspectionMapScreen> {
  final MapController _map = MapController();
  _Layer _layer = _Layer.both;
  bool _fitted = false;

  // Bengaluru — a sensible fallback before any pin has coordinates.
  static const LatLng _fallbackCentre = LatLng(12.9716, 77.5946);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<InspectionLogProvider>().refresh();
      context.read<PendingComplaintsProvider>().refresh();
    });
  }

  List<InspectionLogRow> _scanRows(InspectionLogProvider p) => p.rows
      .where((r) => r.gpsLatitude != null && r.gpsLongitude != null)
      .toList();

  List<PendingComplaintRow> _complaintRows(PendingComplaintsProvider p) => p.rows
      .where((r) => r.gpsLatitude != null && r.gpsLongitude != null)
      .toList();

  void _fitToPins(List<LatLng> points) {
    if (points.isEmpty || _fitted) return;
    _fitted = true;
    if (points.length == 1) {
      _map.move(points.first, 15);
      return;
    }
    _map.fitCamera(
      CameraFit.bounds(
        bounds: LatLngBounds.fromPoints(points),
        padding: const EdgeInsets.all(56),
        maxZoom: 16,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final logs = context.watch<InspectionLogProvider>();
    final complaints = context.watch<PendingComplaintsProvider>();

    final scans = _scanRows(logs);
    final pending = _complaintRows(complaints);

    final showComplaints = _layer != _Layer.scans;
    final showScans = _layer != _Layer.complaints;

    final markers = <Marker>[
      if (showScans) ...scans.map(_scanMarker),
      if (showComplaints) ...pending.map(_complaintMarker),
    ];

    final points = <LatLng>[
      if (showScans) ...scans.map((r) => LatLng(r.gpsLatitude!, r.gpsLongitude!)),
      if (showComplaints)
        ...pending.map((r) => LatLng(r.gpsLatitude!, r.gpsLongitude!)),
    ];
    WidgetsBinding.instance.addPostFrameCallback((_) => _fitToPins(points));

    return Column(
      children: [
        _layerBar(scans.length, pending.length),
        Expanded(
          child: Stack(
            children: [
              FlutterMap(
                mapController: _map,
                options: MapOptions(
                  initialCenter: points.isNotEmpty ? points.first : _fallbackCentre,
                  initialZoom: points.isNotEmpty ? 13 : 11,
                  interactionOptions: const InteractionOptions(
                    flags: InteractiveFlag.all & ~InteractiveFlag.rotate,
                  ),
                ),
                children: [
                  TileLayer(
                    urlTemplate:
                        'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                    userAgentPackageName:
                        'gov.in.legalmetrology.labelguard_mobile',
                    maxZoom: 19,
                  ),
                  MarkerLayer(markers: markers),
                  const RichAttributionWidget(
                    attributions: [
                      TextSourceAttribution('OpenStreetMap contributors'),
                    ],
                  ),
                ],
              ),
              if (markers.isEmpty) _emptyOverlay(logs, complaints),
              Positioned(right: 12, bottom: 92, child: _legend()),
            ],
          ),
        ),
      ],
    );
  }

  // ── Markers ──────────────────────────────────────────────────────────
  Marker _scanMarker(InspectionLogRow r) {
    final color = AppColors.pin(r.pinColor);
    return Marker(
      point: LatLng(r.gpsLatitude!, r.gpsLongitude!),
      width: 40,
      height: 40,
      child: GestureDetector(
        onTap: () => _showScanSheet(r),
        child: _pin(color, Verdict.pinGlyph(r.overallStatus)),
      ),
    );
  }

  Marker _complaintMarker(PendingComplaintRow r) {
    return Marker(
      point: LatLng(r.gpsLatitude!, r.gpsLongitude!),
      width: 40,
      height: 40,
      child: GestureDetector(
        onTap: () => _showComplaintSheet(r),
        child: _pin(AppColors.accent, Icons.campaign),
      ),
    );
  }

  Widget _pin(Color color, IconData icon) {
    return Container(
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white, width: 2.5),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.35),
            blurRadius: 5,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Icon(icon, color: Colors.white, size: 20),
    );
  }

  // ── Layer toggle ─────────────────────────────────────────────────────
  Widget _layerBar(int scanCount, int complaintCount) {
    return Container(
      color: Colors.grey.shade100,
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      child: Row(
        children: [
          Expanded(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(children: [
                _chip('To visit ($complaintCount)', _Layer.complaints),
                const SizedBox(width: 6),
                _chip('Scanned ($scanCount)', _Layer.scans),
                const SizedBox(width: 6),
                _chip('Both', _Layer.both),
              ]),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.my_location),
            tooltip: 'Fit all pins',
            onPressed: () {
              _fitted = false;
              setState(() {});
            },
          ),
        ],
      ),
    );
  }

  Widget _chip(String label, _Layer value) {
    return ChoiceChip(
      label: Text(label, style: const TextStyle(fontSize: 12)),
      selected: _layer == value,
      onSelected: (_) => setState(() {
        _layer = value;
        _fitted = false;
      }),
      selectedColor: AppColors.primary.withValues(alpha: 0.18),
    );
  }

  Widget _legend() {
    Widget row(Color c, IconData i, String label) => Padding(
          padding: const EdgeInsets.symmetric(vertical: 2),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Container(
              width: 16,
              height: 16,
              decoration: BoxDecoration(
                color: c,
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white, width: 1.5),
              ),
              child: Icon(i, size: 10, color: Colors.white),
            ),
            const SizedBox(width: 6),
            Text(label, style: const TextStyle(fontSize: 10.5)),
          ]),
        );

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.94),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        row(AppColors.accent, Icons.campaign, 'Reported'),
        row(AppColors.potentialViolation, Icons.priority_high, 'Action needed'),
        row(AppColors.review, Icons.question_mark, 'Needs review'),
        row(AppColors.compliant, Icons.check, 'Compliant'),
      ]),
    );
  }

  Widget _emptyOverlay(
      InspectionLogProvider logs, PendingComplaintsProvider complaints) {
    final loading = logs.loading || complaints.loading;
    final error = logs.errorMessage ?? complaints.errorMessage;
    return Center(
      child: Container(
        margin: const EdgeInsets.all(28),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.94),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.border),
        ),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          if (loading)
            const CircularProgressIndicator()
          else
            Icon(error != null ? Icons.cloud_off : Icons.location_off,
                size: 44, color: Colors.grey.shade500),
          const SizedBox(height: 10),
          Text(
            loading
                ? 'Loading map data…'
                : error ?? 'No scans or complaints with GPS coordinates yet.',
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 12.5),
          ),
        ]),
      ),
    );
  }

  // ── Bottom sheets ────────────────────────────────────────────────────
  void _showScanSheet(InspectionLogRow r) {
    final color = AppColors.pin(r.pinColor);
    showModalBottomSheet(
      context: context,
      showDragHandle: true,
      builder: (_) => Padding(
        padding: const EdgeInsets.fromLTRB(18, 0, 18, 24),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Row(children: [
            Icon(Verdict.icon(r.overallStatus), color: color),
            const SizedBox(width: 8),
            Expanded(
              child: Text(r.productName ?? 'Evidence #${r.evidenceRecordId}',
                  style: const TextStyle(
                      fontWeight: FontWeight.bold, fontSize: 15)),
            ),
            Text(Verdict.label(r.overallStatus),
                style: TextStyle(
                    color: color, fontWeight: FontWeight.bold, fontSize: 11)),
          ]),
          const SizedBox(height: 8),
          _sheetMeta(
            DateFormat('dd MMM yyyy, HH:mm').format(r.timestamp),
            r.gpsLatitude!,
            r.gpsLongitude!,
          ),
          if (r.actionReason != null) ...[
            const SizedBox(height: 8),
            Text(r.actionReason!,
                style: TextStyle(fontSize: 12.5, color: Colors.grey.shade800)),
          ],
          const SizedBox(height: 14),
          Row(children: [
            Expanded(
              child: OutlinedButton.icon(
                icon: const Icon(Icons.directions, size: 18),
                label: const Text('Directions'),
                onPressed: () =>
                    _openDirections(r.gpsLatitude!, r.gpsLongitude!),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: FilledButton.icon(
                style: FilledButton.styleFrom(backgroundColor: AppColors.primary),
                icon: const Icon(Icons.open_in_new, size: 18),
                label: const Text('Open'),
                onPressed: () {
                  Navigator.of(context).pop();
                  Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => InspectionDetailScreen(
                        evidenceRecordId: r.evidenceRecordId),
                  ));
                },
              ),
            ),
          ]),
        ]),
      ),
    );
  }

  void _showComplaintSheet(PendingComplaintRow r) {
    showModalBottomSheet(
      context: context,
      showDragHandle: true,
      builder: (_) => Padding(
        padding: const EdgeInsets.fromLTRB(18, 0, 18, 24),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Row(children: [
            const Icon(Icons.campaign, color: AppColors.accent),
            const SizedBox(width: 8),
            Expanded(
              child: Text(r.productName ?? 'Consumer report',
                  style: const TextStyle(
                      fontWeight: FontWeight.bold, fontSize: 15)),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: AppColors.accent.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Text('VISIT',
                  style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                      color: AppColors.accent)),
            ),
          ]),
          const SizedBox(height: 8),
          _sheetMeta(
            'Reported ${DateFormat('dd MMM yyyy, HH:mm').format(r.filedAt)}',
            r.gpsLatitude!,
            r.gpsLongitude!,
          ),
          if (r.actionReason != null) ...[
            const SizedBox(height: 8),
            Text(r.actionReason!,
                style: TextStyle(fontSize: 12.5, color: Colors.grey.shade800)),
          ],
          const SizedBox(height: 14),
          Row(children: [
            Expanded(
              child: OutlinedButton.icon(
                icon: const Icon(Icons.directions, size: 18),
                label: const Text('Directions'),
                onPressed: () =>
                    _openDirections(r.gpsLatitude!, r.gpsLongitude!),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: FilledButton.icon(
                style: FilledButton.styleFrom(backgroundColor: AppColors.primary),
                icon: const Icon(Icons.open_in_new, size: 18),
                label: const Text('Evidence'),
                onPressed: r.evidenceRecordId == null
                    ? null
                    : () {
                        Navigator.of(context).pop();
                        Navigator.of(context).push(MaterialPageRoute(
                          builder: (_) => InspectionDetailScreen(
                              evidenceRecordId: r.evidenceRecordId!),
                        ));
                      },
              ),
            ),
          ]),
        ]),
      ),
    );
  }

  Widget _sheetMeta(String when, double lat, double lng) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Text(
        '$when\n${lat.toStringAsFixed(5)}, ${lng.toStringAsFixed(5)}',
        style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
      ),
    );
  }

  Future<void> _openDirections(double lat, double lng) async {
    final uri = Uri.parse('geo:$lat,$lng?q=$lat,$lng');
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      final web = Uri.parse(
          'https://www.openstreetmap.org/?mlat=$lat&mlon=$lng#map=18/$lat/$lng');
      await launchUrl(web, mode: LaunchMode.externalApplication);
    }
  }
}
