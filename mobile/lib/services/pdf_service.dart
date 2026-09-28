import 'dart:io';
import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';
import 'api_service.dart';

/// Downloads legal-notice PDFs and opens them with the OS's default viewer.
class PdfService {
  final ApiService api;

  PdfService(this.api);

  /// Fetches the notice for [evidenceRecordId], saves it under the app's
  /// temporary directory, and launches the platform PDF viewer.
  ///
  /// Returns the local file path (already opened) or throws on failure.
  Future<String> downloadAndOpenLegalNotice(int evidenceRecordId) async {
    final result = await api.downloadLegalNotice(evidenceRecordId);
    final dir = await getTemporaryDirectory();
    final safeName = result.filename.replaceAll(RegExp(r'[^A-Za-z0-9._-]'), '_');
    final outFile = File('${dir.path}/$safeName');
    await outFile.writeAsBytes(result.bytes, flush: true);

    final open = await OpenFilex.open(outFile.path, type: 'application/pdf');
    if (open.type != ResultType.done) {
      throw Exception('Could not open PDF viewer: ${open.message}');
    }
    return outFile.path;
  }
}
